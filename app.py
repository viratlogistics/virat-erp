import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. CONFIGURATION & CLOUD CONNECTION ---
st.set_page_config(page_title="Virat Logistics Master ERP", layout="wide", page_icon="🚚")

# Custom CSS for Professional Look
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e1e4e8; }
    .stExpander { border: 1px solid #d1d5da; border-radius: 8px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

def get_gspread_client():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

sh = None
if client:
    try:
        sh = client.open(SHEET_NAME)
    except Exception:
        st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili. Service email ko Editor banayein.")
        st.stop()

# --- 2. DATA UTILITIES (CLEAN & SECURE) ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # Leak-proof: Remove leading/trailing spaces from all text columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        return df
    except:
        return pd.DataFrame()

def save_ws(ws_name, row_list):
    try:
        ws = sh.worksheet(ws_name)
        ws.append_row(row_list, value_input_option='USER_ENTERED')
        return True
    except: return False

def update_ws(ws_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row], value_input_option='USER_ENTERED')
            return True
        return False
    except: return False

def delete_ws(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row)
            return True
        return False
    except: return False

# --- 3. DATA LOADING & NUMERIC CONVERSION ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")

    # Safety: Create missing columns for older data rows
    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    
    # Accurate Numeric Casting for Calculations
    num_t = ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp", "Other"]
    for c in num_t: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    
    if not df_p.empty:
        df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    else: df_p = pd.DataFrame(columns=cols_p)

    if not df_a.empty:
        df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    else: df_a = pd.DataFrame(columns=cols_a)
else:
    st.stop()

