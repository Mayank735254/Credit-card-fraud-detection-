from flask import Flask, render_template, request, jsonify, session, send_from_directory
import os
import logging
import mysql.connector
from datetime import datetime
from decimal import Decimal
from security_advanced import (
    load_master_key, encrypt_secret, decrypt_secret, 
    generate_otp, get_otp_expiry, verify_otp
)
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Ensure predict worker knows which model to load. Priority:
# 1. Existing env `MODEL_PATH`
# 2. `model.pkl` in project root
# 3. `models/model.pkl` under project
model_path = os.environ.get('MODEL_PATH') or os.path.join(app.root_path, 'model.pkl')
if not os.path.exists(model_path):
    alt = os.path.join(app.root_path, 'models', 'model.pkl')
    if os.path.exists(alt):
        model_path = alt
os.environ['MODEL_PATH'] = model_path

# Load encryption key
MASTER_KEY = load_master_key()
if not MASTER_KEY:
    print("CRITICAL: master.key not found. Run security_advanced.py first.")
    exit(1)

# Database connection
def get_db_connection():
    # Prefer PyMySQL (pure-Python) to avoid native driver instability in-process.
    try:
        import pymysql
        from pymysql.cursors import DictCursor
        try:
            conn = pymysql.connect(host='127.0.0.1', user='root', password='newpassword',
                                   database='fraud_detection_system', port=3306,
                                   connect_timeout=5, cursorclass=DictCursor)
            return conn
        except Exception:
            logging.exception('pymysql connect failed, falling back')
    except Exception:
        logging.info('pymysql not available, will try mysql.connector')

    try:
        # Fallback to mysql.connector
        return mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="newpassword",
            database="fraud_detection_system",
            port=3306,
            connection_timeout=5,
            auth_plugin='mysql_native_password'
        )
    except Exception as e:
        logging.exception(f"Database connection failed: {e}")
        return None


def get_cursor(conn):
    """Return a cursor compatible with both mysql.connector and pymysql."""
    try:
        return conn.cursor(dictionary=True)
    except TypeError:
        # pymysql's cursor doesn't accept dictionary arg if DictCursor set at connect
        return conn.cursor()

# Get IP address from request
def get_client_ip():
    ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if not ip:
        ip = request.headers.get('X-Real-IP', '')
    if not ip:
        ip = request.remote_addr or '127.0.0.1'
    return ip

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/payment')
def payment_page():
    return render_template('payment.html')


@app.route('/favicon.ico')
def favicon():
    static_dir = os.path.join(app.root_path, 'static')
    ico_path = os.path.join(static_dir, 'favicon.ico')
    if os.path.exists(ico_path):
        return send_from_directory(static_dir, 'favicon.ico')
    # No favicon provided; return empty response (204) to avoid 404 logs
    return ('', 204)

# API: User Registration
@app.route('/api/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        logging.info(f"register_user called with data: %s", data)
        
        user_id = data.get('user_id', '').strip()
        card_no = data.get('card_no', '').strip()
        expiry_date = data.get('expiry_date', '').strip()
        cvv = data.get('cvv', '').strip()
        email = data.get('email', '').strip().lower()
        city = data.get('city', '').strip()
        mobile_number = data.get('mobile_number', '').strip()
        
        # Validate required fields
        if not all([user_id, card_no, expiry_date, cvv, email, city, mobile_number]):
            return jsonify({
                "success": False,
                "message": "All fields are required"
            }), 400
        
        # Get IP address
        ip_address = get_client_ip()
        
        conn = get_db_connection()
        logging.info(f"DB connection returned: %s", conn)
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        
        cursor = get_cursor(conn)
        
        # Check if user_id or email already exists
        cursor.execute("SELECT user_id, email FROM users WHERE user_id = %s OR email = %s", 
                      (user_id, email))
        existing = cursor.fetchone()
        
        if existing:
            logging.info(f"Existing check returned: %s", existing)
            if existing['user_id'] == user_id:
                return jsonify({
                    "success": False,
                    "message": "User ID already exists. Please try another one."
                }), 400
            if existing['email'] == email:
                return jsonify({
                    "success": False,
                    "message": "Email already exists. Please try another one."
                }), 400
        
        # Encrypt card number and CVV
        encrypted_card = encrypt_secret(card_no, MASTER_KEY)
        encrypted_cvv = encrypt_secret(cvv, MASTER_KEY)
        
        if not encrypted_card or not encrypted_cvv:
            return jsonify({
                "success": False,
                "message": "Encryption failed"
            }), 500
        
        # Insert user
        cursor.execute("""
            INSERT INTO users (user_id, encrypted_card_no, encrypted_cvv, expiry_date, 
                            email, city, mobile_number, registered_ip, card_limit, current_card_limit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, encrypted_card, encrypted_cvv, expiry_date, email, city, 
              mobile_number, ip_address, 100000.00, 100000.00))
        logging.info('User insert executed')
        
        # Create behavior profile
        cursor.execute("""
            INSERT INTO user_behavior (user_id, usual_city, usual_state, avg_spend, total_transactions)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, city, city, 0.00, 0))
        logging.info('User behavior insert executed')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Registration successful! You can now make payments."
        })
        
    except mysql.connector.IntegrityError as e:
        return jsonify({
            "success": False,
            "message": "User ID or Email already exists"
        }), 400
    except Exception as e:
        logging.exception("Registration error")
        return jsonify({
            "success": False,
            "message": f"Registration failed: {str(e)}"
        }), 500

