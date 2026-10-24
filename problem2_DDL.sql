-- Lab 3, Problem 2: the LIBRARY database (DDL)
-- Re-runnable: it deletes the database and builds it again.
--
--   AUTHOR (author_id, name, country)
--   BOOK   (book_id, title, price, author_id)
--
-- Foreign key: BOOK.author_id -> AUTHOR.author_id.
-- When an author is deleted, all the books of that author are deleted too
-- (ON DELETE CASCADE).
--
-- photo and cover are for the bonus: the file name of an uploaded image
-- (NULL when there is none). The images themselves are files on the server.

DROP DATABASE IF EXISTS library;
CREATE DATABASE library;
USE library;

CREATE TABLE author (
    author_id INT           NOT NULL AUTO_INCREMENT,
    name      VARCHAR(100)  NOT NULL,
    country   VARCHAR(50)   NOT NULL,
    photo     VARCHAR(255),              -- bonus: photo of the author
    PRIMARY KEY (author_id)
);

CREATE TABLE book (
    book_id   INT           NOT NULL AUTO_INCREMENT,
    title     VARCHAR(200)  NOT NULL,
    price     DECIMAL(10,2) NOT NULL,
    author_id INT           NOT NULL,    -- every book has exactly one author
    cover     VARCHAR(255),              -- bonus: cover of the book
    PRIMARY KEY (book_id),
    FOREIGN KEY (author_id) REFERENCES author (author_id) ON DELETE CASCADE
);
