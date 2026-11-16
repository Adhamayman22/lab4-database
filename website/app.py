import os
import re
import textwrap
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps

import bcrypt
import mysql.connector
import pymysql
from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, g, redirect, render_template, request, session, url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))  # reads the .env file into os.environ

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]  # signs the session cookie
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # JavaScript cannot read the cookie
    SESSION_COOKIE_SAMESITE="Lax",  # not sent with POSTs from other sites
    MAX_CONTENT_LENGTH=3 * 1024 * 1024,  # refuse requests bigger than 3 MB
)

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------
# Databases: one connection per request, closed when the request ends.
#   registration -> users and their to-dos (Lab 2)
#   library      -> authors and books (Lab 3)
# ---------------------------------------------------------------

def connect(database):
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD", ""),
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_db():
    if "db" not in g:
        g.db = connect(os.environ.get("DB_NAME", "registration"))
    return g.db


def get_library_db():
    if "library_db" not in g:
        g.library_db = connect(os.environ.get("LIBRARY_DB_NAME", "library"))
    return g.library_db


def run_prepared(sql, params):
    """Bonus (F2.1): a real server-side prepared statement.

    The SQL text has ? placeholders and is sent to MySQL on its own
    (COM_STMT_PREPARE); the values are sent afterwards, separately, in the
    binary protocol (COM_STMT_EXECUTE). What the user typed is never part of
    the SQL text, so it can only ever be a value.
    """
    connection = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("LIBRARY_DB_NAME", "library"),
        charset="utf8mb4",
        use_pure=True,
    )
    try:
        cursor = connection.cursor(prepared=True)
        cursor.execute(sql, params)
        columns = cursor.column_names
        rows = []
        for row in cursor.fetchall():
            rows.append({
                column: value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else value
                for column, value in zip(columns, row)
            })
        cursor.close()
        return rows
    finally:
        connection.close()


@app.teardown_appcontext
def close_db(_error):
    for key in ("db", "library_db"):
        db = g.pop(key, None)
        if db is not None:
            db.close()


# ---------------------------------------------------------------
# Passwords (bcrypt)
# ---------------------------------------------------------------

def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


# Used when the e-mail does not exist, so "unknown e-mail" takes as long
# as "wrong password" and the two cannot be told apart by timing.
DUMMY_HASH = hash_password("dummy-password")


def password_matches(password, stored_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("ascii"))
    except ValueError:  # bcrypt refuses passwords longer than 72 bytes
        return False


# ---------------------------------------------------------------
# Validation: the SAME rules and messages as the JavaScript
# ---------------------------------------------------------------

def validate_register(name, email, password, confirm_password):
    errors = {}

    if name == "":
        errors["name"] = "Name is required"
    elif len(name) > 100:
        errors["name"] = "Name is too long (100 characters at most)"

    if email == "":
        errors["email"] = "Email is required"
    elif len(email) > 255:
        errors["email"] = "Email is too long (255 characters at most)"
    elif not EMAIL_PATTERN.match(email):
        errors["email"] = "Enter a valid email address"

    if password == "":
        errors["password"] = "Password is required"
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    elif len(password.encode("utf-8")) > 72:
        errors["password"] = "Password is too long (72 bytes at most)"
    elif not re.search(r"[A-Z]", password):
        errors["password"] = "Password must contain an uppercase letter"
    elif not re.search(r"[a-z]", password):
        errors["password"] = "Password must contain a lowercase letter"
    elif not re.search(r"[^A-Za-z0-9]", password):
        errors["password"] = "Password must contain a symbol (e.g. ! @ # $)"

    if confirm_password == "":
        errors["confirm_password"] = "Confirm password is required"
    elif password != "" and password != confirm_password:
        errors["confirm_password"] = "Passwords do not match"

    return errors


def validate_login(email, password):
    errors = {}
    if email == "":
        errors["email"] = "Email is required"
    if password == "":
        errors["password"] = "Password is required"
    return errors


def validate_title(raw_title):
    """Returns (clean_title, error_message_or_None)."""
    title = raw_title.strip()
    if title == "":
        return title, "Title is required"
    if len(title) > 200:
        return title, "Title is too long (200 characters at most)"
    return title, None


PRICE_PATTERN = re.compile(r"^\d+(\.\d{1,2})?$")
MAX_PRICE = Decimal("100000000")  # DECIMAL(10,2) holds up to 99999999.99


