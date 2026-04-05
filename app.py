# =============================
# VIRAT LOGISTICS ERP (FINAL CLEAN VERSION)
# =============================

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import date

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Virat ERP", layout="wide")

# ---------------- CONNECTION ----------------
@st.cache_resource
def connect():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

sh = connect()
if sh is None:
    st.stop()

# ---------------- LOAD FUNCTION ----------------
@st.cache_data(ttl=60)
def load(sheet):
    try:
        ws = sh.worksheet(sheet)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

# ---------------- SAVE FUNCTION ----------------
def save(sheet, row):
    try:
        sh.worksheet(sheet).append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Save Error: {e}")
        return False

# ---------------- BALANCE FUNCTION ----------------
def get_balance(df, acc):
    if df.empty: return 0
    return df[df['Account_Name'] == acc]['Amount'].sum()

# ---------------- DATA ----------------
df_p = load("payments")
df_t = load("trips")

# Clean amount
if not df_p.empty:
    df_p['Amount'] = pd.to_numeric(df_p['Amount'], errors='coerce').fillna(0)

# =============================
# MENU
# =============================
menu = st.sidebar.radio("Menu", [
    "Dashboard",
    "LR Entry",
    "Cash & Bank",
    "Business Insights"
])

# =============================
# DASHBOARD
# =============================
if menu == "Dashboard":
    st.title("📊 Dashboard")

    total_rev = df_t['Freight'].sum() if not df_t.empty else 0
    total_exp = df_p[df_p['Type'] == 'EXPENSE']['Amount'].sum() if not df_p.empty else 0
    profit = total_rev - abs(total_exp)

    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue", f"₹{total_rev:,.0f}")
    c2.metric("Expense", f"₹{abs(total_exp):,.0f}")
    c3.metric("Profit", f"₹{profit:,.0f}")

# =============================
# LR ENTRY
# =============================
elif menu == "LR Entry":
    st.title("🚛 LR Entry")

    with st.form("lr"):
        d = st.date_input("Date", date.today())
        party = st.text_input("Party")
        vehicle = st.text_input("Vehicle")
        freight = st.number_input("Freight", min_value=0.0)

        if st.form_submit_button("Save"):
            lr_no = f"LR{int(pd.Timestamp.now().timestamp())}"
            if save("trips", [str(d), lr_no, party, vehicle, freight]):
                st.success("Saved")
                st.rerun()

# =============================
# CASH & BANK
# =============================
elif menu == "Cash & Bank":
    st.title("💰 Cash & Bank")

    accounts = list(df_p['Account_Name'].unique()) if not df_p.empty else []

    st.subheader("Balances")
    for acc in accounts:
        st.metric(acc, f"₹{get_balance(df_p, acc):,.0f}")

    st.divider()

    with st.form("cash"):
        d = st.date_input("Date", date.today())
        from_acc = st.text_input("From")
        to_acc = st.text_input("To")
        amt = st.number_input("Amount", min_value=0.0)
        lr = st.text_input("LR No (optional)")

        if st.form_submit_button("Save"):
            if from_acc and to_acc and amt > 0:
                save("payments", [str(d), from_acc, "EXPENSE", -amt, "Cash", "", lr, to_acc])
                save("payments", [str(d), to_acc, "EXPENSE", amt, "Cash", "", lr, from_acc])
                st.success("Saved")
                st.rerun()

# =============================
# BUSINESS INSIGHTS
# =============================
elif menu == "Business Insights":
    st.title("📈 Insights")

    if not df_t.empty:
        df_t['Freight'] = pd.to_numeric(df_t['Freight'], errors='coerce').fillna(0)
        perf = df_t.groupby('Vehicle')['Freight'].sum().reset_index()
        st.dataframe(perf)

    if not df_p.empty:
        lr_exp = df_p[df_p['LR_No'] != ""]
        st.write("LR Expenses", lr_exp[['LR_No','Amount']])

st.success("✅ FINAL VERSION READY")
