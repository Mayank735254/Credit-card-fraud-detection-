import json
import sys

data = {
    'user_id': 'test_user_1',
    'amount': 12.34,
    'state': 'CA',
    'card_num': '4111111111111111'
}


def run_request_post():
    try:
        import requests  # type: ignore
    except Exception:
        return None

    try:
        url = 'http://127.0.0.1:5000/process_payment'
        resp = requests.post(url, json=data, timeout=5)
        return (resp.status_code, resp.json() if 'application/json' in resp.headers.get('Content-Type','') else resp.text)
    except Exception as e:
        return None


def run_local_test_client():
    from app import app
    with app.test_client() as client:
        resp = client.post('/process_payment', json=data)
        try:
            body = resp.get_json()
        except Exception:
            body = resp.data.decode(errors='replace')
        return (resp.status_code, body)


if __name__ == '__main__':
    result = run_request_post()
    if result is None:
        try:
            result = run_local_test_client()
        except Exception as e:
            print('Both network and local test client failed:', e, file=sys.stderr)
            sys.exit(2)

    print('Status code:', result[0])
    print('Response:', result[1])
