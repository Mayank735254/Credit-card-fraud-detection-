import json
import urllib.request

url = 'http://127.0.0.1:5000/process_payment'
headers = {'Content-Type': 'application/json'}

data = {
    'user_id': 'test_user_1',
    'amount': 12.34,
    'state': 'CA',
    'card_num': '4111111111111111'
}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
with urllib.request.urlopen(req, timeout=10) as resp:
    print(resp.read().decode())
