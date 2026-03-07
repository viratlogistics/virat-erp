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

# --- 2. DATA UTILITIES (LEAK-PROOF LOGIC) ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # Cleaning: Remove spaces that break ledger matching
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

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

# --- 3. DATA REFRESH & NUMERIC CONVERSION ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")

    # Safety: Ensure columns exist
    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    
    # Numeric Casting
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

# --- 4. PDF GENERATORS ---
def create_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20); pdf.set_text_color(180, 0, 0)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 5, "TRANSPORT & FLEET MANAGEMENT", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, f" LR NO: {row['LR']}", 1); pdf.cell(95, 10, f" DATE: {row['Date']}", 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 10)
    pdf.cell(190, 8, f" BILLING PARTY: {row['Party']}", 1, ln=True)
    pdf.cell(95, 8, f" FROM: {row['From']}", 1); pdf.cell(95, 8, f" TO: {row['To']}", 1, ln=True)
    pdf.cell(95, 8, f" VEHICLE: {row['Vehicle']}", 1); pdf.cell(95, 8, f" WEIGHT: {row['Weight']} MT", 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 14)
    pdf.cell(140, 12, " TOTAL FREIGHT AMOUNT", 1, 0, 'R'); pdf.cell(50, 12, f" {row['Freight']}/-", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def create_pl_pdf(df_t, df_a):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(190, 10, "VIRAT LOGISTICS - PROFIT & LOSS", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", '', 12)
    pdf.cell(100, 10, "Total Freight Revenue:"); pdf.cell(90, 10, f"Rs. {df_t['Freight'].sum():,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Total Hired Charges (-):"); pdf.cell(90, 10, f"Rs. {df_t['HiredCharges'].sum():,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Total Diesel & Exp (-):"); pdf.cell(90, 10, f"Rs. {(df_t['Diesel'].sum() + df_t['Toll'].sum()):,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Total Admin/Office (-):"); pdf.cell(90, 10, f"Rs. {df_a['Amount'].sum():,.2f}", ln=True, align='R')
    pdf.ln(5); pdf.set_font("Arial", 'B', 14)
    pdf.cell(100, 12, "NET PROFIT:", 1); pdf.cell(90, 12, f"Rs. {df_t['Profit'].sum() - df_a['Amount'].sum():,.2f}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics Secure Login")
    with st.form("L"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if u == "admin" and p == "1234":
                st.session_state.login = True; st.rerun()
            else: st.error("Access Denied")
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("Main Menu", 
    ["📊 Dashboard", "➕ Add LR", "🔍 LR Manager (Edit/Del/Print)", "📅 Monthly Bill Builder", 
     "🏢 Party Ledger", "🤝 Broker Ledger", "🚛 Vehicle Performance", "📈 P&L Statement",
     "💰 Party Receipt", "💸 Broker Payment", "🏢 Admin Expense"])

# --- DASHBOARD & CASH FLOW ---
if menu == "📊 Dashboard":
    st.title("📊 Financial Summary & Cash Flow")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_out = df_a["Amount"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Trip Profit", f"₹{df_t['Profit'].sum():,.0f}")
    col2.metric("Total Cash Flow (In)", f"₹{p_in:,.0f}")
    col3.metric("Total Expenses (Out)", f"₹{(b_out + adm_out):,.0f}")
    
    st.divider()
    st.subheader("Fund Flow Summary")
    c1, c2 = st.columns(2)
    c1.metric("Party Outstandings", f"₹{(df_t['Freight'].sum() - p_in):,.0f}")
    c2.metric("Market/Broker Payables", f"₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# --- ADD LR ---
elif menu == "➕ Add LR":
    st.header("📝 Create New Consignment")
    v_type = st.radio("Vehicle Selection", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("add_lr", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            lr_id = f"LR-{len(df_t)+1001}"
            pty = st.text_input("Party Name*")
            cnm, cgst, cadd = st.text_input("Consignor"), st.text_input("Consignor GST"), st.text_area("Consignor Address")
        with f2:
            eenm, eegst, eeadd = st.text_input("Consignee"), st.text_input("Consignee GST"), st.text_area("Consignee Address")
            v_no, fl, tl = st.text_input("Vehicle No*"), st.text_input("From"), st.text_input("To")
        with f3:
            mat, wt = st.text_input("Material"), st.number_input("Weight (MT)", 0.0)
            fr = st.number_input("Freight Amount*", 0.0)
            br = st.text_input("Broker", disabled=(v_type=="Own Fleet"))
            if v_type == "Market Hired":
                hchg, dsl, de, tx, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else:
                hchg, dsl, de, tx, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll/Tax"), st.number_input("Other")
        
        if st.form_submit_button("🚀 Save Trip"):
            if pty and v_no and fr > 0:
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                p_val = (fr - hchg) if t_val == "Hired" else (fr - (dsl+de+tx+ot))
                row = [str(d), lr_id, t_val, pty, cnm, cgst, cadd, eenm, eegst, eeadd, mat, wt, v_no, "Driver", br, fl, tl, fr, hchg, dsl, de, tx, ot, p_val]
                if save_ws("trips", row): st.success("Saved Successfully!"); st.rerun()

# --- LR MANAGER (EDIT/DELETE/PRINT) ---
elif menu == "🔍 LR Manager (Edit/Del/Print)":
    st.header("🔍 Search and Manage Trip Records")
    sq = st.text_input("Search (LR, Vehicle, Party)")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"e_f_{i}_{r['LR']}"):
                ec1, ec2, ec3 = st.columns(3)
                up = ec1.text_input("Party", r['Party']); uv = ec1.text_input("Vehicle", r['Vehicle'])
                ucnm = ec2.text_input("Consignor", r['Consignor']); uce = ec2.text_input("Consignee", r['Consignee'])
                uf = ec3.number_input("Freight", value=float(r['Freight'])); uh = ec3.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("Update Data"):
                    upd = list(r.values); upd[3], upd[12], upd[4], upd[7], upd[17], upd[18] = up, uv, ucnm, uce, uf, uh
                    upd[23] = (uf - uh) if r['Type']=="Hired" else (uf - (r['Diesel']+r['Toll']+r['DriverExp']+r['Other']))
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            st.download_button("📥 Print PDF", create_lr_pdf(r), f"{r['LR']}.pdf")
            if st.button(f"🗑️ Delete {r['LR']}", key=f"d_b_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# --- MONTHLY BILL (LR SELECTION FEATURE) ---
elif menu == "📅 Monthly Bill Builder":
    st.header("📅 Monthly Invoice (Select LRs)")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        sp = st.selectbox("Select Party", df_t["Party"].unique())
        m_list = df_t[df_t['Party'] == sp]['Date'].dt.strftime('%B %Y').unique()
        if len(m_list) > 0:
            sm = st.selectbox("Select Month", m_list)
            m_df = df_t[(df_t['Party'] == sp) & (df_t['Date'].dt.strftime('%B %Y') == sm)].copy()
            st.write("Tick LRs to include in the bill:")
            m_df.insert(0, "Select", True)
            edited = st.data_editor(m_df, hide_index=True)
            sel_trips = edited[edited["Select"] == True]
            if not sel_trips.empty:
                st.metric("Total Selected Billing", f"₹{sel_trips['Freight'].sum():,.0f}")

# --- PROFIT & LOSS ---
elif menu == "📈 P&L Statement":
    st.header("📈 Financial Performance Report")
    st.download_button("📥 Download Full P&L Report (PDF)", create_pl_pdf(df_t, df_a), "PL_Report.pdf")
    st.table(pd.DataFrame({
        "Head": ["Total Revenue", "Market Payables", "Fleet Expenses", "Admin Expenses", "Net Profit"],
        "Amount": [df_t['Freight'].sum(), df_t['HiredCharges'].sum(), (df_t['Diesel'].sum()+df_t['Toll'].sum()), df_a['Amount'].sum(), (df_t['Profit'].sum()-df_a['Amount'].sum())]
    }))

# --- VEHICLE PERFORMANCE (OWN ONLY) ---
elif menu == "🚛 Vehicle Performance":
    st.header("🚛 Own Vehicle Performance Analysis")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index().rename(columns={"LR": "Trips", "Freight": "Revenue"})
        st.dataframe(vr.style.format({"Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])
    else: st.info("Own fleet data not found.")

# --- LEDGERS ---
elif menu == "🏢 Party Ledger":
    st.header("🏢 Party Accounts")
    b = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total"})
    p = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Paid"})
    l = pd.merge(b, p, on="Name", how="left").fillna(0)
    l["Balance"] = l["Total"] - l["Paid"]
    st.table(l)

elif menu == "🤝 Broker Ledger":
    st.header("🤝 Broker Market Account")
    h = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not h.empty:
        w = h.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total"})
        p = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Paid"})
        bl = pd.merge(w, p, on="Name", how="left").fillna(0)
        bl["Outstanding"] = bl["Total"] - bl["Paid"]
        st.table(bl)

# --- TRANSACTIONS ---
elif menu in ["💰 Party Receipt", "💸 Broker Payment"]:
    cat = "Party" if "Party" in menu else "Broker"
    st.header(f"💰 Record {cat} Payment")
    with st.form("pay"):
        nms = df_t[cat].unique() if not df_t.empty else []
        snm = st.selectbox("Select Name", nms)
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Bank", "Cash", "Cheque"])
        if st.form_submit_button("Record"):
            if save_ws("payments", [str(date.today()), snm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "🏢 Admin Expense":
    st.header("🏢 Office Admin Expense")
    with st.form("exp"):
        ec = st.selectbox("Category", ["Rent", "Salary", "Office", "Other"])
        ea, er = st.number_input("Amount", 0.0), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            if save_ws("admin", [str(date.today()), ec, ea, er]): st.success("Saved!"); st.rerun()
