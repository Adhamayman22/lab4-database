-- Lab 3, Problem 2: the LIBRARY database (seed data)
-- Run problem2_DDL.sql first.
-- Authors come first: a book can only point at an author that exists.
-- The ids are written explicitly so the data is the same on every machine.

USE library;

INSERT INTO author (author_id, name, country) VALUES
    (1, 'Naguib Mahfouz',         'Egypt'),
    (2, 'Taha Hussein',           'Egypt'),
    (3, 'George Orwell',          'United Kingdom'),
    (4, 'Gabriel Garcia Marquez', 'Colombia');

INSERT INTO book (book_id, title, price, author_id) VALUES
    (1, 'Palace Walk',                        180.00, 1),
    (2, 'Children of the Alley',              150.00, 1),
    (3, 'The Thief and the Dogs',              95.50, 1),
    (4, 'The Days',                           120.00, 2),
    (5, 'The Call of the Curlew',             110.00, 2),
    (6, 'Nineteen Eighty-Four',               210.00, 3),
    (7, 'Animal Farm',                        135.00, 3),
    (8, 'One Hundred Years of Solitude',      250.00, 4);
