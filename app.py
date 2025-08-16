# app.py — Vanto CRM (full clean build)

import streamlit as st
import pandas as pd
from urllib.parse import quote_plus

# DB helpers expected in your project
from db import (
    init_db,
    insert_contact, update_contact, delete_contact, fetch_contacts,
    insert_order, fetch_orders,
    insert_campaign, fetch_campaigns,
    insert_activity, fetch_activities,
    kpis,
)

# ------------------------------------------------------------
# App config + init
# ------------------------------------------------------------
st.set_page_config(page_title="Vanto CRM", page_icon="📇", layout="wide")
init_db()

# ------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------
def wa_link(phone: str, text: str) -> str:
    """Build a WhatsApp deep-link and normalise SA numbers."""
    p = "".join(c for c in str(phone) if c.isdigit() or c == "+")
    if p.startswith("+"):
        p = p[1:]
    if p.startswith("0") and len(p) >= 10:
        p = "27" + p[1:]
    return f"https://wa.me/{p}?text={quote_plus(text)}"


def safe_fetch_contacts():
    """Fetch contacts whether fetch_contacts expects a filter or not."""
    try:
        rows = fetch_contacts({})  # many builds accept an optional filter dict
    except TypeError:
        rows = fetch_contacts()
    return rows or []


def as_dict_rows(rows, fallback_cols):
    """Ensure list of dicts; convert tuples -> dicts with fallback column names."""
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    return [dict(zip(fallback_cols, r)) for r in rows]


# ------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------
st.sidebar.title("📇 Vanto CRM")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Contacts", "Orders", "Campaigns", "WhatsApp Tools", "Import / Export", "Help"],
)

