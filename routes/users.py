from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash
import psycopg2

users_bp = Blueprint("users", __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host = 'localhost',
        database = 'client_management_db',
        user = 'postgres',
        password = '123321'
    )
    return conn

@users_bp.route('/users')
def manage_users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        return "Access Denied: Admins only!", 403
    
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, username, role, created_at FROM users")
    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("users.html", users=users)

@users_bp.route('/add-user', methods=['POST', 'GET'])
def add_user():
    if not session.get('logged_in') or session.get('role') != "admin":
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Corrected function name
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        # Corrected column name to password_hash and passed hashed_password
        cur.execute("INSERT INTO users(username, password_hash, role) VALUES(%s, %s, %s)",
                    (username, hashed_password, role))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('users.manage_users'))
    
    return render_template('add_user.html')

@users_bp.route('/delete-user/<int:id>', methods=['POST'])
def delete_user(id):
    if not session.get('logged_in') or session.get('role') != "admin":
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('DELETE FROM users WHERE id = %s', (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('users.manage_users'))

@users_bp.route('/edit-user/<int:id>', methods=['POST', 'GET'])
def edit_user(id):
    if not session.get('logged_in') or session.get('role') != "admin":
        return redirect(url_for('login'))
    
    # Fixed typo in function name
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        password = request.form['password']

        if password:
            hashed_password = generate_password_hash(password)
            cur.execute("UPDATE users SET username = %s, role = %s, password_hash = %s WHERE id = %s", 
                        (username, role, hashed_password, id))
        else:
            # Fixed typo usernmae -> username
            cur.execute("UPDATE users SET username = %s, role = %s WHERE id = %s", 
                        (username, role, id))
        
        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('users.manage_users'))

    cur.execute('SELECT id, username, role FROM users WHERE id = %s', (id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    return render_template('edit_user.html', user=user)