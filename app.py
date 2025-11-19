import pandas as pd
import joblib
import mysql.connector
from flask import Flask, request, jsonify, render_template
from cryptography.fernet import Fernet
import numpy as np
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
# Generate a key once and keep it safe!
encryption_key = Fernet.generate_key()
cipher_suite = Fernet(encryption_key)

# Load your Model (Ensure 'credit_card_model.pkl' is in the folder)
model = joblib.load("xgboost_oversampled_model.pkl")

# MySQL Connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="yourpassword",
        database="fraud_detection"
    )

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
    cursor = conn.cursor(dictionary=True)
    
    # 1. CHECK IF USER EXISTS
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
    user_record = cursor.fetchone()
    
    # Prepare features for ML Model (Matching your .pkl syntax)
    # Features: [Amount, hour, day_of_week, month, etc.]
    now = datetime.now()
    ml_input = np.array([[amount, now.hour, now.weekday(), now.month, amount/2]]) # Simplified example

    if not user_record:
        # --- NEW USER LOGIC ---
        prediction = model.predict(ml_input)[0]
        status = "Approved" if prediction == 0 else "Fraud"
        
        if status == "Approved":
            # Save User Data for next time
            enc_card = encrypt_data(card_num)
            cursor.execute("""INSERT INTO user_profiles 
                (user_id, encrypted_card, last_state, avg_spend_limit) 
                VALUES (%s, %s, %s, %s)""", 
                (user_id, enc_card, current_state, amount * 1.5))
            conn.commit()
    else:
        # --- RETURNING USER LOGIC (HYBRID) ---
        # BLA Checks
        bla_score = 0
        if current_state != user_record['last_state']:
            bla_score += 0.5 # High risk if location changed
            
        ml_prob = model.predict_proba(ml_input)[0][1]
        
        # Hybrid Weighting: 60% ML, 40% BLA
        final_score = (ml_prob * 0.6) + (bla_score * 0.4)
        status = "Approved" if final_score < 0.6 else "Fraud Flagged"

    # Log Transaction
    cursor.execute("INSERT INTO transaction_logs (user_id, amount, status) VALUES (%s, %s, %s)",
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