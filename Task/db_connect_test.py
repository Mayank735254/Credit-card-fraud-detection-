import mysql.connector
HOST='localhost'
PORT=3306
USER='root'
PASSWORD='newpassword'
DATABASE='fraud_detection_system'
print('Attempting to connect to MySQL at', HOST, PORT)
try:
    conn = mysql.connector.connect(host=HOST, port=PORT, user=USER, password=PASSWORD)
    print('Connected. Server version:', conn.get_server_info())
    conn.close()
except Exception as e:
    print('Connection failed:', type(e).__name__, e)
