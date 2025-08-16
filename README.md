
# Vanto CRM — Distributor Upgrade

This package keeps your original navigation (Orders, Campaigns, WhatsApp Tools, Import/Export, Help) **unchanged** while upgrading:
- **Dashboard**: focused on existing distributors.
- **Contacts**: matches your sample XLS schema. Removes **Source** and **Interest**. Adds **Member Status (Active/Expired)** and **Distributor Status (Distributor/Inactive)**.

## Contacts schema (database)
- level (1–13), leg, associate_id, name, member_status (Active/Expired), distributor_status (Distributor/Inactive), location, phone, email, tags

## Import template
See `v3_contacts_import_template.csv`. It mirrors your sample.

## Install / Run (localhost)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Open: http://localhost:8501

## Notes
- WhatsApp and Orders pages were preserved from your original ZIP.
- Status filter now uses **Distributor / Inactive** only.
