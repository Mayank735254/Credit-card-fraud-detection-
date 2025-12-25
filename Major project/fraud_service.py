import os
import logging
from pathlib import Path
from flask import Flask, request, jsonify
import joblib
import numpy as np
from utils import encrypt_text, decrypt_text, mask_card_number, save_image, luhn_check
from db_mysql import init_db, get_conn

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / 'xgboost_oversampled_model.pkl'

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# init DB (requires MySQL reachable with env-configured credentials)
try:
    init_db()
except Exception as e:
    logging.warning('DB init failed: %s', e)


def load_model(path: Path):
    try:
        return joblib.load(path)
    except Exception as e:
        logging.warning('Failed to load model: %s', e)
        class Dummy:
            def predict(self, X):
                return np.zeros((len(X),), dtype=int)
            def predict_proba(self, X):
                n = len(X)
                return np.vstack([np.ones(n)*0.99, np.ones(n)*0.01]).T
        return Dummy()


MODEL = load_model(MODEL_PATH)


def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


@app.route('/register_user', methods=['POST'])
def register_user():
    # Expected multipart/form-data: user_id, state, amount(optional), card_num, card_cvv, card_expiry, card_image(file)
    user_id = (request.form.get('user_id') or '').strip()
    if not user_id:
        return jsonify({'error': 'missing user_id'}), 400

    card_num = request.form.get('card_num', '')
    card_cvv = request.form.get('card_cvv', '')
    card_expiry = request.form.get('card_expiry', '')
    state = request.form.get('state', '')

    if not luhn_check(card_num):
        return jsonify({'error':'invalid card number'}), 400

    img_path = None
    if 'card_image' in request.files:
        img_path = save_image(request.files['card_image'], BASE_DIR / 'uploads', prefix=user_id)

    enc = encrypt_text('|'.join([card_num, card_cvv, card_expiry]))
    mask = mask_card_number(card_num)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "REPLACE INTO user_profiles (user_id, encrypted_card, card_mask, card_image_path, last_state, avg_spend_limit) VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, enc, mask, img_path, state, 1000.0)
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({'status':'saved','user_id':user_id, 'card_mask': mask})


@app.route('/process_payment', methods=['POST'])
def process_payment():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    user_id = (data.get('user_id') or '').strip()
    card_num = data.get('card_num')
    amount = float(data.get('amount') or 0.0)
    state = data.get('state','')

    client_ip = get_client_ip()
    # Check if user exists by user_id or card number
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        if user_id:
            cur.execute("SELECT * FROM user_profiles WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
        elif card_num:
            mask = mask_card_number(card_num)
            cur.execute("SELECT * FROM user_profiles WHERE card_mask=%s", (mask,))
            row = cur.fetchone()
        else:
            row = None

        if not row:
            # First time user: quick ML check based on features only
            features = np.array([[amount, 0, 0, 0, max(0.0, amount/2)]])
            pred = int(MODEL.predict(features)[0])
            status = 'Fraud' if pred != 0 else 'Approved'
            # store minimal profile if approved
            if status == 'Approved' and user_id and card_num:
                enc = encrypt_text('|'.join([card_num, '', '']))
                mask = mask_card_number(card_num)
                cur.execute("INSERT INTO user_profiles (user_id, encrypted_card, card_mask, last_state, avg_spend_limit) VALUES (%s,%s,%s,%s,%s)",
                            (user_id, enc, mask, state, amount*1.5))
                conn.commit()
        else:
            # Returning user: verify ip/state and then do model probability scoring
            score = 0.0
            if state and state != row.get('last_state'):
                score += 0.4
            # prepare model features (example)
            features = np.array([[amount, 0, 0, 0, max(0.0, amount/2)]])
            try:
                ml_prob = float(MODEL.predict_proba(features)[0][1])
            except Exception:
                ml_prob = float(MODEL.predict(features)[0])
            final = ml_prob*0.6 + score
            status = 'Fraud Flagged' if final >= 0.6 else 'Approved'

        # log transaction
        cur.execute("INSERT INTO transaction_logs (user_id, amount, status, ip_address, client_state) VALUES (%s,%s,%s,%s,%s)",
                    (user_id or row and row.get('user_id'), amount, status, client_ip, state))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'status': status})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
