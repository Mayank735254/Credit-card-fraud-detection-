import requests

url = 'http://127.0.0.1:5000/register_user'
files = {
    'card_image': open('sample_card.png', 'rb') if False else None
}
data = {
    'user_id': 'user123',
    'card_num': '4111111111111111',
    'card_cvv': '123',
    'card_expiry': '12/25',
    'state': 'CA'
}

files_payload = {k:v for k,v in files.items() if v}

resp = requests.post(url, data=data, files=files_payload or None)
print(resp.status_code, resp.text)
