Project integration notes

Run the enhanced fraud service (MySQL with SQLite fallback):

1. Install dependencies:
   py -3 -m pip install -r requirements.txt

2. Configure DB via environment variables or keep default SQLite fallback.

3. Start service:
   py -3 fraud_service.py

4. Use the client examples in `clients/` to register and create a payment.

Notes:
- Sensitive card data is encrypted with Fernet in `utils.py` and stored in DB.
- In production, do NOT store CVV; follow PCI-DSS guidelines.
