import os
import sqlite3
import joblib
from flask import Flask, request, jsonify, render_template
from cryptography.fernet import Fernet
import numpy as np
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
# Persist a single Fernet key to `secret.key` so encryption survives restarts
KEY_PATH = os.path.join(os.path.dirname(__file__), "secret.key")
if os.path.exists(KEY_PATH):
    with open(KEY_PATH, "rb") as f:
        encryption_key = f.read()
else:
    encryption_key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as f:
        f.write(encryption_key)

cipher_suite = Fernet(encryption_key)

# Load your Model (Ensure the pickle file is present). If missing, use a
# simple DummyModel so the app can run locally for testing.
MODEL_PATH = os.path.join(os.path.dirname(__file__), "xgboost_oversampled_model.pkl")
try:
    model = joblib.load(MODEL_PATH)
except Exception:
    class DummyModel:
        def predict(self, X):
            # Always approve (0)
            try:
                n = len(X)
            except Exception:
                n = 1
            return np.zeros((n,), dtype=int)
        def predict_proba(self, X):
            try:
                n = len(X)
            except Exception:
                n = 1
            # low fraud probability column first, high second
            return np.c_[np.ones((n,)) * 0.99, np.ones((n,)) * 0.01]
    model = DummyModel()
    print("Warning: model file not found — using DummyModel for local testing.")

# SQLite connection (file-based) — easier to run locally than MySQL
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Ensure tables exist
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
    return conn

# --- HELPER FUNCTIONS ---
def encrypt_data(data):
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(data):
    return cipher_suite.decrypt(data.encode()).decode()

def calculate_velocity(user_id, current_state):
    # Advanced Feature: Check if the user changed states too fast
    # For now, a simple 'State Mismatch' check
    return 1 # Placeholder logic

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_payment', methods=['POST'])
def process_payment():
    data = request.json
    user_id = data['user_id']
    amount = float(data['amount'])
    current_state = data['state']
    card_num = data['card_num'] # Should be encrypted
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. CHECK IF USER EXISTS
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    user_record = cursor.fetchone()
    # Convert sqlite3.Row to dict-like object for compatibility
    if user_record:
        user_record = dict(user_record)
    
    # Prepare features for ML Model (Matching your .pkl syntax)
    # Features: [Amount, hour, day_of_week, month, etc.]
    now = datetime.now()
    ml_input = np.array([[amount, now.hour, now.weekday(), now.month, amount/2]]) # Simplified example

    if not user_record:
        # --- NEW USER LOGIC ---
        prediction = model.predict(ml_input)[0]
        status = "Approved" if int(prediction) == 0 else "Fraud"

        if status == "Approved":
            # Save User Data for next time
            enc_card = encrypt_data(card_num)
            cursor.execute(
                "INSERT OR REPLACE INTO user_profiles (user_id, encrypted_card, last_state, avg_spend_limit) VALUES (?, ?, ?, ?)",
                (user_id, enc_card, current_state, amount * 1.5)
            )
            conn.commit()
    else:
        # --- RETURNING USER LOGIC (HYBRID) ---
        # BLA Checks
        bla_score = 0
        if current_state != user_record.get('last_state'):
            bla_score += 0.5 # High risk if location changed

        # Some models may not implement predict_proba; fallback to predict
        try:
            ml_prob = float(model.predict_proba(ml_input)[0][1])
        except Exception:
            # If predict_proba not available, use predict as proxy
            ml_pred = int(model.predict(ml_input)[0])
            ml_prob = 0.0 if ml_pred == 0 else 1.0

        # Hybrid Weighting: 60% ML, 40% BLA
        final_score = (ml_prob * 0.6) + (bla_score * 0.4)
        status = "Approved" if final_score < 0.6 else "Fraud Flagged"

    # Log Transaction
    cursor.execute("INSERT INTO transaction_logs (user_id, amount, status) VALUES (?, ?, ?)",
                   (user_id, amount, status))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "status": status,
        "user_type": "New" if not user_record else "Returning",
        "message": f"Payment {status}"
    })

if __name__ == '__main__':
    app.run(debug=True)