import os
import io
from pathlib import Path
from cryptography.fernet import Fernet
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
KEY_PATH = BASE_DIR / "secret.key"

def load_or_create_key():
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    return key

ENCRYPTION_KEY = load_or_create_key()
_FERNET = Fernet(ENCRYPTION_KEY)

def encrypt_text(plain: str) -> str:
    return _FERNET.encrypt(plain.encode()).decode()

def decrypt_text(token: str) -> str:
    return _FERNET.decrypt(token.encode()).decode()

def mask_card_number(card: str) -> str:
    s = ''.join([c for c in str(card) if c.isdigit()])
    if len(s) < 4:
        return '****'
    return '**** **** **** ' + s[-4:]

def save_image(file_storage, dest_dir: Path, prefix: str):
    dest_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(file_storage.stream)
    out_path = dest_dir / f"{prefix}_{file_storage.filename}"
    img.save(out_path)
    return str(out_path)

def luhn_check(card_number: str) -> bool:
    s = ''.join([c for c in card_number if c.isdigit()])
    if not s:
        return False
    total = 0
    reverse = s[::-1]
    for i, ch in enumerate(reverse):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
