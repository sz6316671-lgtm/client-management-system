import os

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
import psycopg2
from routes.client import client_bp
from routes.project import project_bp
from routes.leads import leads_bp
from routes.invoices import invoices_bp
from routes.payments import payments_bp
from routes.users import users_bp
from routes.client_portal import client_portal_bp
from routes.branding import branding_bp, get_branding

app = Flask(__name__)

# Production mein ye values environment variables se set karein
app.secret_key = os.environ.get('SECRET_KEY', 'syszenix_crm_secret_key_123')

app.register_blueprint(client_bp)
app.register_blueprint(project_bp)
app.register_blueprint(leads_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(users_bp)
app.register_blueprint(client_portal_bp)
app.register_blueprint(branding_bp)


@app.context_processor
def inject_branding():
    return {'branding': get_branding()}


def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'client_management_db'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '123321')
    )
    return conn


@app.before_request
def require_login():
    endpoint = request.endpoint

    # 404 ya static files ko skip karo
    if endpoint is None or endpoint == 'login' or endpoint.endswith('static'):
        return

    # Login zaroori hai
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    role = session.get('role')

    # Client sirf apna portal aur logout dekh sakta hai (admin pages block)
    if role == 'client':
        if endpoint != 'logout' and not endpoint.startswith('client_portal.'):
            return redirect(url_for('client_portal.dashboard'))

    # Admin/staff ko client portal ki zaroorat nahi
    elif endpoint.startswith('client_portal.'):
        return redirect(url_for('dashboard'))


@app.route('/login', methods=['POST', 'GET'])
def login():
    # Already logged in ho to seedha andar bhejo
    if session.get('logged_in'):
        if session.get('role') == 'client':
            return redirect(url_for('client_portal.dashboard'))
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                'SELECT id, password_hash, role FROM users WHERE username = %s',
                (username,)
            )
            user = cur.fetchone()

            if user and check_password_hash(user[1], password):
                session.clear()
                session['logged_in'] = True
                session['user_id'] = user[0]
                session['username'] = username
                session['role'] = user[2]

                # Client role ho to clients table se client_id map karo
                if user[2] == 'client':
                    cur.execute(
                        'SELECT id FROM clients WHERE user_id = %s',
                        (user[0],)
                    )
                    client_row = cur.fetchone()

                    if not client_row:
                        session.clear()
                        error = 'Client profile not linked. Contact support.'
                        return render_template('login.html', error=error)

                    session['client_id'] = client_row[0]
                    return redirect(url_for('client_portal.dashboard'))

                return redirect(url_for('dashboard'))

            error = 'Invalid username or password'

        except Exception as e:
            print("Login Error:", e)
            error = 'Something went wrong. Please try again.'

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    # Poori session clear karo (pehle sirf logged_in hata raha tha)
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    total_leads = 0
    new_leads = 0
    total_clients = 0
    total_projects = 0
    monthly_revenue = 0
    outstanding_payments = 0
    conversion_rate = 0
    chart_labels = []
    chart_values = []

    try:
        # 1. Leads Metrics
        cur.execute('SELECT COUNT(*) FROM leads')
        total_leads = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM leads WHERE lead_status ILIKE 'NEW'")
        new_leads = cur.fetchone()[0]

        # 2. Clients & Projects
        cur.execute('SELECT COUNT(*) FROM clients')
        total_clients = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM projects')
        total_projects = cur.fetchone()[0]

        # 3. Financial Metrics
        cur.execute("""
            SELECT COALESCE(SUM(amount_paid), 0)
            FROM payments
            WHERE EXTRACT(MONTH FROM payment_date) = EXTRACT(MONTH FROM CURRENT_DATE)
              AND EXTRACT(YEAR FROM payment_date) = EXTRACT(YEAR FROM CURRENT_DATE)
        """)
        monthly_revenue = cur.fetchone()[0]

        cur.execute('SELECT COALESCE(SUM(amount), 0) FROM invoices')
        total_invoiced = cur.fetchone()[0]

        cur.execute('SELECT COALESCE(SUM(amount_paid), 0) FROM payments')
        total_paid = cur.fetchone()[0]

        # Negative na aaye (overpayment ki surat mein)
        outstanding_payments = max(total_invoiced - total_paid, 0)

        # 4. Lead Conversion Rate
        # NOTE: leads table ke lead_status mein jo actual values hain unhi ko yahan add karein
        cur.execute("""
            SELECT COUNT(*) FROM leads
            WHERE lead_status ILIKE ANY (ARRAY['Converted', 'Won', 'Closed Won', 'Client'])
        """)
        converted_leads = cur.fetchone()[0]

        if total_leads > 0:
            conversion_rate = round(converted_leads / total_leads * 100, 1)

        # 5. Chart data: pichhle 6 mahine ki revenue
        cur.execute("""
            SELECT TO_CHAR(m, 'Mon YYYY'), total
            FROM (
                SELECT DATE_TRUNC('month', payment_date) AS m,
                       SUM(amount_paid) AS total
                FROM payments
                WHERE payment_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
                GROUP BY m
            ) t
            ORDER BY m
        """)
        for label, value in cur.fetchall():
            chart_labels.append(label)
            chart_values.append(float(value))

    except Exception as e:
        print("Dashboard Error:", e)
        conn.rollback()

    finally:
        cur.close()
        conn.close()

    return render_template('dashboard.html',
                           total_leads=total_leads,
                           new_leads=new_leads,
                           total_clients=total_clients,
                           total_projects=total_projects,
                           monthly_revenue=monthly_revenue,
                           outstanding_payments=outstanding_payments,
                           conversion_rate=conversion_rate,
                           chart_labels=chart_labels,
                           chart_values=chart_values)


if __name__ == '__main__':
    app.run(debug=True)