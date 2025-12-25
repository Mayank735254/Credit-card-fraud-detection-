import requests

url = 'http://127.0.0.1:5000/process_payment'
data = {
    'user_id': 'user123',
    'amount': 49.99,
    'state': 'CA'
}

resp = requests.post(url, json=data)
print(resp.status_code, resp.text)
