-- Lab 3, Problem 1: the COMPANY database (DDL)
-- Re-runnable: it deletes the database and builds it again.
--
--   EMPLOYEE   (ssn, fname, lname, bdate, address, gender, salary, Dno)
--   DEPARTMENT (Dnumber, Dname, mgr_ssn, mgr_start_date)
--   PROJECT    (Pnumber, Pname, Plocation, Dno)
--
-- Foreign keys:
--   EMPLOYEE.Dno     -> DEPARTMENT.Dnumber
--   PROJECT.Dno      -> DEPARTMENT.Dnumber
--   DEPARTMENT.mgr_ssn -> EMPLOYEE.ssn
--
-- EMPLOYEE and DEPARTMENT point at each other (a cycle). A table can only
-- point at a table that already exists, so EMPLOYEE is created first without
-- its foreign key, and the key is added at the end with ALTER TABLE.

DROP DATABASE IF EXISTS company;
CREATE DATABASE company;
USE company;

CREATE TABLE employee (
    ssn      CHAR(9)       NOT NULL,   -- always 9 digits, kept as text
    fname    VARCHAR(30)   NOT NULL,
    lname    VARCHAR(30)   NOT NULL,
    bdate    DATE,
    address  VARCHAR(100),
    gender   CHAR(1),                  -- 'M' or 'F'
    salary   DECIMAL(10,2),
    Dno      INT,                      -- the department the employee works for
    PRIMARY KEY (ssn)
);

CREATE TABLE department (
    Dnumber        INT          NOT NULL,
    Dname          VARCHAR(30)  NOT NULL,
    mgr_ssn        CHAR(9),             -- the employee who manages it
    mgr_start_date DATE,
    PRIMARY KEY (Dnumber),
    UNIQUE (Dname),
    FOREIGN KEY (mgr_ssn) REFERENCES employee (ssn)
);

CREATE TABLE project (
    Pnumber   INT          NOT NULL,
    Pname     VARCHAR(30)  NOT NULL,
    Plocation VARCHAR(30),
    Dno       INT,                      -- the department that controls it
    PRIMARY KEY (Pnumber),
    UNIQUE (Pname),
    FOREIGN KEY (Dno) REFERENCES department (Dnumber)
);

-- Now that DEPARTMENT exists, EMPLOYEE can point at it.
ALTER TABLE employee ADD FOREIGN KEY (Dno) REFERENCES department (Dnumber);
