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

# --- 2. DATA UTILITIES ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        return df
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

# --- 3. REFRESH DATA ---
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

# --- 4. PDF ENGINE (LEDGER & REPORTS) ---
def create_ledger_pdf(name, type_label, trips_df, payments_df, balance):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(190, 10, f"ACCOUNT LEDGER: {name} ({type_label})", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.cell(190, 10, f"Date Generated: {date.today()}", ln=True, align='R')
    pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "Date", 1, 0, 'C', True); pdf.cell(40, 10, "LR/Ref", 1, 0, 'C', True); pdf.cell(60, 10, "Particulars", 1, 0, 'C', True)
    pdf.cell(30, 10, "Debit", 1, 0, 'C', True); pdf.cell(30, 10, "Credit", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 9)
    # Adding Trips (Debits for Party, Credits for Broker)
    total_bill = 0; total_paid = 0
    for _, r in trips_df.iterrows():
        amt = r['Freight'] if type_label == "Party" else r['HiredCharges']
        total_bill += amt
        pdf.cell(30, 8, str(r['Date']), 1); pdf.cell(40, 8, str(r['LR']), 1); pdf.cell(60, 8, f"{r['Vehicle']} | {r['From']}-{r['To']}", 1)
        if type_label == "Party": pdf.cell(30, 8, f"{amt:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
        else: pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{amt:,.0f}", 1, 1)
    # Adding Payments
    for _, p in payments_df.iterrows():
        amt = p['Amount']; total_paid += amt
        pdf.cell(30, 8, str(p['Date']), 1); pdf.cell(40, 8, "Payment", 1); pdf.cell(60, 8, f"By {p['Mode']}", 1)
        if type_label == "Party": pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{amt:,.0f}", 1, 1)
        else: pdf.cell(30, 8, f"{amt:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(130, 10, "CLOSING BALANCE", 1, 0, 'R', True); pdf.cell(60, 10, f"Rs. {balance:,.2f}", 1, 1, 'C', True)
    return pdf.output(dest='S').encode('latin-1')

def create_pl_pdf(df_t, df_a):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18); pdf.cell(190, 10, "VIRAT LOGISTICS - P&L REPORT", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", '', 12)
    rev = df_t['Freight'].sum(); hire = df_t['HiredCharges'].sum(); admin = df_a['Amount'].sum()
    pdf.cell(100, 10, "Gross Freight Revenue (+):"); pdf.cell(90, 10, f"Rs. {rev:,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Market Hired Payouts (-):"); pdf.cell(90, 10, f"Rs. {hire:,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Office Admin Expenses (-):"); pdf.cell(90, 10, f"Rs. {admin:,.2f}", ln=True, align='R')
    pdf.ln(5); pdf.set_font("Arial", 'B', 14)
    pdf.cell(100, 12, "NET BUSINESS PROFIT:", 1); pdf.cell(90, 12, f"Rs. {(rev-hire-admin):,.2f}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Portal")
    with st.form("L"):
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Access"):
            if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("Main Menu", ["📊 Dashboard", "➕ Add LR", "🔍 LR Manager (Edit/Print)", "📅 Monthly Bill Builder", "🏢 Party Ledger (PDF)", "🤝 Broker Ledger (PDF)", "🚛 Vehicle Profit", "📉 P&L Report", "💰 Transactions", "🏢 Office Expense"])

# DASHBOARD (FUND FLOW FIX)
if menu == "📊 Dashboard":
    st.title("📊 Cash Flow & Fund Management")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_out = df_a["Amount"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Cash Collected (In)", f"₹{p_in:,.0f}")
    col2.metric("Total Expenses (Out)", f"₹{(b_out + adm_out):,.0f}")
    col3.metric("Net Cash in Hand", f"₹{(p_in - b_out - adm_out):,.0f}")
    
    st.divider()
    st.subheader("Fund Flow Status")
    c1, c2 = st.columns(2)
    # FUND FLOW: Real Pending Receivables and Payables
    c1.info(f"Receivables from Parties: ₹{(df_t['Freight'].sum() - p_in):,.0f}")
    c2.warning(f"Market Payables: ₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# ADD LR
elif menu == "➕ Add LR":
    st.header("📝 Create Trip Record")
    v_type = st.radio("Trip Type", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("add_lr", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today()); lr_id = f"LR-{len(df_t)+1001}"
            pty = st.text_input("Party Name*"); cnm = st.text_input("Consignor")
        with f2:
            eenm = st.text_input("Consignee"); v_no = st.text_input("Vehicle No*")
            fl, tl = st.text_input("From"), st.text_input("To")
        with f3:
            mat, wt = st.text_input("Material"), st.number_input("Weight (MT)", 0.0)
            fr = st.number_input("Freight Amount*", 0.0)
            br = st.text_input("Broker", disabled=(v_type=="Own Fleet"))
            if v_type == "Market Hired": h_c, dsl, de, tx, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else: h_c, dsl, de, tx, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save Trip"):
            if pty and v_no and fr > 0:
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                p_val = (fr - h_c) if t_val == "Hired" else (fr - (dsl+de+tx+ot))
                row = [str(d), lr_id, t_val, pty, cnm, "", "", eenm, "", "", mat, wt, v_no, "Driver", br, fl, tl, fr, h_c, dsl, de, tx, ot, p_val]
                if save_ws("trips", row): st.success("Saved Successfully!"); st.rerun()

# LR MANAGER
elif menu == "🔍 LR Manager (Edit/Print)":
    st.header("🔍 Search and Manage Trip Records")
    sq = st.text_input("Search LR/Vehicle/Party")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"edit_f_{i}_{r['LR']}"):
                ec1, ec2, ec3 = st.columns(3)
                up = ec1.text_input("Party", r['Party']); uv = ec1.text_input("Vehicle", r['Vehicle'])
                ucnm = ec2.text_input("Consignor", r['Consignor']); uce = ec2.text_input("Consignee", r['Consignee'])
                uf = ec3.number_input("Freight", value=float(r['Freight'])); uh = ec3.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("✅ Update Data"):
                    upd = list(r.values); upd[3], upd[12], upd[4], upd[7], upd[17], upd[18] = up, uv, ucnm, uce, uf, uh
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            st.download_button("📥 Print LR PDF", load_ws("trips"), key=f"p_{i}") # PDF Function integration
            if st.button(f"🗑️ Delete Record {r['LR']}", key=f"del_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# MONTHLY BILL BUILDER
elif menu == "📅 Monthly Bill Builder":
    st.header("📅 Monthly Invoice Builder")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        sp = st.selectbox("Select Party", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy()
        m_df.insert(0, "Select", True)
        edited = st.data_editor(m_df, hide_index=True)
        sel_trips = edited[edited["Select"] == True]
        if not sel_trips.empty:
            st.metric("Bill Total", f"₹{sel_trips['Freight'].sum():,.0f}")

# PARTY LEDGER (PDF)
elif menu == "🏢 Party Ledger (PDF)":
    st.header("🏢 Detailed Party Ledger (Download)")
    if not df_t.empty:
        p_name = st.selectbox("Choose Party", df_t["Party"].unique())
        p_trips = df_t[df_t["Party"] == p_name]
        p_payments = df_p[(df_p["Name"] == p_name) & (df_p["Category"] == "Party")]
        balance = p_trips["Freight"].sum() - p_payments["Amount"].sum()
        st.subheader(f"Current Outstanding: ₹{balance:,.0f}")
        st.download_button("📥 Download Detailed Ledger PDF", create_ledger_pdf(p_name, "Party", p_trips, p_payments, balance), f"Ledger_{p_name}.pdf")
        st.dataframe(p_trips[["Date", "LR", "Vehicle", "From", "To", "Freight"]])

# BROKER LEDGER (PDF)
elif menu == "🤝 Broker Ledger (PDF)":
    st.header("🤝 Detailed Broker Ledger (Download)")
    h_df = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not h_df.empty:
        b_name = st.selectbox("Choose Broker", h_df["Broker"].unique())
        b_trips = h_df[h_df["Broker"] == b_name]
        b_payments = df_p[(df_p["Name"] == b_name) & (df_p["Category"] == "Broker")]
        balance = b_trips["HiredCharges"].sum() - b_payments["Amount"].sum()
        st.subheader(f"Total Balance Payable: ₹{balance:,.0f}")
        st.download_button("📥 Download Detailed Broker Ledger PDF", create_ledger_pdf(b_name, "Broker", b_trips, b_payments, balance), f"Broker_{b_name}.pdf")
        st.dataframe(b_trips[["Date", "LR", "Vehicle", "From", "To", "HiredCharges"]])

# P&L REPORT
elif menu == "📉 P&L Report":
    st.header("📉 Profit & Loss Performance")
    st.download_button("📥 Download Full P&L Report PDF", create_pl_pdf(df_t, df_a), "PL_Statement.pdf")
    st.table(pd.DataFrame({
        "Financial Head": ["Total Revenue", "Market Payables", "Fleet Costs", "Admin Expense", "Net Profit"],
        "Amount": [df_t['Freight'].sum(), df_t['HiredCharges'].sum(), (df_t['Diesel'].sum()+df_t['Toll'].sum()), df_a['Amount'].sum(), (df_t['Profit'].sum()-df_a['Amount'].sum())]
    }))

# VEHICLE PERFORMANCE (OWN ONLY)
elif menu == "🚛 Vehicle Performance":
    st.header("🚛 Own Vehicle Profitability")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index().rename(columns={"LR": "Trips", "Freight": "Revenue"})
        st.dataframe(vr.style.format({"Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])

# TRANSACTIONS
elif menu == "💰 Transactions":
    st.header("💰 Payment Entry")
    with st.form("pay"):
        nms = df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist()
        snm = st.selectbox("Select Name", list(set(nms)))
        cat = st.selectbox("Category", ["Party", "Broker"])
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Record Payment"):
            if save_ws("payments", [str(date.today()), snm, cat, am, md]): st.success("Saved!"); st.rerun()

# OFFICE EXPENSE
elif menu == "🏢 Office Expense":
    st.header("🏢 Admin Expenses")
    with st.form("exp"):
        ec = st.selectbox("Category", ["Rent", "Salary", "Stationary", "Other"])
        ea, er = st.number_input("Amount", 0.0), st.text_input("Remarks")
        if st.form_submit_button("Save Expense"):
            if save_ws("admin", [str(date.today()), ec, ea, er]): st.success("Saved!"); st.rerun()
