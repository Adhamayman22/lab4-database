-- Lab 3, Problem 1: the COMPANY database (DML)
-- Run problem1_DDL.sql first.
--
-- The order matters because of the foreign keys:
--   1. employees, still without a department (Dno is NULL)
--   2. departments, each managed by an employee that now exists
--   3. give every employee a department that now exists
--   4. projects, each controlled by an existing department

USE company;

-- 1. Employees
INSERT INTO employee (ssn, fname, lname, bdate, address, gender, salary, Dno) VALUES
    ('123456789', 'Ahmed',   'Hassan',  '1985-03-12', '12 El-Horreya Rd, Alexandria', 'M', 25000.00, NULL),
    ('234567891', 'Mona',    'Ali',     '1990-07-25', '5 Fouad St, Alexandria',       'F', 18000.00, NULL),
    ('345678912', 'Omar',    'Khaled',  '1988-11-02', '30 Sporting St, Alexandria',   'M', 21000.00, NULL),
    ('456789123', 'Sara',    'Mahmoud', '1995-01-30', '8 Smouha St, Alexandria',      'F', 15000.00, NULL),
    ('567891234', 'Youssef', 'Adel',    '1992-05-18', '14 Miami St, Alexandria',      'M', 16500.00, NULL),
    ('678912345', 'Nour',    'Samir',   '1997-09-09', '22 Sidi Gaber, Alexandria',    'F', 14000.00, NULL);

-- 2. Departments
INSERT INTO department (Dnumber, Dname, mgr_ssn, mgr_start_date) VALUES
    (1, 'Research',       '123456789', '2018-01-01'),
    (2, 'Administration', '234567891', '2020-06-15'),
    (3, 'Headquarters',   '345678912', '2015-09-01');

-- 3. Every employee works for a department
UPDATE employee SET Dno = 1 WHERE ssn IN ('123456789', '456789123');
UPDATE employee SET Dno = 2 WHERE ssn IN ('234567891', '678912345');
UPDATE employee SET Dno = 3 WHERE ssn IN ('345678912', '567891234');

-- 4. Projects
INSERT INTO project (Pnumber, Pname, Plocation, Dno) VALUES
    (10, 'ProductX',        'Alexandria', 1),
    (20, 'ProductY',        'Cairo',      1),
    (30, 'Computerization', 'Alexandria', 2),
    (40, 'Reorganization',  'Giza',       3);
