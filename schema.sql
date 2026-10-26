-- ==========================================================
-- SMART LOST & FOUND SYSTEM FOR CAMPUS
-- MySQL Database Schema
-- Database Name: campus_lost_found
-- ==========================================================

CREATE DATABASE IF NOT EXISTS campus_lost_found CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campus_lost_found;

-- Disable foreign key checks for clean recreation
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS smart_matches;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS item_returns;
DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------------------------------------
-- Table: users
-- ----------------------------------------------------------
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    student_id VARCHAR(50) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'admin') DEFAULT 'student',
    department VARCHAR(100) DEFAULT 'Computer Science',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- Table: categories
-- ----------------------------------------------------------
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    icon VARCHAR(50) DEFAULT 'bi-box-seam',
    description VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- Table: items
-- ----------------------------------------------------------
CREATE TABLE items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    item_type ENUM('lost', 'found') NOT NULL,
    title VARCHAR(150) NOT NULL,
    category_id INT NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(150) NOT NULL,
    event_date DATE NOT NULL,
    primary_color VARCHAR(50) DEFAULT 'Unknown',
    brand VARCHAR(100) DEFAULT 'Unknown',
    image_filename VARCHAR(255) DEFAULT 'default_item.png',
    storage_location VARCHAR(255) DEFAULT NULL,
    status ENUM('open', 'claimed', 'returned', 'closed') DEFAULT 'open',
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_items_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_items_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- Table: claims
-- ----------------------------------------------------------
CREATE TABLE claims (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    claimant_id INT NOT NULL,
    proof_description TEXT NOT NULL,
    proof_image VARCHAR(255) DEFAULT NULL,
    contact_number VARCHAR(20) NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    admin_notes TEXT DEFAULT NULL,
    reviewed_by INT DEFAULT NULL,
    reviewed_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_claims_item FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    CONSTRAINT fk_claims_claimant FOREIGN KEY (claimant_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_claims_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- Table: item_returns
-- ----------------------------------------------------------
CREATE TABLE item_returns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL UNIQUE,
    claim_id INT NOT NULL,
    owner_id INT NOT NULL,
    handed_over_by INT NOT NULL,
    receipt_token VARCHAR(64) NOT NULL UNIQUE,
    returned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verification_method VARCHAR(100) DEFAULT 'Student ID & Physical Verification',
    remarks TEXT DEFAULT NULL,
    CONSTRAINT fk_returns_item FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    CONSTRAINT fk_returns_claim FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
    CONSTRAINT fk_returns_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_returns_admin FOREIGN KEY (handed_over_by) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- Table: notifications
-- ----------------------------------------------------------
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    link VARCHAR(255) DEFAULT '#',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- Table: smart_matches
-- ----------------------------------------------------------
CREATE TABLE smart_matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lost_item_id INT NOT NULL,
    found_item_id INT NOT NULL,
    similarity_score DECIMAL(5,2) NOT NULL,
    match_breakdown TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_matches_lost FOREIGN KEY (lost_item_id) REFERENCES items(id) ON DELETE CASCADE,
    CONSTRAINT fk_matches_found FOREIGN KEY (found_item_id) REFERENCES items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- Seed Initial Data
-- ----------------------------------------------------------
INSERT INTO categories (name, icon, description) VALUES
('Electronics & Gadgets', 'bi-laptop', 'Laptops, mobile phones, chargers, headphones, calculators, USB drives'),
('ID Cards & Documents', 'bi-person-badge', 'Campus ID cards, driver licenses, ATM cards, notebooks, certificates'),
('Bags & Wallets', 'bi-bag', 'Backpacks, handbags, purses, wallets, pouches'),
('Keys & Access Cards', 'bi-key', 'Room keys, bike/car keys, hostel keychains, RFID tags'),
('Books & Study Material', 'bi-book', 'Textbooks, lab manuals, assignment notebooks, binders'),
('Clothing & Accessories', 'bi-eyeglasses', 'Jackets, hoodies, caps, watches, spectacles, sunglasses, water bottles'),
('Other Items', 'bi-box', 'Sports equipment, umbrellas, musical instruments, miscellaneous items');

-- Initial System Administrator Account
-- Username: admin / Email: admin@campus.edu / Password: ADMIN@123
INSERT INTO users (full_name, email, student_id, phone, password_hash, role, department) VALUES
('Campus Security Administrator', 'admin@campus.edu', 'ADMIN', '9876543210', 'scrypt:32768:8:1$o17r0zoye7ylY3jp$3351af1e8f4115f13492768a333a6b8b8fef6eae1984d43805590da38bff65f7dfa0959c1af5fc4309647dcb7e94f31c15c7fc785c4b106486978b9245bdb2d5', 'admin', 'Campus Security Office');
