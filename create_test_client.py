"""
Ye script ek test client user banata hai jise aap /login pe test kar sakte hain.
Chalane ka tareeqa: python create_test_client.py
"""

import psycopg2
from werkzeug.security import generate_password_hash

conn = psycopg2.connect(
    host='localhost',
    database='client_management_db',
    user='postgres',
    password='123321'
)
cur = conn.cursor()

TEST_USERNAME = 'testclient'
TEST_PASSWORD = 'Test@1234'   # login test karte waqt yahi use karein

try:
    # 1. users table mein entry banayein (agar pehle se na ho)
    cur.execute('SELECT id FROM users WHERE username = %s', (TEST_USERNAME,))
    existing = cur.fetchone()

    if existing:
        user_id = existing[0]
        print(f'User pehle se maujood hai, id = {user_id}')
    else:
        password_hash = generate_password_hash(TEST_PASSWORD)
        cur.execute(
            'INSERT INTO users (username, password_hash, role) '
            'VALUES (%s, %s, %s) RETURNING id',
            (TEST_USERNAME, password_hash, 'client')
        )
        user_id = cur.fetchone()[0]
        print(f'Naya user banaya, id = {user_id}')

    # 2. clients table mein entry banayein aur user_id link karein
    cur.execute('SELECT id FROM clients WHERE user_id = %s', (user_id,))
    client_existing = cur.fetchone()

    if client_existing:
        print(f'Client row pehle se linked hai, client_id = {client_existing[0]}')
    else:
        cur.execute(
            'INSERT INTO clients (name, email, user_id) '
            'VALUES (%s, %s, %s) RETURNING id',
            ('Test Client', 'testclient@example.com', user_id)
        )
        client_id = cur.fetchone()[0]
        print(f'Naya client row bana, client_id = {client_id}')

    conn.commit()
    print('\n--- Login test karein ---')
    print(f'Username: {TEST_USERNAME}')
    print(f'Password: {TEST_PASSWORD}')

finally:
    cur.close()
    conn.close()