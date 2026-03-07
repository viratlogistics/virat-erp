import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. SETTINGS & THEME ---
st.set_page_config(page_title="Virat Logistics Ultimate ERP", layout="wide", page_icon="🚚")

st.markdown("""
    <style>
    .main { background-color: #f4f7f6; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #28a745; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CLOUD CONNECTION ---
def get_gspread_client():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Google Sheets Connection Error: {e}")
        return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

sh = None
if client:
    try:
        sh = client.open(SHEET_NAME)
    except:
        st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili. Check sharing permissions.")
        st.stop()

# --- 3. DATA UTILITIES (LEAK-PROOF) ---
def load_data(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        df = pd.DataFrame(ws.get_all_records())
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save_data(ws_name, row):
    try:
        sh.worksheet(ws_name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

def update_data(ws_name, lr_no, row):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [row], value_input_option='USER_ENTERED')
            return True
        return False
    except: return False

def delete_data(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row)
            return True
        return False
    except: return False

# --- 4. DATA REFRESH ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
if sh:
    df_t = load_data("trips")
    df_p = load_data("payments")
    df_a = load_data("admin")
    
    # Numeric Casting
    for c in ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "Other", "DriverExp"]:
        if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
else: st.stop()

# --- 5. PDF ENGINE (PROFESSIONAL DESIGN) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(0, 51, 102)
        self.cell(190, 10, 'VIRAT LOGISTICS', ln=True, align='C')
        self.set_font('Arial', 'I', 10)
        self.cell(190, 5, 'Professional Fleet & Transport Solutions', ln=True, align='C')
        self.ln(10)

def gen_lr_pdf(row):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, f"LR NO: {row['LR']}", 1); pdf.cell(95, 10, f"DATE: {row['Date']}", 1, ln=True)
    pdf.ln(5)
    pdf.cell(190, 10, f"BILLING PARTY: {row['Party']}", 1, ln=True)
    pdf.cell(95, 10, f"FROM: {row['From']}", 1); pdf.cell(95, 10, f"TO: {row['To']}", 1, ln=True)
    pdf.cell(95, 10, f"VEHICLE: {row['Vehicle']}", 1); pdf.cell(95, 10, f"MATERIAL: {row['Material']}", 1, ln=True)
    pdf.ln(10); pdf.set_font("Arial", 'B', 14)
    pdf.cell(140, 12, "GRAND TOTAL FREIGHT ", 1, 0, 'R'); pdf.cell(50, 12, f"Rs. {row['Freight']}/-", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def gen_invoice_pdf(party, df_sel, total):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14); pdf.cell(190, 10, f"MONTHLY INVOICE: {party}", ln=True, align='C')
    pdf.ln(5); pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 10, "Date", 1); pdf.cell(30, 10, "LR No", 1); pdf.cell(35, 10, "Vehicle", 1); pdf.cell(70, 10, "Route", 1); pdf.cell(30, 10, "Amount", 1, ln=True)
    pdf.set_font("Arial", '', 9)
    for _, r in df_sel.iterrows():
        pdf.cell(25, 10, str(r['Date']), 1); pdf.cell(30, 10, str(r['LR']), 1); pdf.cell(35, 10, str(r['Vehicle']), 1); pdf.cell(70, 10, f"{r['From']}-{r['To']}", 1); pdf.cell(30, 10, str(r['Freight']), 1, ln=True)
    pdf.set_font("Arial", 'B', 12); pdf.cell(160, 12, "TOTAL BILLABLE AMOUNT ", 1, 0, 'R'); pdf.cell(30, 12, f"{total:,.0f}", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

# --- 6. AUTHENTICATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔐 Virat Logistics ERP Login")
    with st.form("L"):
        u, p = st.text_input("User ID"), st.text_input("Password", type="password")
        if st.form_submit_button("Access ERP"):
            if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- 7. NAVIGATION ---
menu = st.sidebar.selectbox("🚀 NAVIGATION MENU", 
    ["Dashboard", "Add LR", "LR Manager (Edit/Print)", "Monthly Bill Builder", 
     "Party Ledger", "Broker Ledger", "Vehicle Performance", "P&L Statement", 
     "Cash Flow / Fund Flow", "Admin Expense", "Record Payment"])

# DASHBOARD
if menu == "Dashboard":
    st.title("📊 Financial Control Room")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_exp = df_a["Amount"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Trip Profit", f"₹{df_t['Profit'].sum():,.0f}")
    col2.metric("Total Revenue", f"₹{df_t['Freight'].sum():,.0f}")
    col3.metric("Net Cashflow", f"₹{(p_in - b_out - adm_exp):,.0f}")
    
    st.divider()
    st.subheader("Monthly Revenue Trend")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        st.area_chart(df_t.groupby(df_t['Date'].dt.strftime('%m-%Y'))['Freight'].sum())

# ADD LR
elif menu == "Add LR":
    st.header("📝 Consignment Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("add_lr", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: d, party, cnm = st.date_input("Date"), st.text_input("Party*"), st.text_input("Consignor")
        with c2: v_no, fl, tl = st.text_input("Vehicle*"), st.text_input("From"), st.text_input("To")
        with c3: fr, h_c, br = st.number_input("Freight*"), st.number_input("Hired Charges"), st.text_input("Broker")
        if st.form_submit_button("Save Trip"):
            if party and v_no and fr > 0:
                prof = (fr - h_c) if v_type == "Hired" else fr
                row = [str(d), f"LR-{len(df_t)+1001}", v_type, party, cnm, "", "", "", "", "", "", 0, v_no, "Driver", br, fl, tl, fr, h_c, 0, 0, 0, 0, prof]
                if save_data("trips", row): st.success("Trip Saved!"); st.rerun()

# LR MANAGER
elif menu == "LR Manager (Edit/Print)":
    st.header("🔍 Search and Manage Records")
    sq = st.text_input("Quick Search (LR, Vehicle, Party)")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"edit_f_{i}_{r['LR']}"):
                ec1, ec2, ec3 = st.columns(3)
                up = ec1.text_input("Party", r['Party']); uv = ec1.text_input("Vehicle", r['Vehicle'])
                uf = ec2.number_input("Freight", value=float(r['Freight'])); uh = ec2.number_input("Hired", value=float(r['HiredCharges']))
                ufl = ec3.text_input("From", r['From']); utl = ec3.text_input("To", r['To'])
                if st.form_submit_button("Update Record"):
                    upd = list(r.values); upd[3], upd[12], upd[17], upd[18], upd[15], upd[16] = up, uv, uf, uh, ufl, utl
                    if update_data("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            
            p1, p2 = st.columns(2)
            p1.download_button("📥 Print LR PDF", gen_lr_pdf(r), f"{r['LR']}.pdf", key=f"pdf_btn_{i}")
            if p2.button(f"🗑️ Delete {r['LR']}", key=f"del_btn_{i}"):
                if delete_data("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# MONTHLY BILL BUILDER
elif menu == "Monthly Bill Builder":
    st.header("📅 Monthly Invoice Builder")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        sp = st.selectbox("Select Party", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy()
        m_df.insert(0, "Select", True)
        edited = st.data_editor(m_df, hide_index=True, key="bill_editor")
        sel_trips = edited[edited["Select"] == True]
        if not sel_trips.empty:
            total = sel_trips['Freight'].sum()
            st.metric("Total Selected Freight", f"₹{total:,.0f}")
            st.download_button("📥 Print Monthly Invoice", gen_invoice_pdf(sp, sel_trips, total), f"Invoice_{sp}.pdf")

# PROFIT & LOSS STATEMENT
elif menu == "P&L Statement":
    st.header("📉 Professional Profit & Loss Account")
    rev = df_t['Freight'].sum(); hire = df_t['HiredCharges'].sum(); admin = df_a['Amount'].sum()
    gp = rev - hire; np = gp - admin
    
    st.table(pd.DataFrame({
        "Particulars": ["Gross Revenue", "Market Payouts (-)", "Gross Profit", "Office Expenses (-)", "NET PROFIT"],
        "Amount (INR)": [f"₹{rev:,.2f}", f"₹{hire:,.2f}", f"₹{gp:,.2f}", f"₹{admin:,.2f}", f"₹{np:,.2f}"]
    }))
    
    pdf_pl = PDF(); pdf_pl.add_page(); pdf_pl.set_font("Arial", 'B', 16); pdf_pl.cell(190, 10, "P&L Statement", ln=True, align='C')
    pdf_pl.set_font("Arial", '', 12); pdf_pl.cell(100, 10, f"Gross Profit: {gp:,.2f}", ln=True); pdf_pl.cell(100, 10, f"Net Profit: {np:,.2f}", ln=True)
    st.download_button("📥 Download Full P&L Report", pdf_pl.output(dest='S').encode('latin-1'), "PL_Report.pdf")

# CASH FLOW / FUND FLOW
elif menu == "Cash Flow / Fund Flow":
    st.header("🌊 Cash Flow & Receivables Analysis")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Receivables (Party Se Aane Wale)")
        due = df_t['Freight'].sum() - p_in
        st.metric("Pending from Parties", f"₹{due:,.0f}", delta="Action Required", delta_color="inverse")
    with c2:
        st.subheader("Payables (Broker Ko Dene Wale)")
        pay = df_t['HiredCharges'].sum() - b_out
        st.metric("Pending to Market", f"₹{pay:,.0f}", delta="Liabilities")

# VEHICLE PERFORMANCE
elif menu == "Vehicle Performance":
    st.header("🚛 Own Vehicle Efficiency")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index()
        st.dataframe(vr.rename(columns={"LR": "Trips", "Freight": "Revenue"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])

# LEDGERS
elif menu == "Party Ledger":
    st.header("🏢 Party Accounts")
    b = df_t.groupby("Party")["Freight"].sum().reset_index()
    r = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Name":"Party"})
    l = pd.merge(b, r, on="Party", how="left").fillna(0)
    l["Balance"] = l["Freight"] - l["Amount"]
    st.dataframe(l.rename(columns={"Freight": "Total Billed", "Amount": "Total Received"}), use_container_width=True)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Market Account")
    h = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    w = h.groupby("Broker")["HiredCharges"].sum().reset_index()
    p = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Name":"Broker"})
    l = pd.merge(w, p, on="Broker", how="left").fillna(0)
    l["Balance"] = l["HiredCharges"] - l["Amount"]
    st.dataframe(l.rename(columns={"HiredCharges": "Work Total", "Amount": "Paid Total"}), use_container_width=True)

# TRANSACTIONS
elif menu == "Record Payment":
    st.header("💰 Money Receipt / Payment")
    with st.form("tr"):
        nms = list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist()))
        snm = st.selectbox("Select Name", nms)
        cat = st.selectbox("Category", ["Party", "Broker"])
        am, md = st.number_input("Amount"), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Record Entry"):
            if save_data("payments", [str(date.today()), snm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Office Admin Expense")
    with st.form("exp"):
        ec = st.selectbox("Category", ["Rent", "Salary", "Office", "Other"])
        ea, er = st.number_input("Amount"), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            if save_data("admin", [str(date.today()), ec, ea, er]): st.success("Saved!"); st.rerun()
