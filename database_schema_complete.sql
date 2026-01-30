-- Complete Database Schema for Advanced Fraud Detection System
-- Run this in MySQL Workbench

CREATE DATABASE IF NOT EXISTS fraud_detection_system;
USE fraud_detection_system;

-- Users Registration Table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    encrypted_card_no LONGTEXT NOT NULL,
    encrypted_cvv LONGTEXT NOT NULL,
    expiry_date VARCHAR(10) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(100) NOT NULL,
    mobile_number VARCHAR(20) NOT NULL,
    registered_ip VARCHAR(45) NOT NULL,
    card_limit DECIMAL(10, 2) DEFAULT 100000.00,
    current_card_limit DECIMAL(10, 2) DEFAULT 100000.00,
    account_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_mobile (mobile_number)
);

-- Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    card_no_last4 VARCHAR(4),
    amount DECIMAL(10, 2) NOT NULL,
    transaction_location VARCHAR(100),
    transaction_ip VARCHAR(45),
    device_id VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Approved', 'OTP_Sent', 'Blocked', 'Failed') NOT NULL,
    fraud_score FLOAT,
    ml_score FLOAT,
    bla_score FLOAT,
    prediction_method ENUM('ML_Only', 'ML_BLA') NOT NULL,
    otp_code VARCHAR(6),
    otp_verified BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_timestamp (user_id, timestamp),
    INDEX idx_status (status)
);

-- User Behavior Profile Table
CREATE TABLE IF NOT EXISTS user_behavior (
    user_id VARCHAR(50) PRIMARY KEY,
    usual_city VARCHAR(100),
    usual_state VARCHAR(100),
    usual_device VARCHAR(255),
    avg_spend DECIMAL(10, 2) DEFAULT 0.00,
    total_transactions INT DEFAULT 0,
    last_transaction_timestamp TIMESTAMP NULL,
    last_transaction_location VARCHAR(100),
    last_transaction_ip VARCHAR(45),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- OTP Verification Table
CREATE TABLE IF NOT EXISTS otp_verification (
    otp_id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id INT NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    otp_code VARCHAR(6) NOT NULL,
    email VARCHAR(100),
    mobile_number VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_otp_code (otp_code),
    INDEX idx_expires (expires_at)
);

-- Verify tables created
SELECT 'Database schema created successfully!' AS Status;
SELECT COUNT(*) AS 'Users Table' FROM information_schema.tables 
WHERE table_schema = 'fraud_detection_system' AND table_name = 'users';
SELECT COUNT(*) AS 'Transactions Table' FROM information_schema.tables 
WHERE table_schema = 'fraud_detection_system' AND table_name = 'transactions';
SELECT COUNT(*) AS 'User Behavior Table' FROM information_schema.tables 
WHERE table_schema = 'fraud_detection_system' AND table_name = 'user_behavior';
SELECT COUNT(*) AS 'OTP Table' FROM information_schema.tables 
WHERE table_schema = 'fraud_detection_system' AND table_name = 'otp_verification';

