from flask import Blueprint, render_template, request, redirect, url_for, session
import psycopg2

payments_bp = Blueprint('payments', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host = 'localhost',
        database = 'client_management_db',
        user = 'postgres',
        password = '123321'
    )
    return conn

# Helper function to auto-update invoice status based on total payments
def update_invoice_status(cur, invoice_id):
    # Invoice ki total amount nikalain
    cur.execute("SELECT amount FROM invoices WHERE id = %s", (invoice_id,))
    inv_res = cur.fetchone()
    if inv_res:
        invoice_total = inv_res[0]

        # Is invoice par total kitni payment ho chuki hai wo nikalain
        cur.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM payments WHERE invoice_id = %s", (invoice_id,))
        paid_res = cur.fetchone()
        total_paid = paid_res[0] if paid_res else 0

        # Status decide karein
        if total_paid >= invoice_total:
            new_status = 'Paid'
        elif total_paid > 0:
            new_status = 'Partially Paid'
        else:
            new_status = 'Unpaid'

        # Invoice table mein status update kar dein
        cur.execute("UPDATE invoices SET status = %s WHERE id = %s", (new_status, invoice_id))

@payments_bp.route('/payments')
def manage_payments():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, i.invoice_number, c.name AS client_name, p.amount_paid, p.payment_date, p.payment_method, p.notes
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN clients c ON i.client_id = c.id
        ORDER BY p.id DESC
    """)
    payments = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('payments.html', payments = payments)

@payments_bp.route('/add-payment', methods = ['POST','GET'])
def add_payment():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        invoice_id = request.form['invoice_id']
        amount_paid = request.form['amount_paid']
        payment_date = request.form['payment_date']
        payment_method = request.form['payment_method']
        notes = request.form['notes']

        # 1. Payment Insert karein
        cur.execute("""
            INSERT INTO payments (invoice_id, amount_paid, payment_date, payment_method, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (invoice_id, amount_paid, payment_date, payment_method, notes))

        # 2. Related Invoice ka status auto-update karein
        update_invoice_status(cur, invoice_id)

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('payments.manage_payments'))
    
    cur.execute('SELECT id, invoice_number FROM invoices')
    invoices  = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('add_payment.html', invoices = invoices)


@payments_bp.route('/delete-payment/<int:id>', methods = ['POST'])
def delete_payment(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Pehle pata karein ke yeh payment kis invoice ki thi
    cur.execute("SELECT invoice_id FROM payments WHERE id = %s", (id,))
    pay_res = cur.fetchone()
    invoice_id = pay_res[0] if pay_res else None

    # Payment delete karein
    cur.execute("DELETE FROM payments WHERE id = %s", (id,))

    # Agar invoice mil jaye toh uska status dobara recalculate karke update karein
    if invoice_id:
        update_invoice_status(cur, invoice_id)

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('payments.manage_payments'))

@payments_bp.route('/edit-payment/<int:id>', methods = ['POST','GET'])
def edit_payment(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        invoice_id = request.form['invoice_id']
        amount_paid = request.form['amount_paid']
        payment_date = request.form['payment_date']
        payment_method = request.form['payment_method']
        notes = request.form['notes']
        
        # Purani payment ka invoice_id check kar lein (agar invoice change kiya ho)
        cur.execute("SELECT invoice_id FROM payments WHERE id = %s", (id,))
        old_pay = cur.fetchone()
        old_invoice_id = old_pay[0] if old_pay else None

        # Payment update karein
        cur.execute("""
            UPDATE payments 
            SET invoice_id = %s, amount_paid = %s, payment_date = %s, payment_method = %s, notes = %s
            WHERE id = %s
        """, (invoice_id, amount_paid, payment_date, payment_method, notes, id))

        # Naye invoice ka status update karein
        update_invoice_status(cur, invoice_id)

        # Agar invoice change hua hai toh purane invoice ka status bhi update karein
        if old_invoice_id and old_invoice_id != int(invoice_id):
            update_invoice_status(cur, old_invoice_id)

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('payments.manage_payments'))
    
    cur.execute("SELECT id, invoice_id, amount_paid, payment_date, payment_method, notes FROM payments WHERE id = %s", (id,))
    payment = cur.fetchone()

    # Dropdown ke liye invoices ki list
    cur.execute("SELECT id, invoice_number FROM invoices")
    invoices = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('edit_payment.html', payment=payment, invoices=invoices)