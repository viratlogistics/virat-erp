import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. CONFIGURATION & CONNECTION ---
st.set_page_config(page_title="Virat Logistics Ultimate ERP", layout="wide", page_icon="🚚")

def get_gspread_client():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}"); return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

sh = None
if client:
    try: sh = client.open(SHEET_NAME)
    except: st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili."); st.stop()

# --- UTILITIES ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        df = pd.DataFrame(ws.get_all_records())
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save_ws(ws_name, row_list):
    try:
        ws = sh.worksheet(ws_name); ws.append_row(row_list, value_input_option='USER_ENTERED')
        return True
    except: return False

def update_ws(ws_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(ws_name); cell = ws.find(str(lr_no))
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row], value_input_option='USER_ENTERED')
            return True
        return False
    except: return False

def delete_ws(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name); cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row); return True
        return False
    except: return False

# --- DATA REFRESH ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")
    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    num_t = ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp", "Other"]
    for c in num_t: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    else: df_p = pd.DataFrame(columns=cols_p)
    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    else: df_a = pd.DataFrame(columns=cols_a)
else: st.stop()

# --- 2. PDF GENERATORS ---
def pdf_lr(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20); pdf.cell(190, 10, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12); pdf.cell(95, 10, f"LR No: {row['LR']}", 1); pdf.cell(95, 10, f"Date: {row['Date']}", 1, ln=True)
    pdf.ln(5); pdf.cell(190, 10, f"Party: {row['Party']}", 1, ln=True)
    pdf.cell(95, 10, f"Vehicle: {row['Vehicle']}", 1); pdf.cell(95, 10, f"Material: {row['Material']}", 1, ln=True)
    pdf.cell(190, 10, f"Amount: Rs. {row['Freight']:,}/-", 1, align='R')
    return pdf.output(dest='S').encode('latin-1')

def pdf_pl_report(df_trips, df_admin):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(190, 10, "PROFIT & LOSS STATEMENT - VIRAT LOGISTICS", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", 'B', 12)
    rev = df_trips["Freight"].sum(); hire = df_trips["HiredCharges"].sum(); admin = df_admin["Amount"].sum()
    pdf.cell(100, 10, "Total Freight Revenue (+):"); pdf.cell(90, 10, f"Rs. {rev:,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Total Hired Charges (-):"); pdf.cell(90, 10, f"Rs. {hire:,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Total Office Expenses (-):"); pdf.cell(90, 10, f"Rs. {admin:,.2f}", ln=True, align='R')
    pdf.ln(5); pdf.set_fill_color(200, 200, 200)
    pdf.cell(100, 10, "NET PROFIT:", 1, 0, 'L', True); pdf.cell(90, 10, f"Rs. {(rev - hire - admin):,.2f}", 1, 1, 'R', True)
    return pdf.output(dest='S').encode('latin-1')

# --- 3. UI LOGIN ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Portal")
    with st.form("L"):
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Access"):
            if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- 4. NAVIGATION ---
menu = st.sidebar.selectbox("Navigate", ["Dashboard", "Add LR", "LR Manager", "Monthly Bill", "Party Ledger", "Broker Ledger", "Vehicle Profit", "P&L Report", "Transactions", "Admin Expense"])

# DASHBOARD (CASH FLOW SUMMERY)
if menu == "Dashboard":
    st.title("📊 Financial Summary & Cash Flow")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_out = df_a["Amount"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash In (Party)", f"₹{p_in:,.0f}")
    c2.metric("Cash Out (Total)", f"₹{(b_out + adm_out):,.0f}")
    c3.metric("Net Cash Flow", f"₹{(p_in - b_out - adm_out):,.0f}")
    
    st.divider()
    st.subheader("Fund Flow Summary")
    st.write(f"**Total Billed (Party):** ₹{df_t['Freight'].sum():,.0f}")
    st.write(f"**Market Liabilities:** ₹{df_t['HiredCharges'].sum():,.0f}")

# ADD LR
elif menu == "Add LR":
    st.header("📝 New Consignment")
    v_type = st.radio("Type", ["Own", "Hired"], horizontal=True)
    with st.form("a", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: d, pty = st.date_input("Date"), st.text_input("Party*")
        with c2: v_no, fl, tl = st.text_input("Vehicle*"), st.text_input("From"), st.text_input("To")
        with c3: fr, h_c = st.number_input("Freight*"), st.number_input("Hired Charges")
        if st.form_submit_button("Save"):
            prof = (fr - h_c) if v_type == "Hired" else fr
            row = [str(d), f"LR-{len(df_t)+1001}", v_type, pty, "", "", "", "", "", "", "", 0, v_no, "Driver", "", fl, tl, fr, h_c, 0, 0, 0, 0, prof]
            if save_ws("trips", row): st.success("Saved!"); st.rerun()

# LR MANAGER
elif menu == "LR Manager":
    st.header("🔍 Edit / Delete / Print LR")
    sq = st.text_input("Search LR/Vehicle")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"{r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"e_{i}"):
                u_p = st.text_input("Party", r['Party']); u_f = st.number_input("Freight", value=float(r['Freight']))
                if st.form_submit_button("Update"):
                    upd = list(r.values); upd[3], upd[17] = u_p, u_f
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            st.download_button("📥 Download PDF", pdf_lr(r), f"{r['LR']}.pdf")
            if st.button(f"🗑️ Delete {r['LR']}", key=f"d_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# MONTHLY BILL (LR SELECTION FEATURE)
elif menu == "Monthly Bill":
    st.header("📅 Monthly Invoice (Select LR)")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        pty = st.selectbox("Select Party", df_t["Party"].unique())
        m_df = df_t[df_t["Party"] == pty].copy()
        m_df.insert(0, "Select", False)
        selected_data = st.data_editor(m_df, hide_index=True)
        sel_lrs = selected_data[selected_data["Select"] == True]
        if not sel_lrs.empty:
            st.metric("Selected Bill Total", f"₹{sel_lrs['Freight'].sum():,.0f}")
            # PDF logic can be added here similarly

# P&L REPORT DOWNLOAD
elif menu == "P&L Report":
    st.header("📉 Profit & Loss Summary")
    st.write("Click below to download the detailed P&L statement of Virat Logistics.")
    st.download_button("📥 Download P&L Statement (PDF)", pdf_pl_report(df_t, df_a), "PL_Report.pdf")

# LEDGERS
elif menu == "Party Ledger":
    st.header("🏢 Party Ledger")
    b = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total"})
    p = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Paid"})
    l = pd.merge(b, p, on="Name", how="left").fillna(0)
    l["Due"] = l["Total"] - l["Paid"]
    st.table(l)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Ledger")
    h = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    w = h.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total"})
    p = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Paid"})
    l = pd.merge(w, p, on="Name", how="left").fillna(0)
    l["Balance"] = l["Total"] - l["Paid"]
    st.table(l)

# TRANSACTIONS & EXPENSES
elif menu == "Transactions":
    st.header("💰 Payment Entry")
    with st.form("p"):
        nm = st.text_input("Name"); cat = st.selectbox("Type", ["Party", "Broker"]); am = st.number_input("Amt")
        if st.form_submit_button("Save"):
            save_to_gs("payments", [str(date.today()), nm, cat, am, "Cash"]); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Office Expense")
    with st.form("ad"):
        am = st.number_input("Amt"); rem = st.text_input("Remarks")
        if st.form_submit_button("Save"):
            save_to_gs("admin", [str(date.today()), "Other", am, rem]); st.rerun()
