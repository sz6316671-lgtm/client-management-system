import os
from contextlib import contextmanager

from flask import Blueprint, flash, render_template, request, redirect, send_file, url_for
import psycopg2

from routes.invoice_pdf import build_invoice_pdf

invoices_bp = Blueprint('invoices', __name__)


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


# Login check app.py ke before_request mein hota hai.

@invoices_bp.route('/invoices')
def manage_invoices():
    with db_cursor() as cur:
        cur.execute("""
            SELECT i.id, c.name AS client_name, i.invoice_number, i.amount, i.status,
                   i.due_date, i.service_type, i.sub_service
            FROM invoices i
            JOIN clients c ON i.client_id = c.id
            ORDER BY i.id DESC
        """)
        invoices = cur.fetchall()

    return render_template('invoices.html', invoices=invoices)


@invoices_bp.route('/invoice/<int:id>/pdf')
def download_invoice_pdf(id):
    """Admin/staff kisi bhi invoice ka PDF download kar sakta hai."""
    with db_cursor() as cur:
        cur.execute(
            'SELECT id, invoice_number, amount, status, due_date, service_type, sub_service, client_id '
            'FROM invoices WHERE id = %s',
            (id,),
        )
        row = cur.fetchone()

        if row is None:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.manage_invoices'))

        invoice = row[:7]
        cur.execute(
            'SELECT name, email, phone, company FROM clients WHERE id = %s',
            (row[7],),
        )
        client = cur.fetchone() or (None, None, None, None)

        cur.execute(
            'SELECT payment_date, payment_method, amount_paid, notes '
            'FROM payments WHERE invoice_id = %s ORDER BY payment_date ASC',
            (id,),
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


@invoices_bp.route('/add-invoice', methods=['GET', 'POST'])
def add_invoice():
    if request.method == 'POST':
        with db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO invoices (client_id, invoice_number, amount, status, due_date, service_type, sub_service)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                request.form['client_id'],
                request.form['invoice_number'],
                request.form['amount'],
                request.form['status'],
                request.form.get('due_date') or None,
                request.form.get('service_type'),
                request.form.get('sub_service'),
            ))
        return redirect(url_for('invoices.manage_invoices'))

    with db_cursor() as cur:
        cur.execute("SELECT id FROM invoices ORDER BY id DESC LIMIT 1")
        last_inv = cur.fetchone()
        next_id = (last_inv[0] + 1) if last_inv else 1
        auto_invoice_number = f"INV-{1000 + next_id}"

        # Clients ke sath project ka naam aur budget (dropdown/auto-fill ke liye)
        cur.execute("""
            SELECT c.id, c.name, p.project_name, p.budget
            FROM clients c
            LEFT JOIN projects p ON c.id = p.client_id
        """)
        clients = cur.fetchall()

    return render_template('add_invoice.html', clients=clients,
                           auto_invoice_number=auto_invoice_number)


@invoices_bp.route('/delete-invoice/<int:id>', methods=['POST'])
def delete_invoice(id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM invoices WHERE id = %s', (id,))
    return redirect(url_for('invoices.manage_invoices'))


@invoices_bp.route('/edit-invoice/<int:id>', methods=['GET', 'POST'])
def edit_invoice(id):
    if request.method == 'POST':
        with db_cursor(commit=True) as cur:
            cur.execute("""
                UPDATE invoices
                SET client_id = %s, invoice_number = %s, amount = %s, status = %s,
                    due_date = %s, service_type = %s, sub_service = %s
                WHERE id = %s
            """, (
                request.form['client_id'],
                request.form['invoice_number'],
                request.form['amount'],
                request.form['status'],
                request.form.get('due_date') or None,
                request.form.get('service_type'),
                request.form.get('sub_service'),
                id,
            ))
        return redirect(url_for('invoices.manage_invoices'))

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, client_id, invoice_number, amount, status, due_date, service_type, sub_service "
            "FROM invoices WHERE id = %s",
            (id,),
        )
        invoice = cur.fetchone()

        cur.execute("SELECT id, name FROM clients ORDER BY name ASC")
        clients = cur.fetchall()

    if invoice is None:
        return redirect(url_for('invoices.manage_invoices'))

    return render_template('edit_invoice.html', invoice=invoice, clients=clients)