import json
import sys

data = {
    'user_id': 'test_user_1',
    'amount': 12.34,
    'state': 'CA',
    'card_num': '4111111111111111'
}

# Try network POST first (requests). If server not running, fallback to Flask test client.
# ...existing code...
try:
    try:
        import requests  # type: ignore        git add -A && git commit -m "Save changes" && git push -u origin HEAD        git add -A && git commit -m "Save changes" && git push -u origin HEAD        git add -A && git commit -m "Save changes" && git push -u origin HEAD
    except ImportError:
        requests = None

    if requests:
        url = 'http://127.0.0.1:5000/process_payment'
        resp = requests.post(url, json=data, timeout=5)
        print('Status code:', resp.status_code)
        try:
            print('Response:', resp.json())
        except Exception:
            print('Response text:', resp.text)
    else:
        # fallback to Flask test client (adjust import to your app)
        from app import app  # adjust to your Flask app module
        with app.test_client() as client:
            resp = client.post('/process_payment', json=data)
            print('Status code:', resp.status_code)
            print('Response:', resp.get_json())
except Exception as e:
    import sys
    print('Network POST failed:', e, file=sys.stderr)
# ...existing code...
