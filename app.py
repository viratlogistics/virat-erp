import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONFIG & CLOUD SYNC ---
st.set_page_config(page_title="Virat Master ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except Exception as e:
        st.error(f"❌ Connection Fail: {e}"); return None

sh = get_sh()

def load(name):
    try:
        ws = sh.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. DATA LOADING ---
df_t = load("trips"); df_p = load("payments"); df_a = load("admin"); df_d = load("drivers")
num_cols = ["Freight", "HiredCharges", "Diesel", "Toll", "DriverExp", "Advance", "Salary", "Penalty", "Amount"]
for df in [df_t, df_p, df_a, df_d]:
    for c in num_cols:
        if not df.empty and c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

# --- 3. PDF ENGINE ---
def create_pdf(title, data, headers, total=None):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, "VIRAT LOGISTICS", ln=1, align='C')
    pdf.set_font("Arial", 'B', 10); pdf.cell(190, 10, title, ln=1, align='C'); pdf.ln(5)
    cw = 190 / len(headers)
    for h in headers: pdf.cell(cw, 10, h, 1, 0, 'C')
    pdf.ln(); pdf.set_font("Arial", '', 8)
    for row in data:
        for item in row: pdf.cell(cw, 8, str(item), 1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTH ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    with st.sidebar:
        if st.text_input("User") == "admin" and st.text_input("Pass", type="password") == "1234":
            if st.button("Access"): st.session_state.login = True; st.rerun()
    st.stop()

menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard", "Add LR", "LR Manager", "Driver Management", "Party Ledger", "Broker Ledger", "P&L Report", "Transactions", "Office Expense"])

# --- DASHBOARD ---
if menu == "Dashboard":
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum() if not df_p.empty else 0
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum() if not df_p.empty else 0
    st.title("📊 Financial Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash In", f"₹{p_in:,.0f}")
    c2.metric("Cash Out", f"₹{(b_out + df_a['Amount'].sum() if not df_a.empty else b_out):,.0f}")
    c3.metric("Net Flow", f"₹{(p_in - b_out - (df_a['Amount'].sum() if not df_a.empty else 0)):,.0f}")
    st.divider()
    f1, f2 = st.columns(2)
    f1.metric("Receivables (Parties)", f"₹{(df_t['Freight'].sum() - p_in):,.0f}")
    f2.metric("Payables (Brokers)", f"₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# --- ADD LR ---
elif menu == "Add LR":
    st.header("📝 New LR Entry")
    v_type = st.radio("Trip Category", ["Own Truck", "Market Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: d, pty, v_no = st.date_input("Date"), st.text_input("Party*"), st.text_input("Vehicle*")
        with c2: fl, tl, mat = st.text_input("From"), st.text_input("To"), st.text_input("Material")
        with c3:
            fr = st.number_input("Freight*", min_value=0.0)
            if v_type == "Market Hired": br, hc, dsl, tll, de = st.text_input("Broker"), st.number_input("Hired Chg"), 0, 0, 0
            else: br, hc, dsl, tll, de = "OWN", 0, st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Exp")
        if st.form_submit_button("SAVE"):
            pf = (fr - hc) if v_type == "Market Hired" else (fr - dsl - tll - de)
            row = [str(d), f"LR-{len(df_t)+1001}", v_type, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, fl, tl, fr, hc, dsl, de, tll, 0, pf]
            if save("trips", row): st.success("Saved!"); st.rerun()

# --- LR MANAGER ---
elif menu == "LR Manager":
    sq = st.text_input("Search")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)] if not df_t.empty else pd.DataFrame()
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            if st.button(f"🗑️ Delete {r['LR']}", key=f"del_{i}"):
                sh.worksheet("trips").delete_rows(sh.worksheet("trips").find(str(r["LR"])).row); st.rerun()

# --- DRIVER MANAGEMENT ---
elif menu == "Driver Management":
    with st.form("d_f"):
        dn, sl, ad, pn = st.text_input("Driver"), st.number_input("Salary"), st.number_input("Advance"), st.number_input("Penalty")
        if st.form_submit_button("Record"):
            if save("drivers", [str(date.today()), dn, "Present", ad, sl, pn]): st.success("Saved!"); st.rerun()
    if not df_d.empty:
        ds = df_d.groupby("Name").agg({"Advance":"sum", "Salary":"max", "Penalty":"sum", "Date":"count"}).reset_index()
        ds["Balance"] = ((ds["Salary"]/30)*ds["Date"]) - ds["Advance"] - ds["Penalty"]
        st.dataframe(ds)

# --- LEDGERS ---
elif "Ledger" in menu:
    cat_type = "Party" if "Party" in menu else "Broker"
    col_name = "Party" if cat_type == "Party" else "Broker"
    if not df_t.empty:
        sp = st.selectbox("Select Name", df_t[col_name].unique())
        p_t = df_t[df_t[col_name]==sp]; p_p = df_p[(df_p["Name"]==sp) & (df_p["Category"]==cat_type)]
        st.subheader(f"Balance: ₹{p_t['Freight' if cat_type=='Party' else 'HiredCharges'].sum() - p_p['Amount'].sum()}")
        st.dataframe(p_t)

# --- TRANSACTIONS (FIXED NameError) ---
elif menu == "Transactions":
    st.header("💰 Record Payment Entry")
    with st.form("tr_entry"):
        names = list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist())) if not df_t.empty else []
        nm = st.selectbox("Select Party/Broker", names)
        cat = st.selectbox("Category", ["Party", "Broker"])
        am = st.number_input("Amount Received/Paid", min_value=0.0)
        mode = st.selectbox("Payment Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save Transaction"):
            if nm and am > 0:
                if save("payments", [str(date.today()), nm, cat, am, mode]):
                    st.success(f"Payment of ₹{am} recorded for {nm}"); st.rerun()
            else: st.error("Please fill Name and Amount")

# --- OFFICE EXPENSE ---
elif menu == "Office Expense":
    with st.form("oe"):
        am, rem = st.number_input("Amount"), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            if save("admin", [str(date.today()), "Admin", am, rem]): st.success("Saved!"); st.rerun()

# --- P&L ---
elif menu == "P&L Report":
    rev, hire, adm = df_t['Freight'].sum(), df_t['HiredCharges'].sum(), df_a['Amount'].sum()
    st.table({"Particulars":["Revenue","Hired Payouts","Admin Exp","Profit"],"Amount":[rev, hire, adm, (rev-hire-adm)]})
