import os
import uuid

import psycopg2
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

branding_bp = Blueprint("branding", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "client_management_db"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "123321"),
    )


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_branding():
    """Return the single branding row, or safe defaults if it is not configured."""
    defaults = {"company_name": "SysZenix CRM", "logo_url": None}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT company_name, logo_url FROM app_branding WHERE id = 1"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"company_name": row[0] or defaults["company_name"], "logo_url": row[1]}
    except Exception as exc:
        print("Branding read error:", exc)
    return defaults


@branding_bp.route("/settings/branding", methods=["GET", "POST"])
def branding_settings():
    if not session.get("logged_in") or session.get("role") != "admin":
        return redirect(url_for("login"))

    branding = get_branding()

    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip() or "SysZenix CRM"
        uploaded = request.files.get("logo")
        logo_url = branding.get("logo_url")

        if uploaded and uploaded.filename:
            if not allowed_file(uploaded.filename):
                flash("Logo must be PNG, JPG, JPEG, GIF, WEBP, or SVG.", "danger")
                return redirect(url_for("branding.branding_settings"))

            upload_dir = os.path.join(current_app.static_folder, "uploads")
            os.makedirs(upload_dir, exist_ok=True)

            ext = secure_filename(uploaded.filename).rsplit(".", 1)[-1].lower()
            filename = f"logo_{uuid.uuid4().hex}.{ext}"
            uploaded.save(os.path.join(upload_dir, filename))
            logo_url = url_for("static", filename=f"uploads/{filename}")

            old_url = branding.get("logo_url")
            if old_url and "/static/uploads/" in old_url:
                old_filename = old_url.split("/static/uploads/", 1)[1]
                old_path = os.path.join(upload_dir, os.path.basename(old_filename))
                if os.path.isfile(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO app_branding (id, company_name, logo_url)
                VALUES (1, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET company_name = EXCLUDED.company_name,
                    logo_url = EXCLUDED.logo_url
                """,
                (company_name, logo_url),
            )
            conn.commit()
            cur.close()
            conn.close()
            flash("Branding settings updated successfully.", "success")
        except Exception as exc:
            print("Branding save error:", exc)
            flash("Could not save branding settings. Run the database migration first.", "danger")

        return redirect(url_for("branding.branding_settings"))

    return render_template("branding_settings.html", branding=branding)


@branding_bp.route("/settings/branding/remove-logo", methods=["POST"])
def remove_logo():
    if not session.get("logged_in") or session.get("role") != "admin":
        return redirect(url_for("login"))

    branding = get_branding()
    logo_url = branding.get("logo_url")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO app_branding (id, company_name, logo_url)
            VALUES (1, %s, NULL)
            ON CONFLICT (id) DO UPDATE SET logo_url = NULL
            """,
            (branding.get("company_name") or "SysZenix CRM",),
        )
        conn.commit()
        cur.close()
        conn.close()

        if logo_url and "/static/uploads/" in logo_url:
            filename = os.path.basename(logo_url.split("/static/uploads/", 1)[1])
            path = os.path.join(current_app.static_folder, "uploads", filename)
            if os.path.isfile(path):
                os.remove(path)

        flash("Logo removed. The CRM will use the default icon.", "success")
    except Exception as exc:
        print("Branding remove error:", exc)
        flash("Could not remove the logo.", "danger")

    return redirect(url_for("branding.branding_settings"))
