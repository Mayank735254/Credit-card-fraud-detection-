import subprocess
import json
import sys
import os
from datetime import datetime
from dateutil import parser
import logging
from decimal import Decimal

def safe_predict(features, action='predict', timeout=5):
    """Run ML model prediction in isolated subprocess"""
    try:
        # Sanitize features to ensure JSON serializable (convert Decimal -> float)
        def _sanitize(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, list):
                return [_sanitize(x) for x in obj]
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            return obj

        payload = json.dumps(_sanitize({'features': features, 'action': action}))
        proc = subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'predict_worker.py')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        out, err = proc.communicate(payload, timeout=timeout)
        if err:
            logging.warning(f"predict_worker stderr: {err}")
        if not out:
            return None
        resp = json.loads(out)
        if 'error' in resp:
            logging.error(f"predict_worker error: {resp['error']}")
            return None
        return resp
    except Exception as e:
        logging.exception(f"safe_predict failed: {e}")
        return None

def calculate_bla_score(user_data, behavior_data, amount, location, ip_address, cursor):
    """Calculate Business Logic Analysis score"""
    bla_score = 0.0
    flags = {
        'location_mismatch': 0,
        'ip_mismatch': 0,
        'spending_limit': 0,
        'avg_spend_mismatch': 0,
        'impossible_travel': 0
    }
    
    if not behavior_data:
        return bla_score, flags
    
    # 1. Location/City Mismatch (0.15 weight)
    # Compare current city (from location) with registered city
    if location and behavior_data.get('usual_city'):
        current_city = location  # Location should be city name, not coordinates
        registered_city = behavior_data['usual_city']
        if current_city.lower() != registered_city.lower():
            flags['location_mismatch'] = 1
            bla_score += 0.15
            logging.info(f"Location mismatch: {current_city} != {registered_city}")
    
    # 2. IP Address Check (0.10 weight)
    # If IP matches registered IP, it's NOT fraud (reduce score)
    # If IP doesn't match, it's suspicious (increase score)
    if ip_address and user_data.get('registered_ip'):
        if ip_address == user_data['registered_ip']:
            # IP matches - this is good, don't add to fraud score
            flags['ip_mismatch'] = 0
            logging.info(f"IP matches registered IP: {ip_address}")
        else:
            # IP doesn't match - suspicious
            flags['ip_mismatch'] = 1
            bla_score += 0.10
            logging.info(f"IP mismatch: {ip_address} != {user_data['registered_ip']}")
    
    # 3. Spending Limit Check (0.20 weight)
    if user_data.get('current_card_limit', 0) < amount:
        flags['spending_limit'] = 1
        bla_score += 0.20
    
    # 4. Average Spend Mismatch (0.15 weight)
    avg_spend = behavior_data.get('avg_spend', 0) or 0
    if avg_spend > 0 and amount > (avg_spend * 2):  # More than 2x average
        flags['avg_spend_mismatch'] = 1
        bla_score += 0.15
    
    # 5. Impossible Travel (0.30 weight - highest)
    # Check if location changed too quickly (impossible travel)
    if behavior_data.get('last_transaction_timestamp') and location:
        last_time = behavior_data['last_transaction_timestamp']
        last_location = behavior_data.get('last_transaction_location')
        
        if last_location and location.lower() != last_location.lower():
            # Calculate time difference in minutes
            if isinstance(last_time, str):
                last_time = parser.parse(last_time)
            elif isinstance(last_time, datetime):
                pass
            else:
                last_time = datetime.now()  # Fallback
            
            time_diff = (datetime.now() - last_time).total_seconds() / 60  # minutes
            # If location changed in less than 60 minutes, it's impossible
            if time_diff < 60:
                flags['impossible_travel'] = 1
                bla_score += 0.30
                logging.warning(f"Impossible travel detected: {last_location} -> {location} in {time_diff:.1f} minutes")
    
    return min(bla_score, 1.0), flags  # Cap at 1.0

