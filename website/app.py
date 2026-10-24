import os
import re
import uuid
from decimal import Decimal
from functools import wraps

import bcrypt
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


def validate_book(title, price, author_id, author_ids):
    errors = {}

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

    if author_id == "":
        errors["author_id"] = "Author is required"
    elif not author_id.isdigit() or int(author_id) not in author_ids:
        errors["author_id"] = "Choose an existing author"

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


def load_library():
    authors = fetch_authors()
    with get_library_db().cursor() as cur:
        cur.execute("SELECT book_id, title, price, author_id, cover FROM book ORDER BY book_id")
        books = cur.fetchall()

    # No JOIN needed: the author names and the book counts are matched here.
    names = {author["author_id"]: author["name"] for author in authors}
    counts = {}
    for book in books:
        book["author_name"] = names.get(book["author_id"], "")
        counts[book["author_id"]] = counts.get(book["author_id"], 0) + 1
    for author in authors:
        author["book_count"] = counts.get(author["author_id"], 0)

    return {"books": books, "authors": authors}


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

def read_book_form():
    return {
        "title": request.form.get("title", "").strip(),
        "price": request.form.get("price", "").strip(),
        "author_id": request.form.get("author_id", "").strip(),
    }


def fetch_book(book_id):
    with get_library_db().cursor() as cur:
        cur.execute(
            "SELECT book_id, title, price, author_id, cover FROM book WHERE book_id = %s",
            (book_id,),
        )
        return cur.fetchone()


@app.route("/books/add", methods=["POST"])
@login_required
def add_book():
    form = read_book_form()
    author_ids = {author["author_id"] for author in fetch_authors()}
    errors = validate_book(form["title"], form["price"], form["author_id"], author_ids)
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
                "INSERT INTO book (title, price, author_id, cover) VALUES (%s, %s, %s, %s)",
                (form["title"], form["price"], form["author_id"], cover),
            )
        db.commit()
    except pymysql.err.IntegrityError as error:
        db.rollback()
        delete_image("books", cover)
        if error.args[0] != 1452:  # 1452 = the author does not exist (foreign key)
            raise
        errors["author_id"] = "Choose an existing author"
        return render_app("library", view="books", book_errors=errors, book_form=form)

    flash(f"Added “{form['title']}”")
    return redirect(library_url("books"))


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = fetch_book(book_id)
    if book is None:
        abort(404)
    authors = fetch_authors()

    if request.method == "GET":
        form = {
            "title": book["title"],
            "price": f"{book['price']:.2f}",
            "author_id": str(book["author_id"]),
        }
        return render_template(
            "book_edit.html", book=book, form=form, errors={}, authors=authors,
            **layout_context("library"),
        )

    form = read_book_form()
    author_ids = {author["author_id"] for author in authors}
    errors = validate_book(form["title"], form["price"], form["author_id"], author_ids)
    image, image_error = read_image("cover")
    if image_error:
        errors["cover"] = image_error

    if errors:
        return render_template(
            "book_edit.html", book=book, form=form, errors=errors, authors=authors,
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
                "UPDATE book SET title = %s, price = %s, author_id = %s, cover = %s "
                "WHERE book_id = %s",
                (form["title"], form["price"], form["author_id"], cover, book_id),
            )
        db.commit()
    except pymysql.err.IntegrityError as error:
        db.rollback()
        if cover != book["cover"]:
            delete_image("books", cover)
        if error.args[0] != 1452:
            raise
        errors["author_id"] = "Choose an existing author"
        return render_template(
            "book_edit.html", book=book, form=form, errors=errors, authors=authors,
            **layout_context("library"),
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
