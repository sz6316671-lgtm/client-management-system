# CRM Branding Setup

This version adds admin controlled branding to the Flask CRM.

## 1. Run the database migration

Connect to `client_management_db` and run:

    branding_migration.sql

It creates the `app_branding` table.

## 2. Start the CRM

Run the same command you normally use, for example:

    python app.py

## 3. Change the logo

Login with an admin account.

Open:

    Branding

Upload a PNG, JPG, JPEG, GIF, WEBP, or SVG logo and click Save Branding.

The logo appears in:
- Admin/staff sidebar
- Login page
- Client portal

If no logo is uploaded, the existing default CRM icon remains visible.

Uploaded files are stored in `static/uploads/`.
