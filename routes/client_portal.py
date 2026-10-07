import os
from contextlib import contextmanager
from functools import wraps

from flask import Blueprint, flash, request, redirect, render_template, send_file, session, url_for
import psycopg2
from werkzeug.security import generate_password_hash

from routes.invoice_pdf import build_invoice_pdf

client_portal_bp = Blueprint('client_portal', __name__, url_prefix='/portal')


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'client_management_db'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '123321'),
    )


@contextmanager
def db_cursor(commit=False):
    """Connection/cursor hamesha band hote hain, error aaye tab bhi."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# --- Security Decorator ---
def client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') or session.get('role') != 'client' \
                or not session.get('client_id'):
            flash('Access denied. Client login required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


INVOICES_SQL = (
    'SELECT id, invoice_number, amount, status, due_date, service_type, sub_service '
    'FROM invoices WHERE client_id = %s ORDER BY id DESC'
)

PAYMENTS_SQL = """
    SELECT p.id, i.invoice_number, p.amount_paid, p.payment_date, p.payment_method, p.notes
    FROM payments p
    JOIN invoices i ON p.invoice_id = i.id
    WHERE i.client_id = %s
    ORDER BY p.payment_date DESC
"""

# Dashboard aur My Projects dono templates isi order par depend karte hain
# 0 id, 1 name, 2 description, 3 start_date, 4 deadline, 5 status, 6 budget
MY_PROJECTS_SQL = (
    'SELECT id, project_name, description, start_date, deadline, status, budget '
    'FROM projects WHERE client_id = %s ORDER BY id DESC'
)


@client_portal_bp.route('/dashboard')
@client_required
def dashboard():
    client_id = session.get('client_id')

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name, email, phone, company, services, status "
            "FROM clients WHERE id = %s",
            (client_id,),
        )
        client = cur.fetchone()

        cur.execute(INVOICES_SQL, (client_id,))
        invoices = cur.fetchall()

        cur.execute(PAYMENTS_SQL, (client_id,))
        payments = cur.fetchall()

        cur.execute(MY_PROJECTS_SQL, (client_id,))
        projects = cur.fetchall()

    # Allocated budget = client ke saare projects ke budget ka total
    total_budget = sum((p[6] or 0) for p in projects)

    return render_template(
        'portal/dashboard.html',
        client=client,
        invoices=invoices,
        payments=payments,
        projects=projects,
        total_budget=total_budget,
    )


@client_portal_bp.route('/invoices')
@client_required
def my_invoices():
    with db_cursor() as cur:
        cur.execute(INVOICES_SQL, (session.get('client_id'),))
        invoices = cur.fetchall()

    return render_template('portal/my_invoices.html', invoices=invoices)


@client_portal_bp.route('/payments')
@client_required
def my_payments():
    with db_cursor() as cur:
        cur.execute(PAYMENTS_SQL, (session.get('client_id'),))
        payments = cur.fetchall()

    return render_template('portal/my_payments.html', payments=payments)


@client_portal_bp.route('/projects')
@client_required
def my_projects():
    with db_cursor() as cur:
        cur.execute(MY_PROJECTS_SQL, (session.get('client_id'),))
        projects = cur.fetchall()

    return render_template('portal/my_projects.html', projects=projects)


@client_portal_bp.route('/settings', methods=['GET', 'POST'])
@client_required
def settings():
    client_id = session.get('client_id')

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        new_password = request.form.get('password', '')

        if not name or not email:
            flash('Name and email are required.', 'danger')
            return redirect(url_for('client_portal.settings'))

        if new_password.strip() and len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('client_portal.settings'))

        try:
            with db_cursor(commit=True) as cur:
                # 1. Client profile update
                cur.execute(
                    "UPDATE clients SET name = %s, email = %s, phone = %s WHERE id = %s",
                    (name, email, phone, client_id),
                )

                # 2. Password update (agar naya diya ho)
                if new_password.strip():
                    cur.execute('SELECT user_id FROM clients WHERE id = %s', (client_id,))
                    res = cur.fetchone()
                    if res and res[0]:
                        cur.execute(
                            'UPDATE users SET password_hash = %s WHERE id = %s',
                            (generate_password_hash(new_password), res[0]),
                        )
        except psycopg2.Error as e:
            print("Settings Error:", e)
            flash('Could not update settings. Email may already be in use.', 'danger')
            return redirect(url_for('client_portal.settings'))

        session['username'] = name
        flash('Profile settings updated successfully!', 'success')
        return redirect(url_for('client_portal.settings'))

    with db_cursor() as cur:
        cur.execute(
            'SELECT id, name, email, phone, company FROM clients WHERE id = %s',
            (client_id,),
        )
        client = cur.fetchone()

    return render_template('portal/settings.html', client=client)


@client_portal_bp.route('/invoices/<int:invoice_id>/pdf')
@client_required
def download_invoice(invoice_id):
    client_id = session.get('client_id')

    with db_cursor() as cur:
        # client_id ka check zaroori hai: koi client doosre ka invoice na utha sake
        cur.execute(
            'SELECT id, invoice_number, amount, status, due_date, service_type, sub_service '
            'FROM invoices WHERE id = %s AND client_id = %s',
            (invoice_id, client_id),
        )
        invoice = cur.fetchone()

        if invoice is None:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('client_portal.my_invoices'))

        cur.execute(
            'SELECT name, email, phone, company FROM clients WHERE id = %s',
            (client_id,),
        )
        client = cur.fetchone()

        cur.execute(
            'SELECT payment_date, payment_method, amount_paid, notes '
            'FROM payments WHERE invoice_id = %s ORDER BY payment_date ASC',
            (invoice_id,),
        )
        payments = cur.fetchall()

    pdf = build_invoice_pdf(invoice, client, payments)
    safe_number = ''.join(ch for ch in str(invoice[1]) if ch.isalnum() or ch in '-_') or invoice[0]

    return send_file(
        pdf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'invoice_{safe_number}.pdf',
    )