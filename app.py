
import streamlit as st
import pandas as pd
from urllib.parse import quote_plus
from db import init_db, insert_contact, update_contact, delete_contact, fetch_contacts, insert_order, fetch_orders, insert_campaign, fetch_campaigns, insert_activity, fetch_activities, kpis

st.set_page_config(page_title="Vanto CRM", page_icon="📇", layout="wide")

# --- INIT DB ---
init_db()

# --- SIDEBAR NAV ---
st.sidebar.title("📇 Vanto CRM")
page = st.sidebar.radio("Navigate", ["Dashboard","Contacts","Orders","Campaigns","WhatsApp Tools","Import / Export","Help"])

# --- HELPERS ---
def wa_link(phone: str, text: str):
    # Normalize SA numbers (strip spaces) and allow leading 0 or +27 -> 27
    p = "".join([c for c in phone if c.isdigit()])
    if p.startswith("0"):
        p = "27" + p[1:]
    if p.startswith("27") and len(p) < 11:
        # try to pad missing digits if spaces were removed incorrectly; leave as is otherwise
        pass
    encoded = quote_plus(text)
    return f"https://wa.me/{p}?text={encoded}"

# --- DASHBOARD ---
if page == "Dashboard":
    st.header("📊 Distributor Dashboard")
    m = kpis()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Distributors", m["distributors"])
    c2.metric("Active", m["active"])
    c3.metric("Expired", m["expired"])
    c4.metric("Inactive", m["inactive"])

    st.subheader("Levels 1–13")
    from db import get_conn
    with get_conn() as conn:
        lvl_rows = conn.execute("SELECT level, COUNT(*) c FROM contacts WHERE distributor_status='Distributor' GROUP BY level ORDER BY level").fetchall()
    import pandas as pd
    lvl_df = pd.DataFrame(lvl_rows, columns=["level","count"])
    if not lvl_df.empty:
        st.bar_chart(lvl_df.set_index("level"))
    else:
        st.info("No distributors yet. Import your downline using Import / Export.")

elif page == "Contacts":
    st.header("👥 Contacts (Existing Distributors)")
    st.caption("This list mirrors your APLGO downline. Schema follows the provided sample XLS.")

    # Filters
    q = st.text_input("Search name / phone / email / Associate ID", "")
    col1, col2, col3, col4 = st.columns(4)
    member_status = col1.multiselect("Member Status", ["Active","Expired"], default=["Active","Expired"])
    distributor_status = col2.multiselect("Distributor Status", ["Distributor","Inactive"], default=["Distributor","Inactive"])
    levels = col3.multiselect("Levels (1–13)", list(range(1,14)))
    leg_filter = col4.text_input("Leg (optional)", "")

    filters = {"q": q.strip() or None,
               "member_status": member_status or None,
               "distributor_status": distributor_status or None,
               "levels": levels or None,
               "legs": [leg_filter] if leg_filter else None}

    from db import fetch_contacts, insert_contact, update_contact, delete_contact
    data = fetch_contacts({k:v for k,v in filters.items() if v})
    import pandas as pd
    df = pd.DataFrame(data)

    # Create / Edit
    with st.expander("➕ Add or Edit Distributor"):
        mode = st.radio("Mode", ["Add New","Edit Existing"], horizontal=True)
        if mode == "Edit Existing" and not df.empty:
            options = {f'{r["name"]} ({r.get("phone","")})': r["id"] for _, r in df.iterrows()}
            sel = st.selectbox("Pick a contact", list(options.keys()))
            sel_id = options[sel]
            rec = df[df["id"]==sel_id].iloc[0].to_dict()
        else:
            rec = {"level":1,"leg":"","associate_id":"","name":"","member_status":"Active","distributor_status":"Distributor","location":"","phone":"","email":"","tags":""}

        c1, c2, c3 = st.columns(3)
        rec["level"] = c1.number_input("Level", min_value=1, max_value=13, value=int(rec.get("level") or 1), step=1)
        rec["leg"] = c2.text_input("Leg", rec.get("leg",""))
        rec["associate_id"] = c3.text_input("Associate ID", rec.get("associate_id",""))
        rec["name"] = st.text_input("Name and surname", rec.get("name",""))
        c4, c5, c6 = st.columns(3)
        rec["member_status"] = c4.selectbox("Member Status", ["Active","Expired"], index=0 if rec.get("member_status","Active")=="Active" else 1)
        rec["distributor_status"] = c5.selectbox("Distributor Status", ["Distributor","Inactive"], index=0 if rec.get("distributor_status","Distributor")=="Distributor" else 1)
        rec["location"] = c6.text_input("Location", rec.get("location",""))
        c7, c8, c9 = st.columns(3)
        rec["phone"] = c7.text_input("Phone", rec.get("phone",""))
        rec["email"] = c8.text_input("E-mail", rec.get("email",""))
        rec["tags"] = c9.text_input("Tags (comma-separated)", rec.get("tags",""))

        cc1, cc2, cc3 = st.columns(3)
        if cc1.button("Save"):
            if mode == "Edit Existing":
                update_contact(int(sel_id), rec)
                st.success("Updated distributor.")
            else:
                insert_contact(rec)
                st.success("Added distributor.")
        if mode == "Edit Existing":
            if cc3.button("Delete"):
                delete_contact(int(sel_id))
                st.warning("Distributor deleted.")

    # Table
    if df.empty:
        st.info("No data. Import from your sample XLS on the Import / Export page.")
    else:
        st.dataframe(df[["level","leg","associate_id","name","member_status","distributor_status","location","phone","email","tags"]].sort_values(["level","name"]))