YEAR_PATTERN = re.compile(r"^\d{1,4}$")
MIN_YEAR = 1000

# The three lists of a book form: field name -> (label, "the ... " for the message).
BOOK_CHOICES = {
    "author_id": "author",
    "publisher_id": "publisher",
    "category_id": "category",
}


def validate_book(form, choice_ids):
    """form: the typed values. choice_ids: {"author_id": {1, 2, ...}, "publisher_id": ..., ...}"""
    errors = {}
    title, price, year = form["title"], form["price"], form["publish_year"]

    if title == "":
        errors["title"] = "Title is required"
    elif len(title) > 200:
        errors["title"] = "Title is too long (200 characters at most)"

    if price == "":
        errors["price"] = "Price is required"
    elif price.startswith("-"):
        errors["price"] = "Price cannot be negative"
    elif not PRICE_PATTERN.match(price):
        errors["price"] = "Enter a valid price, like 120 or 99.50"
    elif Decimal(price) >= MAX_PRICE:
        errors["price"] = "Price is too large (99999999.99 at most)"

    this_year = date.today().year
    if year == "":
        errors["publish_year"] = "Year is required"
    elif not YEAR_PATTERN.match(year):
        errors["publish_year"] = "Enter a valid year, like 1956"
    elif not MIN_YEAR <= int(year) <= this_year:
        errors["publish_year"] = f"Year must be between {MIN_YEAR} and {this_year}"

    for key, word in BOOK_CHOICES.items():
        value = form[key]
        if value == "":
            errors[key] = f"{word.capitalize()} is required"
        elif not value.isdigit() or int(value) not in choice_ids[key]:
            errors[key] = f"Choose an existing {word}"

    return errors


def validate_author(name, country):
    errors = {}

    if name == "":
        errors["name"] = "Name is required"
    elif len(name) > 100:
        errors["name"] = "Name is too long (100 characters at most)"

    if country == "":
        errors["country"] = "Country is required"
    elif len(country) > 50:
        errors["country"] = "Country is too long (50 characters at most)"

    return errors


# ---------------------------------------------------------------
# Images (bonus): book covers and author photos.
# The file is saved in static/uploads/<books|authors>/ under a random
# name, and only that name is stored in the database.
# ---------------------------------------------------------------

UPLOAD_DIRS = {
    "books": os.path.join(BASE_DIR, "static", "uploads", "books"),
    "authors": os.path.join(BASE_DIR, "static", "uploads", "authors"),
}
for folder in UPLOAD_DIRS.values():
    os.makedirs(folder, exist_ok=True)

MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_NAME = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif|webp)$")


