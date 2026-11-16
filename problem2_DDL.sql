-- Lab 4, Problem 2: the LIBRARY database (DDL)
-- Re-runnable: it deletes the database and builds it again.
--
--   AUTHOR    (author_id, name, country)
--   PUBLISHER (publisher_id, name, country)
--   CATEGORY  (category_id, name)
--   BOOK      (book_id, title, price, publish_year, author_id, publisher_id, category_id)
--   MEMBER    (member_id, name, email, join_date)
--   LOAN      (loan_id, book_id, member_id, loan_date, return_date)
--
-- Foreign keys:
--   BOOK.author_id    -> AUTHOR.author_id        ON DELETE CASCADE (an author's books go with the author)
--   BOOK.publisher_id -> PUBLISHER.publisher_id
--   BOOK.category_id  -> CATEGORY.category_id
--   LOAN.book_id      -> BOOK.book_id            ON DELETE CASCADE (a book's loans go with the book)
--   LOAN.member_id    -> MEMBER.member_id
--
-- return_date is NULL while the book is still borrowed.
-- photo and cover are kept from the Lab 3 bonus: the file name of an uploaded
-- image (NULL when there is none). The images themselves are files on the server.
--
-- Order: a table can only point at a table that already exists, so the
-- parents (author, publisher, category, member) are created before book and loan.

DROP DATABASE IF EXISTS library;
CREATE DATABASE library;
USE library;

CREATE TABLE author (
    author_id INT           NOT NULL AUTO_INCREMENT,
    name      VARCHAR(100)  NOT NULL,
    country   VARCHAR(50)   NOT NULL,
    photo     VARCHAR(255),              -- Lab 3 bonus: photo of the author
    PRIMARY KEY (author_id)
);

CREATE TABLE publisher (
    publisher_id INT          NOT NULL AUTO_INCREMENT,
    name         VARCHAR(100) NOT NULL,
    country      VARCHAR(50)  NOT NULL,
    PRIMARY KEY (publisher_id)
);

CREATE TABLE category (
    category_id INT         NOT NULL AUTO_INCREMENT,
    name        VARCHAR(50) NOT NULL,
    PRIMARY KEY (category_id),
    UNIQUE (name)
);

CREATE TABLE book (
    book_id      INT           NOT NULL AUTO_INCREMENT,
    title        VARCHAR(200)  NOT NULL,
    price        DECIMAL(10,2) NOT NULL,
    publish_year SMALLINT      NOT NULL,
    author_id    INT           NOT NULL,   -- every book has exactly one author
    publisher_id INT           NOT NULL,
    category_id  INT           NOT NULL,
    cover        VARCHAR(255),             -- Lab 3 bonus: cover of the book
    PRIMARY KEY (book_id),
    CHECK (price >= 0),
    FOREIGN KEY (author_id)    REFERENCES author (author_id) ON DELETE CASCADE,
    FOREIGN KEY (publisher_id) REFERENCES publisher (publisher_id),
    FOREIGN KEY (category_id)  REFERENCES category (category_id)
);

CREATE TABLE member (
    member_id INT          NOT NULL AUTO_INCREMENT,
    name      VARCHAR(100) NOT NULL,
    email     VARCHAR(255) NOT NULL,
    join_date DATE         NOT NULL,
    PRIMARY KEY (member_id),
    UNIQUE (email)
);

CREATE TABLE loan (
    loan_id     INT  NOT NULL AUTO_INCREMENT,
    book_id     INT  NOT NULL,
    member_id   INT  NOT NULL,
    loan_date   DATE NOT NULL,
    return_date DATE,                      -- NULL: the book is still borrowed
    PRIMARY KEY (loan_id),
    CHECK (return_date IS NULL OR return_date >= loan_date),
    FOREIGN KEY (book_id)   REFERENCES book (book_id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES member (member_id)
);