# API: Payment Processing
@app.route('/api/payment', methods=['POST'])
def process_payment():
    try:
        data = request.get_json()
        logging.info(f"process_payment called with data: %s", data)
        
        user_id = data.get('user_id', '').strip()
        card_no = data.get('card_no', '').strip()
        expiry_date = data.get('expiry_date', '').strip()
        cvv = data.get('cvv', '').strip()
        email = data.get('email', '').strip().lower()
        # Use Decimal to match DB DECIMAL types
        amount = Decimal(str(data.get('amount', 0)))
        
        # Auto-captured data
        transaction_location = data.get('location', '')  # From browser geolocation
        transaction_ip = get_client_ip()
        device_id = data.get('device_id', '')  # Can be generated from browser
        
        if not all([user_id, card_no, expiry_date, cvv, email, amount > 0]):
            return jsonify({
                "success": False,
                "message": "All fields are required"
            }), 400
        
        conn = get_db_connection()
        logging.info(f"DB connection returned: %s", conn)
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        
        cursor = get_cursor(conn)
        
        # Get user data
        cursor.execute("""
            SELECT user_id, encrypted_card_no, encrypted_cvv, expiry_date, email, 
                   city, mobile_number, registered_ip, current_card_limit
            FROM users WHERE user_id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({
                "success": False,
                "message": "User ID not found. Please register first."
            }), 404
        
        # Decrypt and verify card details
        decrypted_card = decrypt_secret(user['encrypted_card_no'], MASTER_KEY)
        decrypted_cvv = decrypt_secret(user['encrypted_cvv'], MASTER_KEY)
        
        if not decrypted_card or not decrypted_cvv:
            return jsonify({
                "success": False,
                "message": "Card verification failed"
            }), 500
        
        # Verify card information
        if (decrypted_card != card_no or 
            user['expiry_date'] != expiry_date or 
            decrypted_cvv != cvv or 
            user['email'] != email):
            return jsonify({
                "success": False,
                "message": "Wrong information. Please provide correct card details."
            }), 400
        
        # Check card limit
        if user['current_card_limit'] < amount:
            return jsonify({
                "success": False,
                "message": "You exceed your card limit. Available limit: " + 
                          str(user['current_card_limit'])
            }), 400
        
        # Get user behavior
        cursor.execute("""
            SELECT usual_city, usual_state, avg_spend, total_transactions, 
                   last_transaction_timestamp, last_transaction_location, last_transaction_ip
            FROM user_behavior WHERE user_id = %s
        """, (user_id,))
        
        behavior = cursor.fetchone()
        
        # Use city name for location (transaction_location should be city name from frontend)
        current_city = transaction_location if transaction_location else 'Unknown'
        
        # Import fraud detection
        from fraud_detection_engine import detect_fraud
        
        # Detect fraud
        fraud_result = detect_fraud(
            user_id=user_id,
            card_no=card_no,
            amount=amount,
            location=current_city,  # Use city name, not coordinates
            ip_address=transaction_ip,
            user_data=user,
            behavior_data=behavior,
            cursor=cursor
        )
        
        # Save transaction
        cursor.execute("""
            INSERT INTO transactions (user_id, card_no_last4, amount, transaction_location, 
                                    transaction_ip, device_id, status, fraud_score, 
                                    ml_score, bla_score, prediction_method, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, card_no[-4:], amount, current_city, transaction_ip, 
              device_id, fraud_result['status'], fraud_result['fraud_score'],
              fraud_result.get('ml_score'), fraud_result.get('bla_score'),
              fraud_result['method'], datetime.now()))
        
        transaction_id = cursor.lastrowid
        
        # Handle based on status
        if fraud_result['status'] == 'Approved':
            # Update card limit
            new_limit = user['current_card_limit'] - amount
            cursor.execute("UPDATE users SET current_card_limit = %s WHERE user_id = %s",
                          (new_limit, user_id))
            
            # Update behavior
            if behavior:
                new_avg = ((behavior['avg_spend'] * behavior['total_transactions']) + amount) / (behavior['total_transactions'] + 1)
                cursor.execute("""
                    UPDATE user_behavior 
                    SET avg_spend = %s, total_transactions = total_transactions + 1,
                        last_transaction_timestamp = NOW(), last_transaction_location = %s,
                        last_transaction_ip = %s
                    WHERE user_id = %s
                """, (new_avg, transaction_location, transaction_ip, user_id))
        
        elif fraud_result['status'] == 'OTP_Sent':
            # Generate and send OTP
            otp_code = generate_otp()
            expires_at = get_otp_expiry()
            
            cursor.execute("""
                UPDATE transactions SET otp_code = %s WHERE transaction_id = %s
            """, (otp_code, transaction_id))
            
            cursor.execute("""
                INSERT INTO otp_verification (transaction_id, user_id, otp_code, email, 
                                             mobile_number, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (transaction_id, user_id, otp_code, email, user['mobile_number'], expires_at))
            
            # TODO: Send OTP via email/SMS
            logging.info(f"OTP {otp_code} generated for transaction {transaction_id}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "status": fraud_result['status'],
            "message": fraud_result['message'],
            "fraud_score": fraud_result['fraud_score'],
            "transaction_id": transaction_id,
            "otp_required": fraud_result['status'] == 'OTP_Sent'
        })
        
    except ValueError as e:
        logging.exception("Payment processing error - invalid input")
        return jsonify({
            "success": False,
            "message": f"Invalid input: {str(e)}"
        }), 400
    except Exception as e:
        logging.exception("Payment processing error")
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR DETAILS:\n{error_details}")
        return jsonify({
            "success": False,
            "status": "Error",
            "message": f"Payment processing failed: {str(e)}",
            "error_type": type(e).__name__
        }), 500

# API: Verify OTP
@app.route('/api/verify_otp', methods=['POST'])
def verify_otp_endpoint():
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        otp_code = data.get('otp_code', '').strip()
        
        conn = get_db_connection()
        cursor = get_cursor(conn)
        
        cursor.execute("""
            SELECT otp_code, expires_at, user_id, amount, transaction_id
            FROM otp_verification ov
            JOIN transactions t ON ov.transaction_id = t.transaction_id
            WHERE ov.transaction_id = %s
        """, (transaction_id,))
        
        otp_data = cursor.fetchone()
        
        if not otp_data:
            return jsonify({"success": False, "message": "Transaction not found"}), 404
        
        is_valid, message = verify_otp(otp_code, otp_data['otp_code'], otp_data['expires_at'])
        
        if is_valid:
            # Update transaction status
            cursor.execute("""
                UPDATE transactions SET status = 'Approved', otp_verified = TRUE
                WHERE transaction_id = %s
            """, (transaction_id,))
            
            # Update card limit
            cursor.execute("""
                UPDATE users u
                JOIN transactions t ON u.user_id = t.user_id
                SET u.current_card_limit = u.current_card_limit - t.amount
                WHERE t.transaction_id = %s
            """, (transaction_id,))
            
            conn.commit()
            return jsonify({
                "success": True,
                "message": "OTP verified. Transaction approved."
            })
        else:
            return jsonify({
                "success": False,
                "message": message
            }), 400
            
    except Exception as e:
        logging.exception("OTP verification error")
        return jsonify({
            "success": False,
            "message": f"OTP verification failed: {str(e)}"
        }), 500

# Error handler for all exceptions
@app.errorhandler(Exception)
def handle_exception(e):
    logging.exception("Unhandled exception")
    return jsonify({
        "success": False,
        "status": "Error",
        "message": f"Server error: {str(e)}",
        "error_details": str(e) if app.debug else "Internal server error"
    }), 500

if __name__ == '__main__':
    print("Fraud Detection System is LIVE at http://127.0.0.1:5000")
    app.run(debug=False, port=5000)

