import logging
import sqlite3
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from cryptography.fernet import Fernet
import joblib
import numpy as np
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
# provide alias for tests that import APP
APP = app

# Key handling
KEY_PATH = BASE_DIR / "secret.key"
if KEY_PATH.exists():
    encryption_key = KEY_PATH.read_bytes()
else:
    encryption_key = Fernet.generate_key()
    KEY_PATH.write_bytes(encryption_key)

cipher_suite = Fernet(encryption_key)

# Model load with fallback
MODEL_PATH = BASE_DIR / "xgboost_oversampled_model.pkl"
def load_model(path: Path):
    try:
        return joblib.load(path)
    except Exception:
        class DummyModel:
            def predict(self, X):
                arr = np.asarray(X)
                n = arr.shape[0] if arr.ndim > 0 else 1
                return np.zeros((n,), dtype=int)
            def predict_proba(self, X):
                arr = np.asarray(X)
                n = arr.shape[0] if arr.ndim > 0 else 1
                # columns: [prob_not_fraud, prob_fraud]
                return np.vstack([np.ones(n) * 0.99, np.ones(n) * 0.01]).T
        logging.warning("model file not found — using DummyModel for local testing.")
        return DummyModel()

MODEL = load_model(MODEL_PATH)

# DB helpers
DB_PATH = BASE_DIR / "data.db"

def init_db(path: Path):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            encrypted_card TEXT,
            last_state TEXT,
            avg_spend_limit REAL
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
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def encrypt_data(data: str) -> str:
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(token: str) -> str:
    return cipher_suite.decrypt(token.encode()).decode()


init_db(DB_PATH)

# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_payment', methods=['POST'])
def process_payment():
    data = request.get_json(silent=True)
    if not data:
        data = request.form.to_dict() if request.form else {}

    user_id = (data.get('user_id') or '').strip()
    if not user_id:
        return jsonify({'error': 'missing user_id'}), 400

    raw_amount = data.get('amount', '')
    try:
        amount = float(raw_amount)
    except Exception:
        return jsonify({'error': 'invalid amount'}), 400

    state = (data.get('state') or '').strip()
    card_num = data.get('card_num', '')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        user_row = cur.fetchone()
        user_record = dict(user_row) if user_row else None

        now = datetime.now()
        ml_input = np.array([[amount, now.hour, now.weekday(), now.month, max(0.0, amount/2)]])

        if not user_record:
            pred = int(MODEL.predict(ml_input)[0])
            status = 'Approved' if pred == 0 else 'Fraud'
            if status == 'Approved':
                enc_card = encrypt_data(card_num)
                cur.execute(
                    "INSERT OR REPLACE INTO user_profiles (user_id, encrypted_card, last_state, avg_spend_limit) VALUES (?, ?, ?, ?)",
                    (user_id, enc_card, state, amount * 1.5)
                )
                conn.commit()
        else:
            bla_score = 0.0
            if state and state != user_record.get('last_state'):
                bla_score += 0.5
            try:
                ml_prob = float(MODEL.predict_proba(ml_input)[0][1])
            except Exception:
                ml_pred = int(MODEL.predict(ml_input)[0])
                ml_prob = 0.0 if ml_pred == 0 else 1.0
            final_score = ml_prob * 0.6 + bla_score * 0.4
            status = 'Approved' if final_score < 0.6 else 'Fraud Flagged'

        cur.execute("INSERT INTO transaction_logs (user_id, amount, status) VALUES (?, ?, ?)", (user_id, amount, status))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'status': status, 'user_type': 'New' if not user_record else 'Returning', 'message': f'Payment {status}'})


if __name__ == '__main__':
    # bind to all interfaces to help external requests in some environments
    app.run(host='0.0.0.0', port=5000, debug=False)