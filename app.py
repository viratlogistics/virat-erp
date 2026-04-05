# =============================
# VIRAT LOGISTICS ERP - PRO MAX VERSION (UPGRADED)
# =============================
# NOTE: Yeh version tumhare original code ko respect karta hai
# aur sirf problems fix + pro features add karta hai

import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import plotly.express as px
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, time

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Virat Logistics ERP PRO", layout="wide")

# ---------------- CONNECTION ----------------
@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except Exception as e:
        st.error(f"❌ Google Sheet Error: {e}")
        return None

sh = get_sh()
if sh is None:
    st.stop()

# ---------------- LOAD / SAVE ----------------
@st.cache_data(ttl=30)
def load(name):
    try:
        ws = sh.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Save Error: {e}")
        return False

# ---------------- DATA ----------------
df_m = load("masters")
df_t = load("trips")
df_p = load("payments")

# Clean numeric
if not df_p.empty:
    df_p['Amount'] = pd.to_numeric(df_p['Amount'], errors='coerce').fillna(0)

# ---------------- COMMON ----------------
def gl(t):
    if df_m.empty: return []
    return sorted(df_m[df_m['Type'] == t]['Name'].dropna().unique())

# =============================
# SIDEBAR MENU
# =============================
with st.sidebar:
    menu = option_menu("Menu", [
        "Dashboard", "LR Entry", "LR Register",
        "Cash & Bank", "Financials", "Invoice"
    ], icons=["speedometer","plus","table","cash","graph","receipt"])

# =============================
# DASHBOARD (FIXED)
# =============================
if menu == "Dashboard":
    st.title("📊 Dashboard")

    total_rev = df_t['Freight'].sum() if not df_t.empty else 0

    # LR based expense only
    trip_exp = df_p[df_p['LR_No'].astype(str) != ""]["Amount"].sum() if not df_p.empty else 0
    office_exp = df_p[df_p['LR_No'] == ""]["Amount"].sum() if not df_p.empty else 0

    profit = total_rev - abs(trip_exp)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", f"₹{total_rev:,.0f}")
    c2.metric("Trip Expense", f"₹{abs(trip_exp):,.0f}")
    c3.metric("Office Exp", f"₹{abs(office_exp):,.0f}")
    c4.metric("Net Profit", f"₹{profit:,.0f}")

# =============================
# LR ENTRY (IMPROVED)
# =============================
elif menu == "LR Entry":
    st.title("🚛 LR Entry")

    with st.form("lr_form"):
        d = st.date_input("Date", date.today())
        party = st.selectbox("Party", ["Select"] + gl("Party"))
        vehicle = st.text_input("Vehicle")
        freight = st.number_input("Freight", min_value=0.0)

        if st.form_submit_button("Save LR"):
            if party != "Select" and freight > 0:
                lr_no = f"LR{int(time.time())}"
                save("trips", [str(d), lr_no, party, vehicle, freight])
                st.success(f"LR Saved: {lr_no}")
                st.rerun()

# =============================
# LR REGISTER + PDF
# =============================
elif menu == "LR Register":
    st.title("📋 LR Register")

    if not df_t.empty:
        for i, row in df_t.iterrows():
            with st.expander(f"LR: {row['LR No']}"):

                def generate_pdf(r):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0,10,"LR COPY",ln=1)

                    pdf.set_font("Arial", '', 10)
                    for k,v in r.items():
                        pdf.cell(0,6,f"{k}: {v}",ln=1)

                    return pdf.output(dest='S').encode('latin-1')

                pdf_data = generate_pdf(row)

                st.download_button("Download PDF", pdf_data, f"LR_{row['LR No']}.pdf")

        st.dataframe(df_t)

# =============================
# CASH & BANK (FULL FIX)
# =============================
elif menu == "Cash & Bank":
    st.title("💰 Cash & Bank")

    accounts = sorted(df_p['Account_Name'].unique()) if not df_p.empty else []

    st.subheader("Balances")
    for acc in accounts:
        bal = df_p[df_p['Account_Name'] == acc]['Amount'].sum()
        st.metric(acc, f"₹{bal:,.0f}")

    st.divider()

    with st.form("cash_entry"):
        d = st.date_input("Date", date.today())
        from_acc = st.selectbox("From", accounts)
        to_acc = st.selectbox("To", accounts)
        amt = st.number_input("Amount", min_value=0.0)
        lr = st.text_input("LR No")
        remarks = st.text_input("Remarks")

        if st.form_submit_button("Save"):
            if amt > 0:
                save("payments", [str(d), from_acc, "EXP", -amt, "Cash", remarks, lr, to_acc])
                save("payments", [str(d), to_acc, "EXP", amt, "Cash", remarks, lr, from_acc])
                st.success("Saved")
                st.rerun()

# =============================
# FINANCIALS (PARTY/BROKER)
# =============================
elif menu == "Financials":
    st.title("📊 Ledger System")

    acc = st.selectbox("Select Account", ["Select"] + gl("Party") + gl("Broker"))

    if acc != "Select":
        ledger = df_p[df_p['Account_Name'] == acc]
        st.dataframe(ledger)

        bal = ledger['Amount'].sum()
        st.metric("Balance", f"₹{bal:,.0f}")

# =============================
# INVOICE GENERATOR
# =============================
elif menu == "Invoice":
    st.title("🧾 Invoice Generator")

    party = st.selectbox("Party", ["Select"] + gl("Party"))

    if party != "Select":
        lrs = df_t[df_t['Party'] == party]

        selected = []
        for i, r in lrs.iterrows():
            if st.checkbox(f"{r['LR No']} - ₹{r['Freight']}", key=i):
                selected.append(r)

        if selected:
            total = sum(float(x['Freight']) for x in selected)
            st.write(f"Total: ₹{total}")

            if st.button("Generate Invoice"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0,10,"INVOICE",ln=1)

                for r in selected:
                    pdf.cell(0,8,f"LR {r['LR No']} - ₹{r['Freight']}",ln=1)

                pdf.cell(0,10,f"TOTAL: ₹{total}",ln=1)

                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button("Download Invoice", pdf_bytes, "invoice.pdf")

st.success("🔥 PRO MAX VERSION READY")