elif page == "Orders":
    st.header("🧾 Orders")
    rows = fetch_contacts()
    contact_map = {f"#{r[0]} {r[1]}": r[0] for r in rows}
    with st.form("add_order"):
        contact_sel = st.selectbox("Contact", list(contact_map.keys())) if contact_map else None
        product = st.text_input("Product (e.g., STP, NRM, Luna)")
        qty = st.number_input("Quantity", min_value=1, value=1, step=1)
        amount = st.number_input("Amount (ZAR)", min_value=0.0, step=1.0)
        status = st.selectbox("Status", ["Pending","Paid","Shipped","Delivered"], index=0)
        pop_url = st.text_input("POP URL (optional)")
        notes = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Add Order")
        if submitted and contact_sel:
            insert_order(dict(contact_id=contact_map[contact_sel], product=product, quantity=int(qty), amount=float(amount), status=status, pop_url=pop_url, notes=notes))
            st.success("Order added.")

    st.subheader("Recent Orders")
    o_rows = fetch_orders()
    if o_rows:
        o_df = pd.DataFrame(o_rows, columns=["ID","ContactID","Contact","Product","Qty","Amount","Status","POP","Notes","Created"])
        st.dataframe(o_df, use_container_width=True, hide_index=True)
    else:
        st.info("No orders yet.")

# --- CAMPAIGNS ---
elif page == "Campaigns":
    st.header("📣 Campaigns")
    with st.form("add_campaign"):
        channel = st.selectbox("Channel", ["WhatsApp","Facebook","TikTok","Email","YouTube","Other"])
        name = st.text_input("Campaign Name")
        audience = st.text_input("Audience/Segment")
        message = st.text_area("Message (template)")
        outcome = st.selectbox("Outcome", ["","Sent","Replied","Converted","Bounced","Seen"])
        notes = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Save Campaign")
        if submitted:
            insert_campaign(dict(date=None, channel=channel, name=name, audience=audience, message=message, outcome=outcome, notes=notes))
            st.success("Campaign saved.")

    st.subheader("Search")
    s = st.text_input("Search campaigns")
    c_rows = fetch_campaigns(s)
    if c_rows:
        c_df = pd.DataFrame(c_rows, columns=["ID","Date","Channel","Name","Audience","Message","Outcome","Notes"])
        st.dataframe(c_df, use_container_width=True, hide_index=True)
    else:
        st.info("No campaigns yet.")

