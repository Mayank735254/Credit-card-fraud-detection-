# Advanced Fraud Detection System

A comprehensive fraud detection system combining Machine Learning (ML) and Business Logic Analysis (BLA) for secure payment processing.

## 🌟 Features

### User Registration
- Secure signup with encrypted card details
- Duplicate user_id/email detection
- Auto-capture IP address
- Initial card limit: ₹1,00,000

### Payment Processing
- Auto-capture location (browser geolocation)
- Auto-capture IP address
- Auto-capture device ID
- Card limit validation
- Real-time fraud detection

### Fraud Detection

#### New Users (< 3 transactions)
- **Method**: ML Only
- **Features**: user_id, card_id, location, ip_address
- Fast and accurate for first-time users

#### Returning Users (≥ 3 transactions)
- **Method**: ML + BLA Hybrid
- **ML Weight**: 65%
- **BLA Weight**: 35%
- **Features**: user_id, card_id, amount, timestamp, ip_address, location, avg_spend

#### BLA Rules
1. **Location Mismatch** (15%): Different city from registered
2. **IP Mismatch** (10%): Different IP from registered
3. **Spending Limit** (20%): Exceeds card limit
4. **Average Spend Mismatch** (15%): Much higher than usual
5. **Impossible Travel** (30%): Location changed too quickly

### Decision Thresholds
- **Score ≤ 20**: ✅ Approve immediately
- **Score 20-70**: 📱 Send OTP for verification
- **Score > 70**: ❌ Block transaction

### OTP System
- 6-digit OTP for medium-risk transactions
- Sent to registered email/mobile
- Valid for 5 minutes
- Required to complete transaction

## 🚀 Quick Start

1. **Setup Database**:
   ```sql
   -- Run database_schema_complete.sql in MySQL
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements_complete.txt
   ```

3. **Generate Encryption Key**:
   ```bash
   python security_advanced.py
   ```

4. **Train ML Model** (in Google Colab):
   - Follow `MODEL_TRAINING_GUIDE.md`
   - Download trained model
   - Place in project folder

5. **Start Server**:
   ```bash
   python app_complete.py
   ```

6. **Access System**:
   - Home: `http://127.0.0.1:5000`
   - Sign Up: `http://127.0.0.1:5000/signup`
   - Payment: `http://127.0.0.1:5000/payment`

## 📊 Model Training

See `MODEL_TRAINING_GUIDE.md` for complete training instructions.

**Recommended Algorithms**:
- XGBoost (95-98% accuracy) ⭐ Recommended
- LightGBM (94-97% accuracy)
- Random Forest (92-95% accuracy)

## 🔐 Security

- Card numbers and CVV encrypted using Fernet
- IP addresses auto-captured and stored
- Location auto-captured from browser
- OTP verification for suspicious transactions

## 📁 Files

- `app_complete.py`: Main Flask application
- `fraud_detection_engine.py`: ML+BLA fraud detection
- `security_advanced.py`: Encryption & OTP
- `database_schema_complete.sql`: Database schema
- `MODEL_TRAINING_GUIDE.md`: Model training guide
- `templates/`: Frontend HTML pages

## 🎯 How It Works

1. **User Registration**:
   - User provides: user_id, card_no, expiry, cvv, email, city, mobile
   - Card details encrypted and stored
   - IP address auto-captured
   - Card limit set to ₹1,00,000

2. **Payment Processing**:
   - User provides: user_id, card_no, expiry, cvv, email, amount
   - System auto-captures: location, IP, device_id, timestamp
   - Validates card details against database
   - Checks card limit
   - Runs fraud detection (ML or ML+BLA)
   - Returns: Approve, OTP, or Block

3. **Fraud Detection**:
   - New user: ML only (4 features)
   - Returning user: ML+BLA (7 features + BLA rules)
   - Calculates fraud score (0-100)
   - Applies thresholds for decision

## 📈 Expected Performance

- **Accuracy**: 95-98% (with XGBoost)
- **False Positive Rate**: < 2%
- **Processing Time**: < 1 second
- **ROC-AUC Score**: 0.95-0.98

## 🔧 Configuration

Update MySQL credentials in `app_complete.py`:
```python
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="your_password",
        database="fraud_detection_system"
    )
```

## 📝 License

This project is for educational purposes.

## 🤝 Support

For issues or questions, check:
- `COMPLETE_SETUP_GUIDE.md` for setup help
- `MODEL_TRAINING_GUIDE.md` for model training
- Terminal output for debug information

---

**Built with ❤️ for secure payment processing**