def detect_fraud(user_id, card_no, amount, location, ip_address, user_data, behavior_data, cursor):
    """
    Main fraud detection function
    Returns: {
        'status': 'Approved' | 'OTP_Sent' | 'Blocked',
        'fraud_score': float (0.0-1.0),
        'ml_score': float (0.0-1.0),
        'bla_score': float (0.0-1.0),
        'method': 'ML_Only' | 'ML_BLA',
        'message': str
    }
    """
    total_transactions = behavior_data.get('total_transactions', 0) if behavior_data else 0
    
    # New user or insufficient history: ML Only
    # Check for impossible travel first (even for new users)
    impossible_travel_detected = False
    if behavior_data and behavior_data.get('last_transaction_timestamp') and location:
        last_time = behavior_data['last_transaction_timestamp']
        last_location = behavior_data.get('last_transaction_location')
        if last_location and location.lower() != last_location.lower():
            if isinstance(last_time, str):
                last_time = parser.parse(last_time)
            time_diff = (datetime.now() - last_time).total_seconds() / 60
            if time_diff < 60:  # Less than 60 minutes
                impossible_travel_detected = True
                logging.warning(f"Impossible travel detected for new user: {time_diff:.1f} minutes")
    
    if total_transactions < 3:
        # ML Only: user_id, card_id, location, ip_address (4 features as specified)
        # Note: Adjust feature encoding based on your actual model training
        ml_features = [[
            hash(user_id) % 10000,  # user_id feature
            hash(card_no[-4:]) % 10000,  # card_id feature (last 4 digits)
            hash(location) % 1000 if location else 0,  # location/city feature
            hash(ip_address) % 10000 if ip_address else 0  # ip_address feature
        ]]
        
        logging.info(f"ML Only - Features: user_id={user_id}, card_id={card_no[-4:]}, location={location}, ip={ip_address}")
        
        # Get ML prediction
        ml_result = safe_predict(ml_features, action='predict_proba')
        
        if ml_result and 'predict_proba' in ml_result:
            ml_prob = ml_result['predict_proba'][0][1]  # Probability of fraud (0-1)
        else:
            ml_prob = 0.05  # Default low risk if model fails
            logging.warning("ML prediction failed, using default low risk")

        # Work in 0-1 range internally
        ml_score = float(ml_prob)
        bla_score = 0.0

        # If impossible travel detected, block immediately
        if impossible_travel_detected:
            fraud_score = 1.0
            logging.warning("Impossible travel detected - blocking transaction")
        else:
            fraud_score = ml_score

        method = 'ML_Only'
        
    else:
        # Returning user: ML + BLA (has history >= 3 transactions)
        # Check for impossible travel first - block immediately if detected
        impossible_travel_detected = False
        if behavior_data.get('last_transaction_timestamp') and location:
            last_time = behavior_data['last_transaction_timestamp']
            last_location = behavior_data.get('last_transaction_location')
            if last_location and location.lower() != last_location.lower():
                if isinstance(last_time, str):
                    last_time = parser.parse(last_time)
                time_diff = (datetime.now() - last_time).total_seconds() / 60
                if time_diff < 60:  # Less than 60 minutes
                    impossible_travel_detected = True
                    logging.warning(f"Impossible travel: {last_location} -> {location} in {time_diff:.1f} minutes")
        
        # Calculate BLA score (returned 0-1)
        bla_score, bla_flags = calculate_bla_score(
            user_data, behavior_data, amount, location, ip_address, cursor
        )
        
        # Prepare ML features: user_id, card_id, amount, timestamp, ip_address, location, avg_spend (7 features)
        avg_spend = behavior_data.get('avg_spend', 0) or 0
        now = datetime.now()
        
        ml_features = [[
            hash(user_id) % 10000,  # user_id
            hash(card_no[-4:]) % 10000,  # card_id
            amount,  # amount
            now.hour,  # timestamp (hour)
            hash(ip_address) % 10000 if ip_address else 0,  # ip_address
            hash(location) % 1000 if location else 0,  # location/city
            avg_spend  # average spending amount
        ]]
        
        logging.info(f"ML+BLA - Features: user_id={user_id}, card_id={card_no[-4:]}, amount={amount}, "
                    f"timestamp={now.hour}, ip={ip_address}, location={location}, avg_spend={avg_spend}")
        
        # Get ML prediction
        ml_result = safe_predict(ml_features, action='predict_proba')
        
        if ml_result and 'predict_proba' in ml_result:
            ml_prob = ml_result['predict_proba'][0][1]
        else:
            ml_prob = 0.05
            logging.warning("ML prediction failed, using default")

        # Work in 0-1 range internally
        ml_score = float(ml_prob)

        # Combine ML (0.65) + BLA (0.35)
        if impossible_travel_detected:
            fraud_score = 1.0
            logging.warning("Impossible travel detected - blocking transaction")
        else:
            fraud_score = (ml_score * 0.65) + (bla_score * 0.35)

        method = 'ML_BLA'
    
    # Determine status based on thresholds (fraud_score in 0-1)
    if fraud_score <= 0.20:
        status = 'Approved'
        message = 'Transaction approved'
    elif fraud_score <= 0.70:
        status = 'OTP_Sent'
        message = 'OTP sent to your registered email/mobile'
    else:
        status = 'Blocked'
        message = 'Transaction blocked due to high fraud risk'

    return {
        'status': status,
        'fraud_score': round(float(fraud_score), 4),
        'ml_score': round(float(ml_score), 4),
        'bla_score': round(float(bla_score), 4),
        'method': method,
        'message': message
    }

