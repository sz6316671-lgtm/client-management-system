from werkzeug.security import generate_password_hash
import psycopg2

# Database connection
conn = psycopg2.connect(
    host="localhost",
    database="client_management_db",
    user="postgres",
    password="123321"  # Apna postgres password yahan likhein
)
cur = conn.cursor()

# Naya secure password hash generate karein
username = "admin"
password_plain = "admin123"
new_hashed_pwd = generate_password_hash(password_plain)

# Pehle check karein agar admin pehle se hai toh update kar dein, warna insert kar dein
cur.execute("SELECT id FROM users WHERE username = %s", (username,))
existing_user = cur.fetchone()

if existing_user:
    cur.execute(
        "UPDATE users SET password_hash = %s, role = %s WHERE username = %s",
        (new_hashed_pwd, 'admin', username)
    )
    print("Admin password successfully updated in database!")
else:
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
        (username, new_hashed_pwd, 'admin')
    )
    print("Admin user successfully created!")

conn.commit()
cur.close()
conn.close()