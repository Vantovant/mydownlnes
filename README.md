
# Vanto CRM (Local, Laptop-First)

This is a lightweight, Nimble-style CRM you can run **entirely on your laptop**.  
Stack: **Python + Streamlit + SQLite**. No monthly fees, no cloud dependency.

## Features
- Contacts with status (New/Warm/Hot/Customer/Inactive), tags, owner, notes
- Orders linked to contacts (revenue tracking)
- Campaign log (WhatsApp, Facebook, TikTok, Email)
- WhatsApp Tools: one-click message links with templates + activity logging
- Import/Export (CSV/XLSX)
- Simple dashboard KPIs

## Run
1. Install Python 3.10+
2. Open terminal in this folder and run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data
- SQLite database file `crm.sqlite3` is created automatically.
- Back up by copying this file.

## Importing Your Existing Spreadsheet
Use the **Import / Export** page to upload your XLSX/CSV. Map columns to CRM fields and click **Import**.

## Customize
Open `db.py` to add fields or new tables. Extend `app.py` to add pages like **WhatsApp Group Manager** or **Registrations**.
