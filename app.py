
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
    c1.metric("Total Distributors", m.get("distributors", 0))
    c2.metric("Active", m.get("active", 0))
    c3.metric("Expired", m.get("expired", 0))
    c4.metric("Inactive", m.get("inactive", 0))

    st.subheader("Levels 1–13")
    from db import get_conn
    with get_conn() as conn:
        lvl_rows = conn.execute(
    "SELECT level, COUNT(*) c FROM contacts WHERE distributor_status='Distributor' GROUP BY level"
).fetchall()


    import pandas as pd
    lvl_df = pd.DataFrame(lvl_rows, columns=["level", "count"])
    if not lvl_df.empty:
        st.bar_chart(lvl_df.set_index("level"))
    else:
        st.info("No distributors yet. Import your downline on the Import / Export page.")

# --- CONTACTS ---
elif page == "Contacts":
    st.header("👥 Contacts")
    with st.expander("➕ Add / Edit Contact", expanded=True):
        mode = st.radio("Mode", ["Add","Edit","Delete"], horizontal=True)
        if mode == "Add":
            with st.form("add_contact"):
                name = st.text_input("Name *")
                phone = st.text_input("Phone")
                email = st.text_input("Email")
                c1, c2, c3 = st.columns(3)
                with c1:
                    source = st.text_input("Source (e.g., GRW, NRM, Referral)")
                with c2:
                    interest = st.text_input("Interest (e.g., Luna, GRW, STP, NRM)")
                with c3:
                    status = st.selectbox("Status", ["New","Warm","Hot","Customer","Inactive"], index=0)
                tags = st.text_input("Tags (comma-separated)")
                assigned = st.text_input("Assigned (rep/owner)", value="Vanto")
                notes = st.text_area("Notes", height=80)
                submitted = st.form_submit_button("Save Contact")
                if submitted and name:
                    contact_id = insert_contact(dict(name=name, phone=phone, email=email, source=source, interest=interest, status=status, tags=tags, assigned=assigned, notes=notes))
                    st.success(f"Saved contact #{contact_id}: {name}")
        elif mode == "Edit":
            rows = fetch_contacts()
            options = {f"#{r[0]} {r[1]} • {r[2] or ''}": r for r in rows}
            sel = st.selectbox("Select contact", list(options.keys())) if options else None
            if sel:
                r = options[sel]
                with st.form("edit_contact"):
                    name = st.text_input("Name *", r[1])
                    phone = st.text_input("Phone", r[2] or "")
                    email = st.text_input("Email", r[3] or "")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        source = st.text_input("Source", r[4] or "")
                    with c2:
                        interest = st.text_input("Interest", r[5] or "")
                    with c3:
                        status = st.selectbox("Status", ["New","Warm","Hot","Customer","Inactive"], index=["New","Warm","Hot","Customer","Inactive"].index(r[6] or "New"))
                    tags = st.text_input("Tags", r[7] or "")
                    assigned = st.text_input("Assigned", r[8] or "")
                    notes = st.text_area("Notes", r[9] or "", height=80)
                    submitted = st.form_submit_button("Update Contact")
                    if submitted and name:
                        update_contact(r[0], dict(name=name, phone=phone, email=email, source=source, interest=interest, status=status, tags=tags, assigned=assigned, notes=notes))
                        st.success("Contact updated.")
        else:  # Delete
            rows = fetch_contacts()
            options = {f"#{r[0]} {r[1]} • {r[2] or ''}": r for r in rows}
            sel = st.selectbox("Select contact to delete", list(options.keys())) if options else None
            if sel and st.button("Delete Contact", type="primary"):
                r = options[sel]
                delete_contact(r[0])
                st.warning(f"Deleted contact #{r[0]} {r[1]}")

    st.subheader("Search & Filter")
    col1, col2, col3 = st.columns(3)
    with col1:
        search = st.text_input("Search", placeholder="Name, phone, email, interest, notes...")
    with col2:
        status_f = st.selectbox("Status filter", ["","New","Warm","Hot","Customer","Inactive"])
    with col3:
        tag_f = st.text_input("Tag filter")
    rows = fetch_contacts(search=search, status=status_f, tag=tag_f)
    if rows:
        df = pd.DataFrame(rows, columns=["ID","Name","Phone","Email","Source","Interest","Status","Tags","Assigned","Notes","Created"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No contacts found.")

# --- ORDERS ---
elif page == "Orders":
    st.header("🧾 Orders")

    # Load contacts (dict rows, not tuples)
    rows = fetch_contacts({})
    if not rows:
        st.info("No contacts yet. Add or import contacts first.")
    else:
        # Build dropdown: "Name (Phone)" -> id
        contact_map = {
            f"{r.get('name','[No Name]')} ({r.get('phone','')})": r["id"]
            for r in rows
        }
        sel = st.selectbox("Select distributor", list(contact_map.keys()))
        contact_id = contact_map[sel]

        # New order form
        with st.form("new_order"):
            order_date = st.date_input("Order date")
            product = st.text_input("Product")
            qty = st.number_input("Qty", min_value=1, step=1, value=1)
            amount = st.number_input("Amount", min_value=0.0, step=10.0, value=0.0, format="%.2f")
            notes = st.text_area("Notes", "")
            submitted = st.form_submit_button("Add order")
            if submitted:
                insert_order({
                    "contact_id": contact_id,
                    "order_date": str(order_date),
                    "product": product.strip(),
                    "qty": int(qty),
                    "amount": float(amount),
                    "notes": notes.strip(),
                })
                st.success("Order added.")

        # Show recent orders (with contact names)
        import pandas as pd
        id_to_name = {r["id"]: r.get("name","") for r in rows}
        orders = fetch_orders()
        if not orders:
            st.info("No orders yet.")
        else:
            df = pd.DataFrame(orders)
            if "contact_id" in df.columns:
                df.insert(1, "contact_name", df["contact_id"].map(id_to_name).fillna(""))
            st.dataframe(df)

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
    template = st.text_area(
        "Template",
        value=("Hi {name}…")
    )

    # 1) Get contacts (use {} to show everyone)
    rows = fetch_contacts({"distributor_status": ["Distributor"]})

    # 2) If none, show info
    if not rows:
        st.info("Add contacts first.")
    else:
        # 3) Pick a contact
        st.subheader("Pick a contact")
        options = {
            f"{r.get('name','[No Name]')} ({r.get('phone','')})": r["id"]
            for r in rows
        }
        sel_label = st.selectbox("Contact", list(options.keys()))
        sel_id = options[sel_label]
        rec = next(r for r in rows if r["id"] == sel_id)

        # 4) Fill the template
        filled = template.format(
            name=rec.get("name", ""),
            phone=rec.get("phone", ""),
            level=rec.get("level", ""),
            id=rec.get("associate_id", ""),
        )

        # 5) Normalize phone and build wa.me link
        import re
        def normalize_phone(p: str) -> str:
            d = re.sub(r"\D", "", str(p))
            if d.startswith("0"):
                d = "27" + d[1:]
            return d

        wa_num = normalize_phone(rec.get("phone", ""))
        wa_url = f"https://wa.me/{wa_num}?text={quote_plus(filled)}"

        st.markdown(f"[✅ Open WhatsApp message ↗]({wa_url})")
        st.code(filled)

        # 6) Log activity
        if st.button("Log as Activity (WhatsApp)"):
            insert_activity(rec["id"], "whatsapp", filled)
            st.success("Activity logged.")

# --- IMPORT / EXPORT ---
elif page == "Import / Export":
    st.header("📥 Import / Export — Distributors")
    st.caption("Upload your CSV/XLSX following the sample headers. We'll auto-map and import into the Distributor-focused Contacts.")

    expected = ['Level','Leg',"Associate's ID",'Name and surname','GO status','Location','Phone','E-mail','Tags (comma-separated)']
    st.markdown("**Expected headers:** " + ", ".join([f"`{c}`" for c in expected]))

    tab1, tab2 = st.tabs(["Import distributors", "Export distributors"])

    with tab1:
        file = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"])
        if file is not None:
            import pandas as pd
            name = file.name.lower()
            try:
                if name.endswith(".csv"):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                st.success(f"Loaded file with {len(df)} rows.")
                st.dataframe(df.head(20))
                if st.button("Import now"):
                    from db import bulk_upsert_from_dataframe
                    bulk_upsert_from_dataframe(df)
                    st.success("Import complete. Contacts updated.")
            except Exception as e:
                st.error(f"Failed to read file: {e}")

    with tab2:
        from db import fetch_contacts
        data = fetch_contacts({})
        import pandas as pd
        if not data:
            st.info("No contacts yet to export.")
        else:
            df = pd.DataFrame(data)
            rename = {
                "level": "Level",
                "leg": "Leg",
                "associate_id": "Associate's ID",
                "name": "Name and surname",
                "member_status": "GO status",
                "location": "Location",
                "phone": "Phone",
                "email": "E-mail",
                "tags": "Tags (comma-separated)",
            }
            for k in list(rename.keys()):
                if k not in df.columns:
                    df[k] = ""
            out = df[list(rename.keys())].rename(columns=rename)
            st.dataframe(out.head(20))
            st.download_button("Download CSV", data=out.to_csv(index=False), file_name="contacts_export.csv", mime="text/csv")

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