def image_type(data):
    """Look at the first bytes of the file, not at its name."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def read_image(field_name):
    """Returns (image_or_None, error_or_None). An image is (bytes, extension)."""
    upload = request.files.get(field_name)
    if upload is None or upload.filename == "":
        return None, None  # no file chosen: the image is optional

    data = upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        return None, "The image is too large (2 MB at most)"

    extension = image_type(data)
    if extension is None:
        return None, "Choose a PNG, JPG, GIF or WEBP image"

    return (data, extension), None


def save_image(kind, image):
    data, extension = image
    file_name = f"{uuid.uuid4().hex}.{extension}"
    with open(os.path.join(UPLOAD_DIRS[kind], file_name), "wb") as file:
        file.write(data)
    return file_name


def delete_image(kind, file_name):
    # Only names we created ourselves, so nothing else can ever be deleted.
    if file_name and IMAGE_NAME.match(file_name):
        try:
            os.remove(os.path.join(UPLOAD_DIRS[kind], file_name))
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------

def log_in(user_id, name):
    session.clear()  # forget anything from before
    session["user_id"] = user_id
    session["name"] = name


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.after_request
def no_cache(response):
    # So the "Back" button after logout does not show a private page.
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------
# Register / login / logout
# ---------------------------------------------------------------

@app.route("/")
def home():
    return redirect(url_for("todos"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("todos"))

    if request.method == "GET":
        return render_template("register.html", errors={}, form={})

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    errors = validate_register(name, email, password, confirm_password)

    if not errors:  # only now do we touch the database
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)",
                    (email, name, hash_password(password)),
                )
                user_id = cur.lastrowid
            db.commit()
        except pymysql.err.IntegrityError as error:
            db.rollback()
            if error.args[0] != 1062:  # 1062 = duplicate entry (UNIQUE email)
                raise
            errors["email"] = "Email Already Exists"
        else:
            log_in(user_id, name)
            return redirect(url_for("todos"))  # redirect after POST: refresh is safe

    # Show the form again with the messages (never send the passwords back).
    return render_template("register.html", errors=errors, form={"name": name, "email": email})


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("todos"))

    if request.method == "GET":
        return render_template("login.html", errors={}, form={}, form_error=None)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    errors = validate_login(email, password)
    form_error = None

    if not errors:
        with get_db().cursor() as cur:
            cur.execute(
                "SELECT user_id, name, password_hash FROM users WHERE email = %s",
                (email,),
            )
            user = cur.fetchone()

        stored_hash = user["password_hash"] if user else DUMMY_HASH
        if password_matches(password, stored_hash) and user:
            log_in(user["user_id"], user["name"])
            return redirect(url_for("todos"))

        # Same message for a wrong e-mail and a wrong password.
        form_error = "Invalid email or password"

    return render_template("login.html", errors=errors, form={"email": email}, form_error=form_error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------
# The app page: one page with two tabs (To-Do and Library).
# The browser switches tabs without reloading (static/tabs.js);
# /todos and /library open the page on the matching tab.
# ---------------------------------------------------------------

FILTERS = ("all", "open", "done")
VIEWS = ("books", "authors")


def current_filter():
    """The filter and the search text come from the address (?status=open&q=milk)."""
    status = request.args.get("status", "all")
    if status not in FILTERS:
        status = "all"
    query = request.args.get("q", "").strip()[:200]
    return status, query


def keep_args():
    """Only the non-default values, so the address stays short."""
    status, query = current_filter()
    args = {}
    if status != "all":
        args["status"] = status
    if query:
        args["q"] = query
    return args


def list_url():
    """The list address with the same filter, so an action does not reset it."""
    return url_for("todos", **keep_args())


def library_url(view="books"):
    return url_for("library", view=None if view == "books" else view)


def current_view():
    view = request.args.get("view", "books")
    return view if view in VIEWS else "books"


def layout_context(active, view="books"):
    """What the top bar and the tabs need on every page."""
    return {
        "active": active,
        "name": session["name"],
        "todos_href": list_url(),
        "library_href": library_url(view),
        "explore_href": url_for("explore"),
    }


def load_todos(edit_error=None):
    with get_db().cursor() as cur:
        cur.execute(
            "SELECT todo_id, title, is_done, created_at FROM todos "
            "WHERE user_id = %s ORDER BY todo_id DESC",
            (session["user_id"],),
        )
        items = cur.fetchall()

    # Filter and search happen here, on this user's rows only,
    # so the SQL stays exactly the query from the lab.
    status, query = current_filter()
    shown = items
    if status == "open":
        shown = [item for item in shown if not item["is_done"]]
    elif status == "done":
        shown = [item for item in shown if item["is_done"]]
    if query:
        shown = [item for item in shown if query.lower() in item["title"].lower()]

    # When an edit failed, show what the user typed next to the message.
    if edit_error:
        for item in shown:
            if item["todo_id"] == edit_error["todo_id"]:
                item["title"] = edit_error["value"]

    return {
        "todos": shown,
        "total": len(items),
        "open_count": sum(1 for item in items if not item["is_done"]),
        "status": status,
        "q": query,
        "keep": keep_args(),
        "edit_error": edit_error,
    }


def fetch_authors():
    with get_library_db().cursor() as cur:
        cur.execute("SELECT author_id, name, country, photo FROM author ORDER BY author_id")
        return cur.fetchall()


def fetch_publishers():
    with get_library_db().cursor() as cur:
        cur.execute("SELECT publisher_id, name, country FROM publisher ORDER BY name")
        return cur.fetchall()


def fetch_categories():
    with get_library_db().cursor() as cur:
        cur.execute("SELECT category_id, name FROM category ORDER BY name")
        return cur.fetchall()


def book_choices():
    """The lists of the book form: authors, publishers, categories."""
    return {
        "authors": fetch_authors(),
        "publishers": fetch_publishers(),
        "categories": fetch_categories(),
    }


def choice_ids(choices):
    return {
        "author_id": {row["author_id"] for row in choices["authors"]},
        "publisher_id": {row["publisher_id"] for row in choices["publishers"]},
        "category_id": {row["category_id"] for row in choices["categories"]},
    }


def load_library():
    authors = fetch_authors()
    with get_library_db().cursor() as cur:
        cur.execute(
            "SELECT book_id, title, price, publish_year, author_id, cover "
            "FROM book ORDER BY book_id"
        )
        books = cur.fetchall()

    # No JOIN needed: the author names and the book counts are matched here.
    names = {author["author_id"]: author["name"] for author in authors}
    counts = {}
    for book in books:
        book["author_name"] = names.get(book["author_id"], "")
        counts[book["author_id"]] = counts.get(book["author_id"], 0) + 1
    for author in authors:
        author["book_count"] = counts.get(author["author_id"], 0)

    return {
        "books": books,
        "authors": authors,
        "publishers": fetch_publishers(),
        "categories": fetch_categories(),
    }


def render_app(active, view=None, edit_error=None, **extra):
    view = view or current_view()
    context = layout_context(active, view)
    context.update(load_todos(edit_error))
    context.update(load_library())
    context.update(
        view=view,
        add_error=None,
        add_value="",
        book_errors={},
        book_form={},
        author_errors={},
        author_form={},
    )
    context.update(extra)
    return render_template("app.html", **context)


@app.route("/todos")
@login_required
def todos():
    return render_app("todos")


@app.route("/library")
@login_required
def library():
    return render_app("library")


# ---------------------------------------------------------------
# To-do list (every query has AND user_id = %s, taken from the session)
# ---------------------------------------------------------------

@app.route("/todos/add", methods=["POST"])
@login_required
def add_todo():
    title, error = validate_title(request.form.get("title", ""))
    if error:
        return render_app("todos", add_error=error, add_value=request.form.get("title", ""))

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO todos (user_id, title) VALUES (%s, %s)",
            (session["user_id"], title),
        )
    db.commit()
    return redirect(list_url())


@app.route("/todos/<int:todo_id>/edit", methods=["POST"])
@login_required
def edit_todo(todo_id):
    raw_title = request.form.get("title", "")
    title, error = validate_title(raw_title)
    if error:
        return render_app(
            "todos", edit_error={"todo_id": todo_id, "message": error, "value": raw_title}
        )

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE todos SET title = %s WHERE todo_id = %s AND user_id = %s",
            (title, todo_id, session["user_id"]),
        )
    db.commit()
    return redirect(list_url())


@app.route("/todos/<int:todo_id>/toggle", methods=["POST"])
@login_required
def toggle_todo(todo_id):
    is_done = 1 if request.form.get("is_done") == "1" else 0

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE todos SET is_done = %s WHERE todo_id = %s AND user_id = %s",
            (is_done, todo_id, session["user_id"]),
        )
    db.commit()
    return redirect(list_url())


@app.route("/todos/<int:todo_id>/delete", methods=["POST"])
@login_required
def delete_todo(todo_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM todos WHERE todo_id = %s AND user_id = %s",
            (todo_id, session["user_id"]),
        )
    db.commit()
    return redirect(list_url())


# ---------------------------------------------------------------
# Library: books (F2.2 add, F2.3 edit, F2.4 remove)
# ---------------------------------------------------------------

BOOK_FIELDS = ("title", "price", "publish_year", "author_id", "publisher_id", "category_id")


def read_book_form():
    return {name: request.form.get(name, "").strip() for name in BOOK_FIELDS}


def fetch_book(book_id):
    with get_library_db().cursor() as cur:
        cur.execute(
            "SELECT book_id, title, price, publish_year, author_id, publisher_id, "
            "category_id, cover FROM book WHERE book_id = %s",
            (book_id,),
        )
        return cur.fetchone()


def foreign_key_errors(form):
    """After MySQL refused a book (1452: a list value was removed meanwhile),
    find which one is missing now."""
    errors = validate_book(form, choice_ids(book_choices()))
    return errors or {"author_id": "Choose an existing author"}


@app.route("/books/add", methods=["POST"])
@login_required
def add_book():
    form = read_book_form()
    errors = validate_book(form, choice_ids(book_choices()))
    image, image_error = read_image("cover")
    if image_error:
        errors["cover"] = image_error

    if errors:  # show the form again; the database is not touched
        return render_app("library", view="books", book_errors=errors, book_form=form)

    cover = save_image("books", image) if image else None
    db = get_library_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO book (title, price, publish_year, author_id, publisher_id, "
                "category_id, cover) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (form["title"], form["price"], form["publish_year"], form["author_id"],
                 form["publisher_id"], form["category_id"], cover),
            )
        db.commit()
    except pymysql.err.IntegrityError as error:
        db.rollback()
        delete_image("books", cover)
        if error.args[0] != 1452:  # 1452 = a parent row does not exist (foreign key)
            raise
        errors = foreign_key_errors(form)
        return render_app("library", view="books", book_errors=errors, book_form=form)

    flash(f"Added “{form['title']}”")
    return redirect(library_url("books"))


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = fetch_book(book_id)
    if book is None:
        abort(404)
    choices = book_choices()

    if request.method == "GET":
        form = {name: str(book[name]) for name in BOOK_FIELDS}
        form["price"] = f"{book['price']:.2f}"
        return render_template(
            "book_edit.html", book=book, form=form, errors={}, **choices,
            **layout_context("library"),
        )

    form = read_book_form()
    errors = validate_book(form, choice_ids(choices))
    image, image_error = read_image("cover")
    if image_error:
        errors["cover"] = image_error

    if errors:
        return render_template(
            "book_edit.html", book=book, form=form, errors=errors, **choices,
            **layout_context("library"),
        )

    cover = book["cover"]
    if image:
        cover = save_image("books", image)
    elif request.form.get("remove_cover") == "1":
        cover = None

    db = get_library_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE book SET title = %s, price = %s, publish_year = %s, author_id = %s, "
                "publisher_id = %s, category_id = %s, cover = %s WHERE book_id = %s",
                (form["title"], form["price"], form["publish_year"], form["author_id"],
                 form["publisher_id"], form["category_id"], cover, book_id),
            )
        db.commit()
    except pymysql.err.IntegrityError as error:
        db.rollback()
        if cover != book["cover"]:
            delete_image("books", cover)
        if error.args[0] != 1452:
            raise
        return render_template(
            "book_edit.html", book=book, form=form, errors=foreign_key_errors(form),
            **book_choices(), **layout_context("library"),
        )

    if cover != book["cover"]:
        delete_image("books", book["cover"])  # the old cover is not used any more
    flash(f"Saved “{form['title']}”")
    return redirect(library_url("books"))


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    book = fetch_book(book_id)
    if book is not None:
        db = get_library_db()
        with db.cursor() as cur:
            cur.execute("DELETE FROM book WHERE book_id = %s", (book_id,))
        db.commit()
        delete_image("books", book["cover"])
        flash(f"Removed “{book['title']}”")
    return redirect(library_url("books"))


# ---------------------------------------------------------------
# Library: authors (F2.2 add, F2.3 edit, F2.5 remove)
# ---------------------------------------------------------------

def read_author_form():
    return {
        "name": request.form.get("name", "").strip(),
        "country": request.form.get("country", "").strip(),
    }


def fetch_author(author_id):
    with get_library_db().cursor() as cur:
        cur.execute(
            "SELECT author_id, name, country, photo FROM author WHERE author_id = %s",
            (author_id,),
        )
        return cur.fetchone()


@app.route("/authors/add", methods=["POST"])
@login_required
def add_author():
    form = read_author_form()
    errors = validate_author(form["name"], form["country"])
    image, image_error = read_image("photo")
    if image_error:
        errors["photo"] = image_error

    if errors:
        return render_app("library", view="authors", author_errors=errors, author_form=form)

    photo = save_image("authors", image) if image else None
    db = get_library_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO author (name, country, photo) VALUES (%s, %s, %s)",
            (form["name"], form["country"], photo),
        )
    db.commit()
    flash(f"Added {form['name']}")
    return redirect(library_url("authors"))


@app.route("/authors/<int:author_id>/edit", methods=["GET", "POST"])
@login_required
def edit_author(author_id):
    author = fetch_author(author_id)
    if author is None:
        abort(404)

    if request.method == "GET":
        form = {"name": author["name"], "country": author["country"]}
        return render_template(
            "author_edit.html", author=author, form=form, errors={},
            **layout_context("library", "authors"),
        )

    form = read_author_form()
    errors = validate_author(form["name"], form["country"])
    image, image_error = read_image("photo")
    if image_error:
        errors["photo"] = image_error

    if errors:
        return render_template(
            "author_edit.html", author=author, form=form, errors=errors,
            **layout_context("library", "authors"),
        )

    photo = author["photo"]
    if image:
        photo = save_image("authors", image)
    elif request.form.get("remove_photo") == "1":
        photo = None

    db = get_library_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE author SET name = %s, country = %s, photo = %s WHERE author_id = %s",
            (form["name"], form["country"], photo, author_id),
        )
    db.commit()

    if photo != author["photo"]:
        delete_image("authors", author["photo"])
    flash(f"Saved {form['name']}")
    return redirect(library_url("authors"))


@app.route("/authors/<int:author_id>/delete", methods=["POST"])
@login_required
def delete_author(author_id):
    author = fetch_author(author_id)
    if author is not None:
        db = get_library_db()
        with db.cursor() as cur:
            # The covers of this author's books, to delete their files too.
            cur.execute("SELECT cover FROM book WHERE author_id = %s", (author_id,))
            covers = [row["cover"] for row in cur.fetchall()]
            # ON DELETE CASCADE removes the author's books in the same statement.
            cur.execute("DELETE FROM author WHERE author_id = %s", (author_id,))
        db.commit()

        delete_image("authors", author["photo"])
        for cover in covers:
            delete_image("books", cover)

        books = f"{len(covers)} book" + ("" if len(covers) == 1 else "s")
        flash(f"Removed {author['name']} and {books}")
    return redirect(library_url("authors"))


# ---------------------------------------------------------------
# Lab 4: the Explore tab (search queries, F2.1 to F2.6).
# The SQL here is the same as in problem2_Queries.sql; every page also
# shows its SQL under "Show the SQL".
# ---------------------------------------------------------------

def sql(text):
    """Write the queries indented in the code, show them without the indent."""
    return textwrap.dedent(text).strip()


EXPLORE_SECTIONS = [
    # (address, requirement, name in the menu)
    ("search", "F2.1", "Search"),
    ("catalogue", "F2.2", "Catalogue"),
    ("reports", "F2.3", "Reports"),
    ("loans", "F2.4", "Loans"),
    ("popular", "F2.5", "Most borrowed"),
    ("authors", "F2.6", "Authors"),
]

# F2.1 (bonus): a prepared statement, the values go in the ? placeholders.
SEARCH_SQL = sql("""
    SELECT b.book_id, b.title, b.price, b.publish_year, a.name AS author, c.name AS category
    FROM book b
    JOIN author a   ON b.author_id = a.author_id
    JOIN category c ON b.category_id = c.category_id
    WHERE b.title LIKE ?
      AND b.price BETWEEN ? AND ?
      AND (? = 0 OR b.category_id = ?)
    ORDER BY b.price ASC
