from cryptography.fernet import Fernet
import secrets
import string
from datetime import datetime, timedelta
import os

# Generate master key (run once)
def generate_master_key():
    key = Fernet.generate_key()
    key_path = os.path.join(os.path.dirname(__file__), "master.key")
    with open(key_path, "wb") as key_file:
        key_file.write(key)
    print(f"Master Key generated and saved as '{key_path}'")

# Load master key
def load_master_key():
    try:
        key_path = os.path.join(os.path.dirname(__file__), "master.key")
        with open(key_path, "rb") as k:
            return k.read()
    except FileNotFoundError:
        print("ERROR: master.key not found. Run generate_master_key() first.")
        return None

# Encrypt sensitive data
def encrypt_secret(plain_text, key):
    if not key:
        return None
    try:
        cipher_suite = Fernet(key)
        encrypted_text = cipher_suite.encrypt(plain_text.encode())
        return encrypted_text.decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return None

# Decrypt sensitive data
def decrypt_secret(encrypted_text, key):
    if not key:
        return None
    try:
        cipher_suite = Fernet(key)
        decrypted_text = cipher_suite.decrypt(encrypted_text.encode())
        return decrypted_text.decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return None

# Mask card number (show only last 4 digits)
def mask_card(card_number):
    if not card_number or len(card_number) < 4:
        return "****"
    return "**** **** **** " + card_number[-4:]

# Generate 6-digit OTP
def generate_otp():
    return ''.join(secrets.choice(string.digits) for _ in range(6))

# OTP expiration time (5 minutes)
def get_otp_expiry():
    return datetime.now() + timedelta(minutes=5)

# Verify OTP
def verify_otp(entered_otp, stored_otp, expires_at):
    if datetime.now() > expires_at:
        return False, "OTP expired"
    if entered_otp == stored_otp:
        return True, "OTP verified"
    return False, "Invalid OTP"

if __name__ == "__main__":
    # Generate key if not exists
    if not load_master_key():
        generate_master_key()
    
    # Test encryption
    key = load_master_key()
    test_card = "4532781290123456"
    encrypted = encrypt_secret(test_card, key)
    decrypted = decrypt_secret(encrypted, key)
    
    print(f"Original: {test_card}")
    print(f"Encrypted: {encrypted[:50]}...")
    print(f"Decrypted: {decrypted}")
    print(f"Masked: {mask_card(test_card)}")
    print(f"OTP: {generate_otp()}")

