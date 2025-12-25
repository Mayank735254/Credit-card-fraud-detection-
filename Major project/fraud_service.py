import os
import logging
from pathlib import Path
from flask import Flask, request, jsonify
import joblib
import numpy as np
from utils import encrypt_text, decrypt_text, mask_card_number, save_image, luhn_check
from db_mysql import init_db, get_conn
import time
from collections import defaultdict
import threading
import requests

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


# Simple in-memory rate limiter per IP (works for single-process)
_RATE = defaultdict(lambda: {'ts': time.time(), 'count': 0})
_RATE_LOCK = threading.Lock()
RATE_LIMIT = int(os.environ.get('RATE_LIMIT', 60))  # requests per minute


def check_rate_limit(ip: str):
    now = time.time()
    with _RATE_LOCK:
        rec = _RATE[ip]
        # reset window every 60s
        if now - rec['ts'] > 60:
            rec['ts'] = now
            rec['count'] = 0
        rec['count'] += 1
        if rec['count'] > RATE_LIMIT:
            return False
        return True


def get_geo_info(ip: str):
    """Try to fetch simple geo info for an IP using ipapi.co (best-effort)."""
    try:
        resp = requests.get(f'https://ipapi.co/{ip}/json/', timeout=2)
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return {}


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
    if not check_rate_limit(client_ip):
        return jsonify({'error':'rate_limited'}), 429
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
            # geolocation check
            geo = get_geo_info(client_ip)
            if state and state != row.get('last_state'):
                score += 0.4
            if geo:
                # small boost if location mismatch
                city = geo.get('city')
                region = geo.get('region')
                country = geo.get('country_name')
                if region and row.get('last_state') and region != row.get('last_state'):
                    score += 0.2
            # prepare model features (example)
            features = np.array([[amount, 0, 0, 0, max(0.0, amount/2)]])
            try:
                ml_prob = float(MODEL.predict_proba(features)[0][1])
            except Exception:
                ml_prob = float(MODEL.predict(features)[0])
            final = ml_prob*0.6 + score
            status = 'Fraud Flagged' if final >= 0.6 else 'Approved'

        # log transaction
        # support both MySQL param styles and SQLite
        try:
            cur.execute("INSERT INTO transaction_logs (user_id, amount, status, ip_address, client_state) VALUES (%s,%s,%s,%s,%s)",
                        (user_id or (row and row.get('user_id')), amount, status, client_ip, state))
        except Exception:
            cur.execute("INSERT INTO transaction_logs (user_id, amount, status, ip_address, client_state) VALUES (?,?,?,?,?)",
                        (user_id or (row and row.get('user_id')), amount, status, client_ip, state))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'status': status})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
