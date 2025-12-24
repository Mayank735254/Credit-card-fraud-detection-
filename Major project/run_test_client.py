from app import APP as app

with app.test_client() as client:
    payload = {
        'user_id': 'test_user_client',
        'amount': 45.67,
        'state': 'NY',
        'card_num': '4111111111111111'
    }
    resp = client.post('/process_payment', json=payload)
    print('Status code:', resp.status_code)
    print('Response JSON:', resp.get_json())