""")

# One column of a result table: (key in the row, header, kind).
# kind: "text", "id", "money", "number", "date".
EXPLORE_QUERIES = {
    "catalogue": [
        {
            "code": "F2.2",
            "title": "All the books",
            "text": "Every book with the names of its author, publisher and category instead of the ids (three JOINs).",
            "sql": sql("""
                SELECT b.book_id, b.title, b.price, b.publish_year,
                       a.name AS author, p.name AS publisher, c.name AS category
                FROM book b
                JOIN author a    ON b.author_id = a.author_id
                JOIN publisher p ON b.publisher_id = p.publisher_id
                JOIN category c  ON b.category_id = c.category_id
                ORDER BY b.title
            """),
            "columns": [
                ("book_id", "ID", "id"), ("title", "Title", "text"), ("author", "Author", "text"),
                ("publisher", "Publisher", "text"), ("category", "Category", "text"),
                ("publish_year", "Year", "number"), ("price", "Price", "money"),
            ],
        },
    ],
    "reports": [
        {
            "code": "F2.3 (c)",
            "title": "The whole library",
            "text": "Aggregate functions over the whole book table (no GROUP BY: one result row).",
            "sql": sql("""
                SELECT COUNT(*) AS books, SUM(price) AS total_price, MIN(price) AS smallest_price,
                       MAX(price) AS largest_price
                FROM book
            """),
            "style": "stats",
            "columns": [
                ("books", "Books", "number"), ("total_price", "Total price", "money"),
                ("smallest_price", "Smallest price", "money"), ("largest_price", "Largest price", "money"),
            ],
        },
        {
            "code": "F2.3 (a)",
            "title": "Books per category",
            "text": "The number of books and the average price of each category (GROUP BY).",
            "sql": sql("""
                SELECT c.name AS category, COUNT(*) AS books, ROUND(AVG(b.price), 2) AS average_price
                FROM book b
                JOIN category c ON b.category_id = c.category_id
                GROUP BY c.category_id, c.name
                ORDER BY c.name
            """),
            "columns": [
                ("category", "Category", "text"), ("books", "Books", "number"),
                ("average_price", "Average price", "money"),
            ],
        },
        {
            "code": "F2.3 (b)",
            "title": "Authors with at least 2 books",
            "text": "The groups of one author are kept only when they have 2 books or more (HAVING).",
            "sql": sql("""
                SELECT a.author_id, a.name, COUNT(*) AS books
                FROM author a
                JOIN book b ON b.author_id = a.author_id
                GROUP BY a.author_id, a.name
                HAVING COUNT(*) >= 2
                ORDER BY books DESC, a.name
            """),
            "columns": [
                ("author_id", "ID", "id"), ("name", "Author", "text"), ("books", "Books", "number"),
            ],
        },
    ],
    "loans": [
        {
            "code": "F2.4 (a)",
            "title": "Loans not returned yet",
            "text": "The loans whose return_date IS NULL, with the book title and the member name.",
            "sql": sql("""
                SELECT l.loan_id, b.title, m.name AS member, l.loan_date
                FROM loan l
                JOIN book b   ON l.book_id = b.book_id
                JOIN member m ON l.member_id = m.member_id
                WHERE l.return_date IS NULL
                ORDER BY l.loan_date
            """),
            "columns": [
                ("loan_id", "Loan", "id"), ("title", "Book", "text"), ("member", "Member", "text"),
                ("loan_date", "Borrowed on", "date"),
            ],
        },
        {
            "code": "F2.4 (b)",
            "title": "Members who never borrowed a book",
            "text": "LEFT JOIN keeps every member; the ones with no loan have NULL in the loan columns.",
            "sql": sql("""
                SELECT m.member_id, m.name, m.email, m.join_date
                FROM member m
                LEFT JOIN loan l ON l.member_id = m.member_id
                WHERE l.loan_id IS NULL
                ORDER BY m.name
            """),
            "columns": [
                ("member_id", "ID", "id"), ("name", "Member", "text"), ("email", "Email", "text"),
                ("join_date", "Joined on", "date"),
            ],
        },
        {
            "code": "F2.4 (c)",
            "title": "Books that were never borrowed",
            "text": "The same idea for the books: LEFT JOIN loan, then keep the rows with no loan.",
            "sql": sql("""
                SELECT b.book_id, b.title, b.price
                FROM book b
                LEFT JOIN loan l ON l.book_id = b.book_id
                WHERE l.loan_id IS NULL
                ORDER BY b.title
            """),
            "columns": [
                ("book_id", "ID", "id"), ("title", "Title", "text"), ("price", "Price", "money"),
            ],
        },
    ],
    "popular": [
        {
            "code": "F2.5",
            "title": "The member with the most loans",
            "text": "Group the loans by member, sort by the count, keep the first row (LIMIT 1).",
            "sql": sql("""
                SELECT m.member_id, m.name, COUNT(*) AS loans
                FROM loan l
                JOIN member m ON l.member_id = m.member_id
                GROUP BY m.member_id, m.name
                ORDER BY loans DESC, m.name
                LIMIT 1
            """),
            "style": "stats",
            "columns": [("name", "Member", "text"), ("loans", "Loans", "number")],
        },
        {
            "code": "F2.5",
            "title": "The 3 most borrowed books",
            "text": "Group the loans by book, sort by the count, keep the first 3 rows (LIMIT 3).",
            "sql": sql("""
                SELECT b.book_id, b.title, COUNT(*) AS loans
                FROM loan l
                JOIN book b ON l.book_id = b.book_id
                GROUP BY b.book_id, b.title
                ORDER BY loans DESC, b.title
                LIMIT 3
            """),
            "style": "ranked",
            "columns": [
                ("book_id", "ID", "id"), ("title", "Title", "text"), ("loans", "Loans", "number"),
            ],
        },
    ],
    "authors": [
        {
            "code": "F2.6 (a)",
            "title": "Every author and the number of books",
            "text": "LEFT JOIN keeps the authors with no book; COUNT(b.book_id) gives them 0.",
            "sql": sql("""
                SELECT a.author_id, a.name, a.country, COUNT(b.book_id) AS books
                FROM author a
                LEFT JOIN book b ON b.author_id = a.author_id
                GROUP BY a.author_id, a.name, a.country
                ORDER BY books DESC, a.name
            """),
            "columns": [
                ("author_id", "ID", "id"), ("name", "Author", "text"), ("country", "Country", "text"),
                ("books", "Books", "number"),
            ],
        },
        {
            "code": "F2.6 (b)",
            "title": "Author and publisher from the same country",
            "text": "Join each book with its author and its publisher, keep the rows where the two countries are equal.",
            "sql": sql("""
                SELECT b.book_id, b.title, a.name AS author, p.name AS publisher, a.country
                FROM book b
                JOIN author a    ON b.author_id = a.author_id
                JOIN publisher p ON b.publisher_id = p.publisher_id
                WHERE a.country = p.country
                ORDER BY b.title
            """),
            "columns": [
                ("book_id", "ID", "id"), ("title", "Title", "text"), ("author", "Author", "text"),
                ("publisher", "Publisher", "text"), ("country", "Country", "text"),
            ],
        },
    ],
}


def run_queries(section):
    blocks = []
    with get_library_db().cursor() as cur:
        for query in EXPLORE_QUERIES[section]:
            cur.execute(query["sql"])
            blocks.append(dict(query, rows=cur.fetchall()))
    return blocks


def read_price(raw, label, errors, key):
    """An optional price of the search form: None when empty."""
    if raw == "":
        return None
    if raw.startswith("-"):
        errors[key] = f"The {label} price cannot be negative"
    elif not PRICE_PATTERN.match(raw):
        errors[key] = "Enter a valid price, like 15 or 19.99"
    else:
        try:
            value = Decimal(raw)
        except InvalidOperation:
            value = None
        if value is not None and value < MAX_PRICE:
            return value
        errors[key] = "Price is too large (99999999.99 at most)"
    return None


def search_books():
    """F2.1: read the form (from the address, GET), check it, run the search."""
    form = {
        "q": request.args.get("q", "").strip(),
        "min_price": request.args.get("min_price", "").strip(),
        "max_price": request.args.get("max_price", "").strip(),
        "category_id": request.args.get("category_id", "").strip(),
    }
    categories = fetch_categories()
    errors = {}

    if len(form["q"]) > 200:
        errors["q"] = "The keyword is too long (200 characters at most)"

    low = read_price(form["min_price"], "minimum", errors, "min_price")
    high = read_price(form["max_price"], "maximum", errors, "max_price")
    if low is not None and high is not None and low > high:
        errors["max_price"] = "The maximum must be at least the minimum"

    category = 0  # 0 = all the categories
    if form["category_id"] != "":
        ids = {row["category_id"] for row in categories}
        if form["category_id"].isdigit() and int(form["category_id"]) in ids:
            category = int(form["category_id"])
        else:
            errors["category_id"] = "Choose an existing category"

    results = None
    if not errors:
        # % and _ are wildcards of LIKE: a typed "%" must only match a "%".
        keyword = form["q"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params = (
            f"%{keyword}%",
            low if low is not None else Decimal("0"),
            high if high is not None else MAX_PRICE - Decimal("0.01"),
            category,
            category,
        )
        results = run_prepared(SEARCH_SQL, params)

    return {
        "form": form,
        "errors": errors,
        "categories": categories,
        "results": results,
        "searched": any(form.values()),
        "search_sql": SEARCH_SQL,
    }


@app.route("/explore")
@app.route("/explore/<section>")
@login_required
def explore(section="search"):
    if section not in {key for key, _code, _name in EXPLORE_SECTIONS}:
        abort(404)

    context = layout_context("explore")
    context.update(section=section, sections=EXPLORE_SECTIONS)
    if section == "search":
        context.update(search_books())
    else:
        context["blocks"] = run_queries(section)
    return render_template("explore.html", **context)


# ---------------------------------------------------------------
# Friendly error pages (no stack traces)
# ---------------------------------------------------------------

@app.errorhandler(404)
def not_found(_error):
    return render_template(
        "error.html", code=404, message="We could not find that page."
    ), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return render_template(
        "error.html", code=405, message="That action is not allowed here."
    ), 405


@app.errorhandler(413)
def too_large(_error):
    return render_template(
        "error.html", code=413, message="That file is too large. Images can be 2 MB at most."
    ), 413


@app.errorhandler(500)
def server_error(_error):
    return render_template(
        "error.html", code=500, message="Something went wrong on our side. Please try again."
    ), 500


if __name__ == "__main__":
    app.run(debug=False)
