-- Lab 4, Problem 2: the LIBRARY database (seed data)
-- Run problem2_DDL.sql first.
-- Parents come first (author, publisher, category, member), then book, then loan:
-- a row can only point at a row that already exists.
-- The ids are written explicitly so the data is the same on every machine.
--
-- What the data contains (the lab's checklist):
--   two authors from the same country ........ Naguib Mahfouz and Taha Hussein (Egypt)
--   an author with no books .................. Chinua Achebe (5)
--   an author who wrote at least 2 books ...... Mahfouz (4), Orwell (3), Garcia Marquez (3), Hussein (2)
--   an author and a publisher, same country ... Mahfouz / Hussein + Dar El Shorouk (Egypt);
--                                                Orwell + Penguin Books (United Kingdom)
--   a book priced between 15 and 20 ........... Palace Walk 18.50, Children of the Alley 16.00, ...
--   a book that was never borrowed ............ books 11 and 12
--   a member with no loans .................... Nour Hassan (6)
--   a loan that is not returned yet ........... loans 4, 7, 13, 14, 16 (return_date IS NULL)

USE library;

INSERT INTO author (author_id, name, country) VALUES
    (1, 'Naguib Mahfouz',         'Egypt'),
    (2, 'Taha Hussein',           'Egypt'),
    (3, 'George Orwell',          'United Kingdom'),
    (4, 'Gabriel Garcia Marquez', 'Colombia'),
    (5, 'Chinua Achebe',          'Nigeria');

INSERT INTO publisher (publisher_id, name, country) VALUES
    (1, 'Dar El Shorouk', 'Egypt'),
    (2, 'Penguin Books',  'United Kingdom'),
    (3, 'Vintage Books',  'United States');

INSERT INTO category (category_id, name) VALUES
    (1, 'Novel'),
    (2, 'Autobiography'),
    (3, 'Dystopia'),
    (4, 'Poetry');

INSERT INTO book (book_id, title, price, publish_year, author_id, publisher_id, category_id) VALUES
    ( 1, 'Palace Walk',                      18.50, 1956, 1, 1, 1),
    ( 2, 'Children of the Alley',            16.00, 1959, 1, 1, 1),
    ( 3, 'The Thief and the Dogs',           12.75, 1961, 1, 2, 1),
    ( 4, 'The Days',                         14.00, 1929, 2, 1, 2),
    ( 5, 'The Call of the Curlew',           13.50, 1934, 2, 1, 1),
    ( 6, 'Nineteen Eighty-Four',             22.00, 1949, 3, 2, 3),
    ( 7, 'Animal Farm',                      15.00, 1945, 3, 2, 3),
    ( 8, 'One Hundred Years of Solitude',    25.00, 1967, 4, 3, 1),
    ( 9, 'Love in the Time of Cholera',      21.50, 1985, 4, 3, 1),
    (10, 'Sugar Street',                     19.99, 1957, 1, 1, 1),
    (11, 'Down and Out in Paris and London', 17.25, 1933, 3, 2, 2),
    (12, 'Chronicle of a Death Foretold',    11.00, 1981, 4, 3, 1);

INSERT INTO member (member_id, name, email, join_date) VALUES
    (1, 'Omar Khaled',  'omar.khaled@example.com',  '2025-02-10'),
    (2, 'Mona Adel',    'mona.adel@example.com',    '2025-03-22'),
    (3, 'Youssef Hany', 'youssef.hany@example.com', '2025-06-05'),
    (4, 'Salma Tarek',  'salma.tarek@example.com',  '2025-09-18'),
    (5, 'Karim Nabil',  'karim.nabil@example.com',  '2026-01-07'),
    (6, 'Nour Hassan',  'nour.hassan@example.com',  '2026-08-30');

INSERT INTO loan (loan_id, book_id, member_id, loan_date, return_date) VALUES
    ( 1,  6, 1, '2026-09-01', '2026-09-15'),
    ( 2,  6, 2, '2026-09-03', '2026-09-20'),
    ( 3,  6, 3, '2026-09-25', '2026-10-05'),
    ( 4,  6, 4, '2026-10-10', NULL),
    ( 5,  1, 2, '2026-09-05', '2026-09-19'),
    ( 6,  1, 5, '2026-09-22', '2026-10-02'),
    ( 7,  1, 1, '2026-10-20', NULL),
    ( 8,  8, 2, '2026-09-10', '2026-09-30'),
    ( 9,  8, 3, '2026-10-12', '2026-10-26'),
    (10,  2, 4, '2026-09-14', '2026-09-28'),
    (11,  4, 2, '2026-10-01', '2026-10-15'),
    (12,  7, 5, '2026-10-03', '2026-10-17'),
    (13,  9, 2, '2026-10-28', NULL),
    (14,  3, 3, '2026-11-02', NULL),
    (15,  5, 1, '2026-11-05', '2026-11-12'),
    (16, 10, 4, '2026-11-08', NULL);
