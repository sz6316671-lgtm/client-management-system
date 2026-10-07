import os
from contextlib import contextmanager

from flask import Blueprint, render_template, request, redirect, url_for, flash
import psycopg2

leads_bp = Blueprint('leads', __name__)


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


def read_lead_form(form):
    """Form se lead data nikalo. Khali follow_up_date -> None (DB error se bachne ke liye)."""
    return (
        form.get('name', '').strip(),
        form.get('company', '').strip(),
        form.get('phone', '').strip(),
        form.get('email', '').strip(),
        form.get('source', '').strip(),
        form.get('service_interested', '').strip(),
        form.get('lead_status', 'New').strip() or 'New',
        form.get('assigned_salesperson', '').strip(),
        form.get('notes', '').strip(),
        form.get('follow_up_date') or None,
    )


# Login check app.py ke before_request mein ho raha hai, isliye yahan dobara zaroorat nahi.

@leads_bp.route('/leads')
def manage_leads():
    with db_cursor() as cur:
        cur.execute(
            'SELECT id, name, company, phone, email, source, service_interested, '
            'lead_status, assigned_salesperson, follow_up_date '
            'FROM leads ORDER BY id DESC'
        )
        leads = cur.fetchall()

    return render_template('leads.html', leads=leads)


@leads_bp.route('/add-lead', methods=['GET', 'POST'])
def add_lead():
    if request.method == 'POST':
        data = read_lead_form(request.form)

        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO leads (name, company, phone, email, source, service_interested,
                                   lead_status, assigned_salesperson, notes, follow_up_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                data,
            )
        return redirect(url_for('leads.manage_leads'))

    return render_template('add_lead.html')


@leads_bp.route('/lead-delete/<int:id>', methods=['POST'])
def delete_lead(id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM leads WHERE id = %s', (id,))
    return redirect(url_for('leads.manage_leads'))


@leads_bp.route('/lead-edit/<int:id>', methods=['GET', 'POST'])
def edit_lead(id):
    if request.method == 'POST':
        data = read_lead_form(request.form)

        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE leads
                SET name = %s, company = %s, phone = %s, email = %s, source = %s,
                    service_interested = %s, lead_status = %s, assigned_salesperson = %s,
                    notes = %s, follow_up_date = %s
                WHERE id = %s
                """,
                data + (id,),
            )
        return redirect(url_for('leads.manage_leads'))

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name, company, phone, email, source, service_interested, "
            "lead_status, assigned_salesperson, notes, follow_up_date "
            "FROM leads WHERE id = %s",
            (id,),
        )
        lead = cur.fetchone()

    # Lead na mile (ya delete ho chuki ho) to page crash na ho
    if lead is None:
        return redirect(url_for('leads.manage_leads'))

    return render_template('edit_lead.html', lead=lead)


@leads_bp.route('/lead-convert/<int:id>', methods=['POST'])
def convert_lead(id):
    """Lead ko client bana do aur lead ka status 'Won' kar do (dashboard conversion rate isi se banta hai)."""
    with db_cursor(commit=True) as cur:
        cur.execute(
            "SELECT name, company, phone, email, service_interested, lead_status "
            "FROM leads WHERE id = %s FOR UPDATE",
            (id,),
        )
        lead = cur.fetchone()

        if lead is None:
            flash('Lead not found.', 'danger')
            return redirect(url_for('leads.manage_leads'))

        name, company, phone, email, service, status = lead

        if status and status.strip().lower() == 'won':
            flash('This lead is already converted.', 'info')
            return redirect(url_for('leads.manage_leads'))

        # Duplicate client se bachne ke liye email check
        client_exists = False
        if email:
            cur.execute("SELECT id FROM clients WHERE LOWER(email) = LOWER(%s)", (email,))
            client_exists = cur.fetchone() is not None

        if not client_exists:
            cur.execute(
                """
                INSERT INTO clients (name, email, phone, company, services, status)
                VALUES (%s, %s, %s, %s, %s, 'Active')
                """,
                (name, email, phone, company, service),
            )

        cur.execute("UPDATE leads SET lead_status = 'Won' WHERE id = %s", (id,))

    if client_exists:
        flash(f'"{name}" marked as Won. A client with this email already exists, so no duplicate was created.', 'info')
    else:
        flash(f'"{name}" converted to a client successfully.', 'success')

    return redirect(url_for('leads.manage_leads'))