# ======================================================================
# Dashboard
# ======================================================================
if page == "Dashboard":
    st.header("📊 Distributor Dashboard")

    try:
        metrics = kpis() or {}
    except Exception:
        metrics = {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Distributors", metrics.get("distributors", 0))
    c2.metric("Active", metrics.get("active", 0))
    c3.metric("Expired", metrics.get("expired", 0))
    c4.metric("Inactive", metrics.get("inactive", 0))

    # Optional level chart if your DB has the table
    try:
        from db import get_conn
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT level, COUNT(*) AS c
                FROM contacts
                WHERE distributor_status='Distributor'
                GROUP BY level ORDER BY level
            """).fetchall()
        lvl_df = pd.DataFrame(rows, columns=["level", "count"])
        if not lvl_df.empty:
            st.bar_chart(lvl_df.set_index("level"))
        else:
            st.info("No distributors yet. Import your downline via Import / Export.")
    except Exception:
        pass

# ======================================================================
# Contacts
# ======================================================================
elif page == "Contacts":
    st.header("👥 Contacts (Existing Distributors)")
    st.caption("Schema: level, leg, associate_id, name, member_status, distributor_status, location, phone, email, tags.")

    # Filters
    q = st.text_input("Search name / phone / email / Associate ID", "")
    col1, col2, col3, col4 = st.columns(4)
    member_status = col1.multiselect("Member Status", ["Active", "Expired"], default=["Active", "Expired"])
    distributor_status = col2.multiselect("Distributor Status", ["Distributor", "Inactive"], default=["Distributor", "Inactive"])
    levels = col3.multiselect("Levels (1–13)", list(range(1, 14)))
    leg_filter = col4.text_input("Leg (optional)", "")

    filters = {
        "q": q.strip() or None,
        "member_status": member_status or None,
        "distributor_status": distributor_status or None,
        "levels": levels or None,
        "legs": [leg_filter] if leg_filter else None,
    }

    try:
        data = fetch_contacts({k: v for k, v in filters.items() if v})
    except TypeError:
        data = fetch_contacts()

    df = pd.DataFrame(data)

    # Create / Edit
    with st.expander("➕ Add or Edit Distributor"):
        mode = st.radio("Mode", ["Add New", "Edit Existing"], horizontal=True)

        if mode == "Edit Existing" and not df.empty:
            options = {f'{r["name"]} ({r.get("phone","")})': r["id"] for _, r in df.iterrows()}
            sel = st.selectbox("Pick a contact", list(options.keys()))
            sel_id = options[sel]
            rec = df[df["id"] == sel_id].iloc[0].to_dict()
        else:
            rec = {
                "level": 1,
                "leg": "",
                "associate_id": "",
                "name": "",
                "member_status": "Active",
                "distributor_status": "Distributor",
                "location": "",
                "phone": "",
                "email": "",
                "tags": "",
            }

        c1, c2, c3 = st.columns(3)
        rec["level"] = c1.number_input("Level", min_value=1, max_value=13, value=int(rec.get("level") or 1), step=1)
        rec["leg"] = c2.text_input("Leg", rec.get("leg", ""))
        rec["associate_id"] = c3.text_input("Associate ID", rec.get("associate_id", ""))

        rec["name"] = st.text_input("Name and surname", rec.get("name", ""))

        c4, c5, c6 = st.columns(3)
        rec["member_status"] = c4.selectbox("Member Status", ["Active", "Expired"],
                                            index=0 if rec.get("member_status", "Active") == "Active" else 1)
        rec["distributor_status"] = c5.selectbox("Distributor Status", ["Distributor", "Inactive"],
                                                 index=0 if rec.get("distributor_status", "Distributor") == "Distributor" else 1)
        rec["location"] = c6.text_input("Location", rec.get("location", ""))

        c7, c8, c9 = st.columns(3)
        rec["phone"] = c7.text_input("Phone", rec.get("phone", ""))
        rec["email"] = c8.text_input("E-mail", rec.get("email", ""))
        rec["tags"] = c9.text_input("Tags (comma-separated)", rec.get("tags", ""))

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
        cols = [c for c in ["level","leg","associate_id","name","member_status","distributor_status","location","phone","email","tags"] if c in df.columns]
        st.dataframe(df[cols].sort_values(["level","name"]), use_container_width=True)

# ======================================================================
# Orders
# ======================================================================
elif page == "Orders":
    st.header("🧾 Orders")
    rows = safe_fetch_contacts()
    rows = as_dict_rows(rows, ["id","name","phone","email"])
    contact_map = {f'#{r.get("id")} {r.get("name","")}': r.get("id") for r in rows} if rows else {}

    with st.form("add_order"):
        contact_sel = st.selectbox("Contact", list(contact_map.keys())) if contact_map else None
        product = st.text_input("Product (e.g., STP, NRM, Luna)")
        qty = st.number_input("Quantity", min_value=1, value=1, step=1)
        amount = st.number_input("Amount (ZAR)", min_value=0.0, step=1.0)
        status = st.selectbox("Status", ["Pending", "Paid", "Shipped", "Delivered"], index=0)
        pop_url = st.text_input("POP URL (optional)")
        notes = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Add Order")
        if submitted and contact_sel:
            insert_order(dict(
                contact_id=contact_map[contact_sel],
                product=product,
                quantity=int(qty),
                amount=float(amount),
                status=status,
                pop_url=pop_url,
                notes=notes
            ))
            st.success("Order added.")

    st.subheader("Recent Orders")
    o_rows = fetch_orders()
    if o_rows:
        o_df = pd.DataFrame(o_rows, columns=["ID","ContactID","Contact","Product","Qty","Amount","Status","POP","Notes","Created"])
        st.dataframe(o_df, use_container_width=True, hide_index=True)
    else:
        st.info("No orders yet.")

# ======================================================================
# Campaigns
# ======================================================================
elif page == "Campaigns":
    st.header("📣 Campaigns")

    # Create / Save
    with st.form("add_campaign"):
        channel = st.selectbox("Channel", ["WhatsApp","Facebook","TikTok","Email","YouTube","Other"])
        name = st.text_input("Campaign Name")
        audience = st.text_input("Audience / Segment")
        message = st.text_area("Message (template)")
        outcome = st.selectbox("Outcome", ["","Sent","Replied","Converted","Bounced","Seen"])
        notes = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Save Campaign")
        if submitted:
            insert_campaign(dict(
                date=None, channel=channel, name=name, audience=audience,
                message=message, outcome=outcome, notes=notes
            ))
            st.success("Campaign saved.")

    # Search (Python-side, because some builds of fetch_campaigns() take no args)
    st.subheader("Search")
    s = st.text_input("Search campaigns", value="")

    c_rows = fetch_campaigns() or []
    c_rows = as_dict_rows(c_rows, ["id","date","channel","name","audience","message","outcome","notes"])

    if s and s.strip():
        needle = s.strip().lower()
        def hit(r: dict) -> bool:
            return any(
                needle in str(r.get(k, "")).lower()
                for k in ("name","notes","message","channel","audience","outcome","date","tags")
            )
        c_rows = [r for r in c_rows if hit(r)]

    if c_rows:
        display_cols = ["id","date","channel","name","audience","message","outcome","notes"]
        header_map = {"id":"ID","date":"Date","channel":"Channel","name":"Name",
                      "audience":"Audience","message":"Message","outcome":"Outcome","notes":"Notes"}
        df_c = pd.DataFrame(c_rows)
        display_cols = [c for c in display_cols if c in df_c.columns]
        st.dataframe(df_c[display_cols].rename(columns=header_map), use_container_width=True, hide_index=True)
    else:
        st.info("No campaigns yet.")

# ======================================================================
# WhatsApp Tools
# ======================================================================
elif page == "WhatsApp Tools":
    st.header("💬 WhatsApp Tools")
    st.write("Create one-click WhatsApp messages with your templates.")

    template = st.text_area(
        "Template",
        value=("Hi 👋 {name}, it’s Vanto from APLGO SA.\n"
               "Your R375 membership unlocks global shopping 🌍, currency payouts 💱, and the same powerful lozenges you love 🍃.\n"
               "Life has seasons — your door to APLGO is open again! 🔑\n"
               "Rejoin here 👉 https://myaplworld.com/pages.cfm?p=CC1809B8\n"
               "We’ve kept your seat warm 🔥")
    )

    rows = safe_fetch_contacts()
    rows = as_dict_rows(rows, ["id","name","phone","email","status","tags"])

    if rows:
        st.subheader("Pick a contact")
        lookup = {f'#{r.get("id")} {r.get("name","")}': r for r in rows}
        sel = st.selectbox("Contact", list(lookup.keys()))
        r = lookup[sel]

        ctx = {
            "name": r.get("name", ""),
            "phone": r.get("phone", ""),
            "interest": r.get("interest", ""),
            "status": r.get("status") or r.get("distributor_status", ""),
            "tags": r.get("tags", ""),
            "assigned": r.get("assigned", ""),
            "city": r.get("city", ""),
            "province": r.get("province", ""),
            "country": r.get("country", ""),
            "apl_go_id": r.get("username") or r.get("associate_id", ""),
        }

        try:
            filled = template.format(**ctx)
        except KeyError as e:
            st.error(f"Your template uses {{{e}}} but that field isn’t in the contact record.")
            filled = template

        link = wa_link(ctx["phone"], filled)
        st.markdown(f"[Open WhatsApp message ↗]({link})")
        st.code(filled)

        if st.button("Log as Activity (WhatsApp)"):
            insert_activity(dict(
                contact_id=r.get("id"),
                activity_date=None,
                type="whatsapp",
                summary="Sent template",
                details=filled
            ))
            st.success("Activity logged.")
    else:
        st.info("Add contacts first.")

# ======================================================================
# Import / Export
# ======================================================================
elif page == "Import / Export":
    st.header("📥 Import / Export")
    st.write("Import distributors from CSV/Excel. Map to the APLGO-style fields used on the Contacts page.")

    upl = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if upl is not None:
        df = pd.read_csv(upl) if upl.name.endswith(".csv") else pd.read_excel(upl)
        st.write("Preview:")
        st.dataframe(df.head(), use_container_width=True)

        crm_fields = [
            "level", "leg", "associate_id", "name",
            "member_status", "distributor_status",
            "location", "phone", "email", "tags",
        ]

        def norm(s: str) -> str:
            return "".join(c for c in s.lower().replace("’", "'") if c.isalnum())

        col_norm_map = {c: norm(c) for c in df.columns}
        guesses = {
            "level": ["level"],
            "leg": ["leg"],
            "associate_id": ["associatesid","associateid","associate'sid"],
            "name": ["nameandsurname","fullname","name"],
            "member_status": [],
            "distributor_status": [],
            "location": ["location","city","town"],
            "phone": ["phone","phonenumber","cell","mobile"],
            "email": ["email","e-mail","mail"],
            "tags": ["tagscommaseparated","tags","labels","gostatus","go-status"],
        }

        st.write("Map your columns to CRM fields (we pre-guess common names):")
        col_map = {}
        for f in crm_fields:
            options = ["--"] + list(df.columns)
            guess_idx = 0
            for target in guesses.get(f, []):
                for i, c in enumerate(df.columns, start=1):
                    if col_norm_map[c] == target:
                        guess_idx = i
                        break
                if guess_idx:
                    break
            col_map[f] = st.selectbox(f"{f}", options, index=guess_idx, key=f"map_{f}")

        if st.button("Import Now", type="primary"):
            cnt = 0
            for _, row in df.iterrows():
                rec = {}

                def get_val(field):
                    col = col_map.get(field, "--")
                    if col and col != "--":
                        val = row[col]
                        return "" if pd.isna(val) else str(val)
                    return ""

                rec["level"] = int(float(get_val("level") or 1))
                rec["leg"] = get_val("leg")
                rec["associate_id"] = get_val("associate_id")
                rec["name"] = get_val("name")
                rec["member_status"] = get_val("member_status") or "Active"
                rec["distributor_status"] = get_val("distributor_status") or "Distributor"
                rec["location"] = get_val("location")
                phone_raw = get_val("phone")
                rec["phone"] = "".join(ch for ch in phone_raw if ch.isdigit() or ch == "+")
                rec["email"] = get_val("email")
                rec["tags"] = get_val("tags").strip().strip(",")

                if rec.get("name") or rec.get("phone"):
                    insert_contact(rec)
                    cnt += 1

            st.success(f"Imported {cnt} distributors.")

    st.divider()
    st.subheader("Export")
    exp_rows = safe_fetch_contacts()
    if exp_rows:
        try:
            exp_df2 = pd.DataFrame(exp_rows)
            cols = ["level","leg","associate_id","name","member_status","distributor_status","location","phone","email","tags"]
            cols = [c for c in cols if c in exp_df2.columns]
            if cols:
                st.download_button(
                    "Download Contacts CSV (Contacts schema)",
                    exp_df2[cols].to_csv(index=False).encode("utf-8"),
                    "contacts_export.csv",
                    "text/csv",
                )
            else:
                exp_df = pd.DataFrame(exp_rows)
                st.download_button(
                    "Download Contacts CSV (raw)",
                    exp_df.to_csv(index=False).encode("utf-8"),
                    "contacts_export_raw.csv",
                    "text/csv",
                )
        except Exception:
            exp_df = pd.DataFrame(exp_rows)
            st.download_button(
                "Download Contacts CSV (raw)",
                exp_df.to_csv(index=False).encode("utf-8"),
                "contacts_export_raw.csv",
                "text/csv",
            )
    else:
        st.info("No contacts to export yet.")

# ======================================================================
# Help
# ======================================================================
elif page == "Help":
    st.header("🚀 How to run this CRM")
    help_md = (
        "**1) Install Python 3.10+**\n\n"
        "**2) Open Terminal / Command Prompt** and run:\n"
        "```\n"
        "pip install -r requirements.txt\n"
        "streamlit run app.py\n"
        "```\n\n"
        "The app opens at **http://localhost:8501**.\n\n"
        "**Tips**\n"
        "- Use **Import / Export** to bring in your Excel lists.\n"
        "- Use **WhatsApp Tools** to send pre-filled messages per contact.\n"
        "- Track progress with statuses (Active / Expired; Distributor / Inactive).\n"
        "- Log interactions under **WhatsApp Tools** (Activity log).\n"
    )
    st.markdown(help_md)
