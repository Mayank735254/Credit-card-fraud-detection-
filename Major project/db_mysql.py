import os
import mysql.connector
from mysql.connector import errorcode
from pathlib import Path

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'fraud_db')
}


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def init_db():
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id VARCHAR(128) PRIMARY KEY,
            encrypted_card TEXT,
            card_mask VARCHAR(32),
            card_image_path TEXT,
            last_state VARCHAR(32),
            avg_spend_limit DOUBLE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS transaction_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(128),
            amount DOUBLE,
            status VARCHAR(64),
            ip_address VARCHAR(64),
            client_state VARCHAR(32),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_behaviour (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(128),
            ip_address VARCHAR(64),
            location TEXT,
            user_agent TEXT,
            event_type VARCHAR(64),
            event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)

        conn.commit()
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            raise
    finally:
        if conn:
            conn.close()
