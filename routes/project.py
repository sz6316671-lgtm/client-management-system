import os
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for
import psycopg2

project_bp = Blueprint('project', __name__)

# DATABASE CONFIGURATION (env variables se, defaults wahi purane)
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'client_management_db')
DB_USERNAME = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '123321')


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USERNAME,
        password=DB_PASSWORD
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


def read_project_form(form):
    """Form values clean karo: khali date -> None, budget -> Decimal (default 0)."""
    client_id = form.get('client_id')
    project_name = form.get('project_name', '').strip()
    description = form.get('description', '').strip()
    start_date = form.get('start_date') or None
    deadline = form.get('deadline') or None
    status = form.get('status', 'Pending')

    try:
        budget = Decimal(form.get('budget') or 0)
    except InvalidOperation:
        budget = Decimal(0)
    if budget < 0:
        budget = Decimal(0)

    return (client_id, project_name, description, start_date, deadline, status, budget)


@project_bp.route('/manage-projects')
def manage_projects():
    search_query = request.args.get('search', '').strip()

    query = """
        SELECT projects.id, clients.name, projects.project_name, projects.description,
               projects.start_date, projects.deadline, projects.status, projects.budget
        FROM projects
        JOIN clients ON projects.client_id = clients.id
    """
    params = ()

    if search_query:
        query += """
            WHERE projects.project_name ILIKE %s
               OR clients.name ILIKE %s
               OR projects.status ILIKE %s
        """
        like = f"%{search_query}%"
        params = (like, like, like)

    query += " ORDER BY projects.id DESC"

    with db_cursor() as cur:
        cur.execute(query, params)
        projects = cur.fetchall()

    return render_template('manage_projects.html', projects=projects)


@project_bp.route('/add-project', methods=['POST', 'GET'])
def add_project():
    if request.method == 'POST':
        data = read_project_form(request.form)

        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO projects
                    (client_id, project_name, description, start_date, deadline, status, budget)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                data
            )
        return redirect(url_for('project.manage_projects'))

    with db_cursor() as cur:
        cur.execute('SELECT id, name FROM clients ORDER BY name ASC')
        clients = cur.fetchall()

    return render_template('add_project.html', clients=clients)


@project_bp.route('/delete-project/<int:id>', methods=['POST', 'GET'])
def delete_project(id):
    with db_cursor(commit=True) as cur:
        cur.execute('DELETE FROM projects WHERE id = %s', (id,))
    return redirect(url_for('project.manage_projects'))


@project_bp.route('/edit-project/<int:id>', methods=['GET', 'POST'])
def edit_project(id):
    if request.method == 'POST':
        data = read_project_form(request.form)

        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE projects
                SET client_id = %s, project_name = %s, description = %s,
                    start_date = %s, deadline = %s, status = %s, budget = %s
                WHERE id = %s
                """,
                data + (id,)
            )
        return redirect(url_for('project.manage_projects'))

    with db_cursor() as cur:
        cur.execute("SELECT * FROM projects WHERE id = %s", (id,))
        project = cur.fetchone()

        cur.execute("SELECT id, name FROM clients ORDER BY name ASC")
        clients = cur.fetchall()

    if project is None:
        return redirect(url_for('project.manage_projects'))

    return render_template('edit_project.html', project=project, clients=clients)