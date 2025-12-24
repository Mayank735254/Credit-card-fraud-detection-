# Major project

Run the Flask app locally (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

- If `xgboost_oversampled_model.pkl` is not present, the app will use a DummyModel for local testing.
- The app stores an encryption key in `secret.key` and uses an SQLite DB at `data.db`.
