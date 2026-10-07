-- CRM branding settings
-- Run this once on client_management_db.

CREATE TABLE IF NOT EXISTS app_branding (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    company_name VARCHAR(150) NOT NULL DEFAULT 'SysZenix CRM',
    logo_url TEXT
);

INSERT INTO app_branding (id, company_name, logo_url)
VALUES (1, 'SysZenix CRM', NULL)
ON CONFLICT (id) DO NOTHING;