# --- 4. PDF GENERATION ENGINE ---
def create_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 22); pdf.set_text_color(180, 0, 0)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12); pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 10, f" LR NO: {row['LR']}", 1); pdf.cell(95, 10, f" DATE: {row['Date']}", 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 10)
    pdf.cell(190, 8, f" BILLING PARTY: {row['Party']}", 1, ln=True)
    pdf.cell(95, 8, f" FROM: {row['From']}", 1); pdf.cell(95, 8, f" TO: {row['To']}", 1, ln=True)
    pdf.cell(95, 8, f" VEHICLE: {row['Vehicle']}", 1); pdf.cell(95, 8, f" MATERIAL: {row['Material']}", 1, ln=True)
    pdf.ln(10); pdf.set_font("Arial", 'B', 14)
    pdf.cell(140, 12, " TOTAL FREIGHT CHARGES ", 1, 0, 'R'); pdf.cell(50, 12, f" {row['Freight']}/-", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def create_ledger_pdf(name, type_label, trips_df, payments_df, balance):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(190, 10, f"ACCOUNT LEDGER: {name}", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.cell(190, 10, f"Statement Date: {date.today()}", ln=True, align='R')
    pdf.ln(5); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230, 230, 230)
    pdf.cell(25, 10, "Date", 1, 0, 'C', True); pdf.cell(35, 10, "LR No", 1, 0, 'C', True); pdf.cell(70, 10, "Details", 1, 0, 'C', True)
    pdf.cell(30, 10, "Debit", 1, 0, 'C', True); pdf.cell(30, 10, "Credit", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 8)
    for _, r in trips_df.iterrows():
        amt = r['Freight'] if type_label == "Party" else r['HiredCharges']
        pdf.cell(25, 8, str(r['Date']), 1); pdf.cell(35, 8, str(r['LR']), 1); pdf.cell(70, 8, f"{r['Vehicle']} | {r['From']}-{r['To']}", 1)
        if type_label == "Party": pdf.cell(30, 8, f"{amt:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
        else: pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{amt:,.0f}", 1, 1)
    for _, p in payments_df.iterrows():
        pdf.cell(25, 8, str(p['Date']), 1); pdf.cell(35, 8, "PYMT", 1); pdf.cell(70, 8, f"Payment Recv via {p['Mode']}", 1)
        if type_label == "Party": pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1, 1)
        else: pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(130, 10, "CLOSING BALANCE", 1, 0, 'R', True); pdf.cell(60, 10, f"Rs. {balance:,.2f}", 1, 1, 'C', True)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Portal")
    with st.form("L"):
        u = st.text_input("User ID")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Access ERP"):
            if u == "admin" and p == "1234":
                st.session_state.login = True; st.rerun()
            else: st.error("Wrong User/Pass")
    st.stop()

# --- 6. NAVIGATION MENU ---
menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard", "Add LR", "LR Manager (Edit/Del/Print)", "Monthly Bill Builder", "Party Ledger (PDF)", "Broker Ledger (PDF)", "Vehicle Profit", "Office Expense", "Transactions"])

# DASHBOARD (CASH FLOW & FUND FLOW)
if menu == "Dashboard":
    st.title("📊 Cash Flow & Funds")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_out = df_a["Amount"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Trip Profit (Booked)", f"₹{df_t['Profit'].sum():,.0f}")
    c2.metric("Total Cash Collected", f"₹{p_in:,.0f}")
    c3.metric("Net Cashflow", f"₹{(p_in - b_out - adm_out):,.0f}")
    
    st.divider()
    st.subheader("Fund Flow Status")
    f1, f2 = st.columns(2)
    f1.info(f"Total Outstanding from Parties: ₹{(df_t['Freight'].sum() - p_in):,.0f}")
    f2.warning(f"Total Market Payables: ₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# ADD LR
elif menu == "Add LR":
    st.header("📝 Create New Consignment")
    v_type = st.radio("Trip Category", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("add_lr", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("LR Date", date.today()); lr_id = f"LR-{len(df_t)+1001}"
            pty = st.text_input("Billing Party Name*"); cnm = st.text_input("Consignor Name")
        with c2:
            eenm = st.text_input("Consignee Name"); v_no = st.text_input("Vehicle Number*")
            fl, tl = st.text_input("From Location"), st.text_input("To Location")
        with c3:
            mat, wt = st.text_input("Material Desc"), st.number_input("Weight (MT)", 0.0)
            fr = st.number_input("Total Freight*", 0.0)
            br = st.text_input("Broker/Owner Name", disabled=(v_type=="Own Fleet"))
            if v_type == "Market Hired": h_c, dsl, de, tx, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else: h_c, dsl, de, tx, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll/Tax"), st.number_input("Other Exp")
        
        if st.form_submit_button("✅ SAVE & SYNC"):
            if pty and v_no and fr > 0:
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                p_val = (fr - h_c) if t_val == "Hired" else (fr - (dsl+de+tx+ot))
                # Full 24-Column Mapping
                row = [str(d), lr_id, t_val, pty, cnm, "", "", eenm, "", "", mat, wt, v_no, "Driver", br, fl, tl, fr, h_c, dsl, de, tx, ot, p_val]
                if save_ws("trips", row): st.success("Record Saved Successfully!"); st.rerun()

# LR MANAGER (FULL EDIT / DELETE / PRINT)
elif menu == "LR Manager (Edit/Del/Print)":
    st.header("🔍 Search and Manage Trip Records")
    sq = st.text_input("Search (LR No, Vehicle, or Party)")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"edit_lr_{i}_{r['LR']}"):
                ec1, ec2, ec3 = st.columns(3)
                u_p = ec1.text_input("Party", r['Party']); u_v = ec1.text_input("Vehicle", r['Vehicle'])
                u_f = ec2.number_input("Freight", value=float(r['Freight'])); u_h = ec2.number_input("Hired", value=float(r['HiredCharges']))
                u_fl = ec3.text_input("From", r['From']); u_tl = ec3.text_input("To", r['To'])
                if st.form_submit_button("💾 UPDATE"):
                    upd = list(r.values); upd[3], upd[12], upd[17], upd[18], upd[15], upd[16] = u_p, u_v, u_f, u_h, u_fl, u_tl
                    # Re-calc profit
                    upd[23] = (u_f - u_h) if r['Type'] == "Hired" else (u_f - (r['Diesel'] + r['Toll'] + r['DriverExp'] + r['Other']))
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            
            cp1, cp2 = st.columns([1, 1])
            cp1.download_button("📥 Print PDF", create_lr_pdf(r), f"{r['LR']}.pdf", key=f"pdf_{i}")
            if cp2.button(f"🗑️ Delete Record {r['LR']}", key=f"del_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# MONTHLY BILL BUILDER (SELECTION FEATURE)
elif menu == "Monthly Bill Builder":
    st.header("📅 Select LRs for Monthly Bill")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        sp = st.selectbox("Select Party", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy()
        m_df.insert(0, "Select", True)
        edited = st.data_editor(m_df, hide_index=True)
        sel_trips = edited[edited["Select"] == True]
        if not sel_trips.empty:
            st.metric("Total Billing for Selected", f"₹{sel_trips['Freight'].sum():,.0f}")

# LEDGERS (DETAILED PDF DOWNLOAD)
elif menu == "Party Ledger (PDF)":
    st.header("🏢 Party Wise Outstanding & Ledger")
    if not df_t.empty:
        p_name = st.selectbox("Choose Billing Party", df_t["Party"].unique())
        p_trips = df_t[df_t["Party"] == p_name]
        p_pmts = df_p[(df_p["Name"] == p_name) & (df_p["Category"] == "Party")]
        bal = p_trips["Freight"].sum() - p_pmts["Amount"].sum()
        st.subheader(f"Current Balance: ₹{bal:,.2f}")
        st.download_button("📥 Download Detailed Ledger PDF", create_ledger_pdf(p_name, "Party", p_trips, p_pmts, bal), f"Ledger_{p_name}.pdf")
        st.dataframe(p_trips[["Date", "LR", "Vehicle", "Freight"]])

elif menu == "Broker Ledger (PDF)":
    st.header("🤝 Market Broker Payable Ledger")
    h_df = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not h_df.empty:
        b_name = st.selectbox("Choose Broker", h_df["Broker"].unique())
        b_trips = h_df[h_df["Broker"] == b_name]
        b_pmts = df_p[(df_p["Name"] == b_name) & (df_p["Category"] == "Broker")]
        bal = b_trips["HiredCharges"].sum() - b_pmts["Amount"].sum()
        st.subheader(f"Payable Balance: ₹{bal:,.2f}")
        st.download_button("📥 Download Broker Ledger PDF", create_ledger_pdf(b_name, "Broker", b_trips, b_pmts, bal), f"Broker_{b_name}.pdf")
        st.dataframe(b_trips[["Date", "LR", "Vehicle", "HiredCharges"]])

# VEHICLE PERFORMANCE (OWN ONLY)
elif menu == "Vehicle Profit":
    st.header("🚛 Own Vehicle Profitability Analysis")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index().rename(columns={"LR": "Trips", "Freight": "Revenue"})
        st.dataframe(vr.style.format({"Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])

# TRANSACTIONS & OFFICE EXPENSES
elif menu == "Transactions":
    st.header("💰 Money Receipt / Payment Entry")
    with st.form("tr"):
        nms = list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist()))
        snm = st.selectbox("Select Name", nms)
        cat = st.selectbox("Category", ["Party", "Broker"])
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Record Entry"):
            if save_ws("payments", [str(date.today()), snm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "Office Expense":
    st.header("🏢 Admin Expenses")
    with st.form("oe"):
        ec = st.selectbox("Category", ["Rent", "Salary", "Stationary", "Electricity", "Other"])
        am, rem = st.number_input("Amount", 0.0), st.text_input("Remarks")
        if st.form_submit_button("Save Expense"):
            if save_ws("admin", [str(date.today()), ec, am, rem]): st.success("Saved!"); st.rerun()
