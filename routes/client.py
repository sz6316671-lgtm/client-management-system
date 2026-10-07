from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
import psycopg2

# Blueprint create kar rahe hain
client_bp = Blueprint('client', __name__)

# Database Configuration
DB_HOST = "localhost"
DB_NAME = "client_management_db"
DB_USER = "postgres"
DB_PASSWORD = "123321"  # Apna password yahan likhein


def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn


# Add Client Route (ab users table mein login account bhi banata hai)
@client_bp.route('/add-client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        company = request.form['company']
        website = request.form['website']
        services = request.form['services']
        status = request.form['status']

        # Login ke liye zaroori fields
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Pehle check karein username pehle se to nahi hai
            cur.execute('SELECT id FROM users WHERE username = %s', (username,))
            if cur.fetchone():
                flash('Ye username pehle se maujood hai. Doosra username chunein.', 'danger')
                return redirect(url_for('client.add_client'))

            # 1. users table mein login account banayein
            password_hash = generate_password_hash(password)
            cur.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, 'client')
                RETURNING id
                """,
                (username, password_hash)
            )
            user_id = cur.fetchone()[0]

            # 2. clients table mein profile banayein, user_id se link karte hue
            cur.execute(
                """
                INSERT INTO clients (name, email, phone, company, website, services, status, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (name, email, phone, company, website, services, status, user_id)
            )

            conn.commit()
            flash(f'Client "{name}" ban gaya. Login username: {username}', 'success')
            return redirect(url_for('client.manage_client'))

        except Exception as e:
            conn.rollback()
            flash(f'Client add karte waqt error aaya: {e}', 'danger')
            return redirect(url_for('client.add_client'))

        finally:
            cur.close()
            conn.close()

    return render_template('add_client.html')


# Manage Client Route (Search ke sath)
@client_bp.route('/manage-client')
def manage_client():
    search_query = request.args.get('search', '')
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        if search_query:
            query = """
                SELECT * FROM clients
                WHERE name ILIKE %s OR company ILIKE %s OR email ILIKE %s
                ORDER BY id DESC
            """
            search_param = f"%{search_query}%"
            cur.execute(query, (search_param, search_param, search_param))
        else:
            cur.execute("SELECT * FROM clients ORDER BY id DESC")

        clients = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return render_template('manage_client.html', clients=clients)


# Delete Client Route (client ke sath uska login account bhi delete hoga)
@client_bp.route('/delete-client/<int:id>', methods=['POST', 'GET'])
def delete_client(id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Pehle client ka linked user_id nikal lein
        cur.execute('SELECT user_id FROM clients WHERE id = %s', (id,))
        row = cur.fetchone()
        linked_user_id = row[0] if row else None

        # Client row delete karein
        cur.execute("DELETE FROM clients WHERE id = %s", (id,))

        # Agar login account linked tha, usay bhi delete karein
        if linked_user_id:
            cur.execute("DELETE FROM users WHERE id = %s", (linked_user_id,))

        conn.commit()
        flash('Client aur uska login account delete ho gaya.', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Delete karte waqt error aaya: {e}', 'danger')

    finally:
        cur.close()
        conn.close()

    return redirect(url_for('client.manage_client'))


# Edit & Update Client Route (ab login username/password bhi manage karta hai)
@client_bp.route('/edit-client/<int:id>', methods=['GET', 'POST'])
def edit_client(id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Client ka current data + uska linked user_id nikalein
        cur.execute("SELECT * FROM clients WHERE id = %s", (id,))
        client = cur.fetchone()

        if client is None:
            return redirect(url_for('client.manage_client'))

        # user_id column ka index clients table ke column order par depend karta hai.
        # Pehle diye gaye schema ke mutabiq: id, name, email, phone, company, website, services, status, user_id
        linked_user_id = client[-1]

        if request.method == 'POST':
            name = request.form['name']
            email = request.form['email']
            phone = request.form['phone']
            company = request.form['company']
            website = request.form['website']
            services = request.form['services']
            status = request.form['status']

            # Ye fields optional hain - khali chhoड़ने ka matlab "change mat karo"
            new_username = request.form.get('username', '').strip()
            new_password = request.form.get('password', '').strip()

            try:
                # 1. Client profile update karein
                cur.execute(
                    """
                    UPDATE clients
                    SET name = %s, email = %s, phone = %s, company = %s, website = %s, services = %s, status = %s
                    WHERE id = %s
                    """,
                    (name, email, phone, company, website, services, status, id)
                )

                # 2. Agar admin ne username diya hai, to login account handle karein
                if new_username:
                    # Username kisi doosre user ne to nahi le rakha (khud ko chhod kar)
                    cur.execute(
                        'SELECT id FROM users WHERE username = %s AND id != %s',
                        (new_username, linked_user_id or -1)
                    )
                    if cur.fetchone():
                        conn.rollback()
                        flash('Ye username kisi aur account mein pehle se use ho raha hai.', 'danger')
                        return redirect(url_for('client.edit_client', id=id))

                    if linked_user_id:
                        # Client ka login account pehle se maujood hai - update karein
                        if new_password:
                            password_hash = generate_password_hash(new_password)
                            cur.execute(
                                'UPDATE users SET username = %s, password_hash = %s WHERE id = %s',
                                (new_username, password_hash, linked_user_id)
                            )
                        else:
                            # Sirf username badla ja raha hai, password wahi rahega
                            cur.execute(
                                'UPDATE users SET username = %s WHERE id = %s',
                                (new_username, linked_user_id)
                            )
                    else:
                        # Ye purana/legacy client hai jiska login account tha hi nahi - naya banayein
                        if not new_password:
                            conn.rollback()
                            flash('Naya login banane ke liye password bhi likhein.', 'danger')
                            return redirect(url_for('client.edit_client', id=id))

                        password_hash = generate_password_hash(new_password)
                        cur.execute(
                            """
                            INSERT INTO users (username, password_hash, role)
                            VALUES (%s, %s, 'client')
                            RETURNING id
                            """,
                            (new_username, password_hash)
                        )
                        new_user_id = cur.fetchone()[0]

                        # Client row ko is naye user se link karein
                        cur.execute(
                            'UPDATE clients SET user_id = %s WHERE id = %s',
                            (new_user_id, id)
                        )

                conn.commit()
                flash('Client update ho gaya.', 'success')
                return redirect(url_for('client.manage_client'))

            except Exception as e:
                conn.rollback()
                flash(f'Update karte waqt error aaya: {e}', 'danger')
                return redirect(url_for('client.edit_client', id=id))

        # GET request - agar login account maujood hai to uska username dikhayein
        current_username = None
        if linked_user_id:
            cur.execute('SELECT username FROM users WHERE id = %s', (linked_user_id,))
            row = cur.fetchone()
            current_username = row[0] if row else None

        return render_template(
            'edit_client.html',
            client=client,
            current_username=current_username,
            has_login=linked_user_id is not None
        )

    finally:
        cur.close()
        conn.close()