# --- WHATSAPP TOOLS ---
elif page == "WhatsApp Tools":
    st.header("💬 WhatsApp Tools")
    st.write("Create one-click WhatsApp messages with your templates.")
    template = st.text_area("Template", value=("Hi 👋 {name}, it’s Vanto from APLGO SA.\n"
                                               "Your R375 membership expired, but exciting news — MyAPL World is here 🌍, plus our new product Luna 🌙, multicurrency payouts 💱, and the same powerful lozenges you love 🍃.\n"
                                               "Life has seasons — your door to APLGO is open again! 🔑\n"
                                               "Rejoin here 👉 https://myaplworld.com/pages.cfm?p=CC1809B8\n"
                                               "We’ve kept your seat warm 🔥"))
    rows = fetch_contacts()
    if rows:
        st.subheader("Pick a contact")
        lookup = {f"#{r[0]} {r[1]}": r for r in rows}
        sel = st.selectbox("Contact", list(lookup.keys()))
        r = lookup[sel]
        filled = template.format(
            name=r[1], phone=r[2] or "", interest=r[5] or "", status=r[6] or "", tags=r[7] or "", assigned=r[8] or ""
        )
        link = wa_link(r[2] or "", filled)
        st.markdown(f"[Open WhatsApp message ↗]({link})")
        st.code(filled)
        # Log activity
        if st.button("Log as Activity (WhatsApp)"):
            insert_activity(dict(contact_id=r[0], activity_date=None, type="whatsapp", summary="Sent template", details=filled))
            st.success("Activity logged.")
    else:
        st.info("Add contacts first.")

# --- IMPORT / EXPORT ---
elif page == "Import / Export":
    st.header("📥 Import / Export")
    st.write("Import contacts from CSV/Excel. Columns auto-detected: name, phone, email, source, interest, status, tags, assigned, notes.")
    upl = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"])
    if upl is not None:
        if upl.name.endswith(".csv"):
            df = pd.read_csv(upl)
        else:
            df = pd.read_excel(upl)
        st.write("Preview:")
        st.dataframe(df.head(), use_container_width=True)
        # Map columns
        default_map = {
            "name":"name","phone":"phone","email":"email","source":"source","interest":"interest",
            "status":"status","tags":"tags","assigned":"assigned","notes":"notes"
        }
        st.write("Map your columns to CRM fields:")
        crm_fields = list(default_map.keys())
        col_map = {}
        for f in crm_fields:
            options = ["--"] + list(df.columns)
            guess = next((c for c in df.columns if c.lower().strip().replace(" ","") == f), None)
            col_map[f] = st.selectbox(f"{f}", options, index=(options.index(guess) if guess in options else 0), key=f"map_{f}")
        if st.button("Import Now", type="primary"):
            cnt = 0
            for _, row in df.iterrows():
                data = {}
                for f, col in col_map.items():
                    if col != "--":
                        data[f] = str(row[col]) if not pd.isna(row[col]) else ""
                    else:
                        data[f] = ""
                # require at least name or phone
                if data.get("name") or data.get("phone"):
                    insert_contact(data)
                    cnt += 1
            st.success(f"Imported {cnt} contacts.")
    st.divider()
    st.subheader("Export")
    exp_rows = fetch_contacts()
    if exp_rows:
        exp_df = pd.DataFrame(exp_rows, columns=["ID","Name","Phone","Email","Source","Interest","Status","Tags","Assigned","Notes","Created"])
        st.download_button("Download Contacts CSV", exp_df.to_csv(index=False).encode("utf-8"), "contacts_export.csv", "text/csv")

# --- HELP ---
elif page == "Help":
    st.header("🚀 How to run this CRM")
    st.markdown("""
**1) Install Python 3.10+**  
**2) Open Terminal/Command Prompt** and run:
```
pip install -r requirements.txt
streamlit run app.py
```
The app opens in your browser at **http://localhost:8501** and runs completely on your laptop.

**Tips**
- Use **Import / Export** to bring in your Excel lists.
- Use **WhatsApp Tools** to fire off pre-filled messages per contact.
- Track progress with **status** (New → Warm → Hot → Customer → Inactive).
- Log interactions under **WhatsApp Tools** (Activity log).
""")
