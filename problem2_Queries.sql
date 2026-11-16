-- Lab 4, Problem 2: the SQL of every new page of the website (F2.1 to F2.6).
-- Run problem2_DDL.sql and problem2_DML.sql first, then:
--     mysql -u root -p < problem2_Queries.sql
-- (or open this file in MySQL Workbench and press the lightning button).
--
-- The website runs exactly these queries (see the *_SQL constants in website/app.py).
-- Where the page takes values from a form, this file uses example values.

USE library;


-- F2.1 Search books (WHERE)
-- A title keyword (LIKE), a minimum and a maximum price (BETWEEN) and a category;
-- the matching books, cheapest first.
-- Example: titles containing "the", priced from 10 to 20, in the category Novel (1).
SELECT b.book_id, b.title, b.price, b.publish_year, a.name AS author, c.name AS category
FROM book b
JOIN author a   ON b.author_id = a.author_id
JOIN category c ON b.category_id = c.category_id
WHERE b.title LIKE '%the%'
  AND b.price BETWEEN 10 AND 20
  AND b.category_id = 1
ORDER BY b.price ASC;

-- F2.1 (bonus) The same search as a prepared statement with placeholders (?).
-- The text of the statement never contains what the user typed: the values are
-- sent separately and MySQL only ever treats them as values.
-- (The website does the same through the binary protocol of MySQL, with
--  mysql-connector-python and cursor(prepared=True).)
-- A category of 0 means "all categories"; an empty keyword matches every title.
PREPARE search_books FROM
    'SELECT b.book_id, b.title, b.price, b.publish_year, a.name AS author, c.name AS category
     FROM book b
     JOIN author a   ON b.author_id = a.author_id
     JOIN category c ON b.category_id = c.category_id
     WHERE b.title LIKE ?
       AND b.price BETWEEN ? AND ?
       AND (? = 0 OR b.category_id = ?)
     ORDER BY b.price ASC';
SET @keyword = '%the%', @min_price = 10, @max_price = 20, @category_id = 1;
EXECUTE search_books USING @keyword, @min_price, @max_price, @category_id, @category_id;
SET @keyword = '%%', @min_price = 15, @max_price = 20, @category_id = 0;
EXECUTE search_books USING @keyword, @min_price, @max_price, @category_id, @category_id;
DEALLOCATE PREPARE search_books;


-- F2.2 Catalogue (JOIN)
-- Every book with the author name, the publisher name and the category name instead of the ids.
SELECT b.book_id, b.title, b.price, b.publish_year,
       a.name AS author, p.name AS publisher, c.name AS category
FROM book b
JOIN author a    ON b.author_id = a.author_id
JOIN publisher p ON b.publisher_id = p.publisher_id
JOIN category c  ON b.category_id = c.category_id
ORDER BY b.title;


-- F2.3 Reports (GROUP BY, HAVING)
-- (a) The number of books and the average price of each category.
SELECT c.name AS category, COUNT(*) AS books, ROUND(AVG(b.price), 2) AS average_price
FROM book b
JOIN category c ON b.category_id = c.category_id
GROUP BY c.category_id, c.name
ORDER BY c.name;

-- (b) The authors who wrote at least 2 books.
SELECT a.author_id, a.name, COUNT(*) AS books
FROM author a
JOIN book b ON b.author_id = a.author_id
GROUP BY a.author_id, a.name
HAVING COUNT(*) >= 2
ORDER BY books DESC, a.name;

-- (c) The total, smallest and largest price of the whole library (and the number of books).
SELECT COUNT(*) AS books, SUM(price) AS total_price, MIN(price) AS smallest_price,
       MAX(price) AS largest_price
FROM book;


-- F2.4 Loans (JOIN, LEFT JOIN)
-- (a) The loans not returned yet, with the book title and the member name.
SELECT l.loan_id, b.title, m.name AS member, l.loan_date
FROM loan l
JOIN book b   ON l.book_id = b.book_id
JOIN member m ON l.member_id = m.member_id
WHERE l.return_date IS NULL
ORDER BY l.loan_date;

-- (b) The members who never borrowed a book.
SELECT m.member_id, m.name, m.email, m.join_date
FROM member m
LEFT JOIN loan l ON l.member_id = m.member_id
WHERE l.loan_id IS NULL
ORDER BY m.name;

-- (c) The books that were never borrowed.
SELECT b.book_id, b.title, b.price
FROM book b
LEFT JOIN loan l ON l.book_id = b.book_id
WHERE l.loan_id IS NULL
ORDER BY b.title;


-- F2.5 Most borrowed (GROUP BY, ORDER BY, LIMIT)
-- The 3 books with the most loans.
SELECT b.book_id, b.title, COUNT(*) AS loans
FROM loan l
JOIN book b ON l.book_id = b.book_id
GROUP BY b.book_id, b.title
ORDER BY loans DESC, b.title
LIMIT 3;

-- The member with the most loans.
SELECT m.member_id, m.name, COUNT(*) AS loans
FROM loan l
JOIN member m ON l.member_id = m.member_id
GROUP BY m.member_id, m.name
ORDER BY loans DESC, m.name
LIMIT 1;


-- F2.6 Authors and books (LEFT JOIN, JOIN)
-- (a) Every author with the number of books he or she wrote, including the authors who wrote 0.
--     COUNT(b.book_id) counts only the rows where a book was found, so an author with no book gets 0.
SELECT a.author_id, a.name, a.country, COUNT(b.book_id) AS books
FROM author a
LEFT JOIN book b ON b.author_id = a.author_id
GROUP BY a.author_id, a.name, a.country
ORDER BY books DESC, a.name;

-- (b) The books whose author and publisher come from the same country.
SELECT b.book_id, b.title, a.name AS author, p.name AS publisher, a.country
FROM book b
JOIN author a    ON b.author_id = a.author_id
JOIN publisher p ON b.publisher_id = p.publisher_id
WHERE a.country = p.country
ORDER BY b.title;
