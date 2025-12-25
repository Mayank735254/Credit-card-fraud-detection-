import os
from pathlib import Path
import sqlite3

USE_SQLITE = os.environ.get('USE_SQLITE', '1') == '1'

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'fraud_db')
}

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / 'data_fraud.db'


def get_conn():
    """Try MySQL connection if configured and available, otherwise fallback to SQLite."""
    if not USE_SQLITE:
        try:
            import mysql.connector
            return mysql.connector.connect(**DB_CONFIG)
        except Exception:
            pass
    # fallback sqlite
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # Use SQL compatible with both SQLite and MySQL where possible
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            encrypted_card TEXT,
            card_mask TEXT,
            card_image_path TEXT,
            last_state TEXT,
            avg_spend_limit REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            amount REAL,
            status TEXT,
            ip_address TEXT,
            client_state TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_behaviour (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            ip_address TEXT,
            location TEXT,
            user_agent TEXT,
            event_type TEXT,
            event_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()
