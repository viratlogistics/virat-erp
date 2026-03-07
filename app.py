import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. CONFIGURATION & CLOUD CONNECTION ---
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

# --- 2. DATA UTILITIES (LEAK-PROOF & CLEAN) ---
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

# --- 3. DATA REFRESH & NUMERIC CONVERSION ---
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
    
    if not df_p.empty:
        df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    else: df_p = pd.DataFrame(columns=cols_p)

    if not df_a.empty:
        df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    else: df_a = pd.DataFrame(columns=cols_a)
else: st.stop()

# --- 4. PDF GENERATORS ---
def create_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 22); pdf.set_text_color(200, 0, 0)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12); pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 12, f" LR NO: {row['LR']}", 1); pdf.cell(95, 12, f" DATE: {row['Date']}", 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 10)
    pdf.cell(190, 10, f" BILLING PARTY: {row['Party']}", 1, ln=True)
    pdf.cell(95, 10, f" FROM: {row['From']}", 1); pdf.cell(95, 10, f" TO: {row['To']}", 1, ln=True)
    pdf.cell(95, 10, f" VEHICLE: {row['Vehicle']}", 1); pdf.cell(95, 10, f" MATERIAL: {row['Material']}", 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 14)
    pdf.cell(140, 12, " TOTAL FREIGHT ", 1, 0, 'R'); pdf.cell(50, 12, f" Rs. {row['Freight']}/-", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def create_monthly_bill_pdf(party_name, selected_lrs, total_amt):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(190, 10, f"SUMMARY BILL - {party_name}", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 10, "Date", 1); pdf.cell(40, 10, "LR No", 1); pdf.cell(40, 10, "Vehicle", 1); pdf.cell(50, 10, "Route", 1); pdf.cell(30, 10, "Amount", 1, ln=True)
    pdf.set_font("Arial", '', 9)
    for _, r in selected_lrs.iterrows():
        pdf.cell(30, 10, str(r['Date']), 1); pdf.cell(40, 10, str(r['LR']), 1); pdf.cell(40, 10, str(r['Vehicle']), 1); pdf.cell(50, 10, f"{r['From']}-{r['To']}", 1); pdf.cell(30, 10, str(r['Freight']), 1, ln=True)
    pdf.set_font("Arial", 'B', 12); pdf.cell(160, 12, "GRAND TOTAL ", 1, 0, 'R'); pdf.cell(30, 12, f"Rs. {total_amt:,.0f}", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def create_pl_pdf(df_t, df_a):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(190, 10, "VIRAT LOGISTICS - P&L REPORT", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", '', 12)
    rev = df_t['Freight'].sum(); hire = df_t['HiredCharges'].sum(); admin = df_a['Amount'].sum()
    pdf.cell(100, 10, "Total Freight Revenue:"); pdf.cell(90, 10, f"Rs. {rev:,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Total Market Payouts (-):"); pdf.cell(90, 10, f"Rs. {hire:,.2f}", ln=True, align='R')
    pdf.cell(100, 10, "Total Office Expense (-):"); pdf.cell(90, 10, f"Rs. {admin:,.2f}", ln=True, align='R')
    pdf.ln(10); pdf.set_font("Arial", 'B', 14)
    pdf.cell(100, 12, "NET BUSINESS PROFIT:", 1); pdf.cell(90, 12, f"Rs. {(rev-hire-admin):,.2f}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 5. LOGIN ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Portal")
    with st.form("Login"):
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        if st.form_submit_button("Access ERP"):
            if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("Navigate Menu", ["📊 Dashboard", "➕ Add LR", "🔍 LR Manager (Edit/Print)", "📅 Monthly Bill Builder", "🏢 Party Ledger", "🤝 Broker Ledger", "🚛 Vehicle Profit", "📈 P&L Report", "💰 Transactions", "🏢 Office Expense"])

# --- DASHBOARD (CASH FLOW) ---
if menu == "📊 Dashboard":
    st.title("📊 Cash Flow & Performance")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_out = df_a["Amount"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Trip Profit (Billed)", f"₹{df_t['Profit'].sum():,.0f}")
    col2.metric("Cash Collected", f"₹{p_in:,.0f}")
    col3.metric("Net Cash Flow", f"₹{(p_in - b_out - adm_out):,.0f}")
    
    st.divider()
    st.subheader("Asset & Liability Status")
    c1, c2 = st.columns(2)
    c1.info(f"Outstanding from Parties: ₹{(df_t['Freight'].sum() - p_in):,.0f}")
    c2.warning(f"Payable to Market: ₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# --- ADD LR ---
elif menu == "➕ Add LR":
    st.header("📝 Create Trip Record")
    v_type = st.radio("Trip Category", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("lr_entry", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            lr_id = f"LR-{len(df_t)+1001}"
            pty = st.text_input("Billing Party Name*")
            cnm, cgst, cadd = st.text_input("Consignor"), st.text_input("GST"), st.text_area("Address")
        with f2:
            eenm, eegst, eeadd = st.text_input("Consignee"), st.text_input("Consignee GST"), st.text_area("Consignee Add")
            v_no, fl, tl = st.text_input("Vehicle No*"), st.text_input("From"), st.text_input("To")
        with f3:
            mat, wt = st.text_input("Material"), st.number_input("Weight (MT)", 0.0)
            fr = st.number_input("Freight Amount*", 0.0)
            br = st.text_input("Broker", disabled=(v_type=="Own Fleet"))
            if v_type == "Market Hired":
                h_c, dsl, de, tx, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else:
                h_c, dsl, de, tx, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("🚀 SAVE TO CLOUD"):
            if pty and v_no and fr > 0:
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                p_val = (fr - h_c) if t_val == "Hired" else (fr - (dsl+de+tx+ot))
                row = [str(d), lr_id, t_val, pty, cnm, cgst, cadd, eenm, eegst, eeadd, mat, wt, v_no, "Driver", br, fl, tl, fr, h_c, dsl, de, tx, ot, p_val]
                if save_ws("trips", row): st.success("Saved Successfully!"); st.rerun()

# --- LR MANAGER (FIXED BUTTON KEYS) ---
elif menu == "🔍 LR Manager (Edit/Print)":
    st.header("🔍 Search and Manage Trip Records")
    sq = st.text_input("Search LR/Vehicle/Party")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        # Unique keys added to prevent DuplicateElementId error
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"edit_f_{i}_{r['LR']}"):
                ec1, ec2, ec3 = st.columns(3)
                up = ec1.text_input("Party", r['Party']); uv = ec1.text_input("Vehicle", r['Vehicle'])
                ucnm = ec2.text_input("Consignor", r['Consignor']); uce = ec2.text_input("Consignee", r['Consignee'])
                uf = ec3.number_input("Freight", value=float(r['Freight'])); uh = ec3.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("✅ Update Data"):
                    upd = list(r.values); upd[3], upd[12], upd[4], upd[7], upd[17], upd[18] = up, uv, ucnm, uce, uf, uh
                    upd[23] = (uf - uh) if r['Type']=="Hired" else (uf - (r['Diesel']+r['Toll']+r['DriverExp']+r['Other']))
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            
            c_pdf, c_del = st.columns([1, 1])
            # PDF Download button with UNIQUE KEY
            c_pdf.download_button(label="📥 Download PDF", data=create_lr_pdf(r), file_name=f"{r['LR']}.pdf", mime="application/pdf", key=f"pdf_btn_{i}")
            if c_del.button(f"🗑️ Delete Record", key=f"del_btn_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# --- MONTHLY BILL (LR SELECTION & PRINT) ---
elif menu == "📅 Monthly Bill Builder":
    st.header("📅 Create Monthly Summary Invoice")
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
                total_sel = sel_trips['Freight'].sum()
                st.metric("Total Bill Amount", f"₹{total_sel:,.0f}")
                st.download_button("📥 Download Monthly Summary Bill", create_monthly_bill_pdf(sp, sel_trips, total_sel), f"Bill_{sp}_{sm}.pdf", key="m_bill_btn")

# --- P&L REPORT ---
elif menu == "📈 P&L Report":
    st.header("📈 Financial Performance Summary")
    st.write("Generate and download the detailed Profit & Loss Statement for Virat Logistics.")
    st.download_button("📥 Download Full P&L Report (PDF)", create_pl_pdf(df_t, df_a), "PL_Statement.pdf", key="pl_btn")
    st.table(pd.DataFrame({
        "Financial Head": ["Total Revenue", "Market Payables", "Fleet Direct Costs", "Admin/Office Expenses", "Net Business Profit"],
        "Amount": [df_t['Freight'].sum(), df_t['HiredCharges'].sum(), (df_t['Diesel'].sum()+df_t['Toll'].sum()), df_a['Amount'].sum(), (df_t['Profit'].sum()-df_a['Amount'].sum())]
    }))

# --- VEHICLE PERFORMANCE (OWN ONLY) ---
elif menu == "🚛 Vehicle Profit":
    st.header("🚛 Own Vehicle Performance Report")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index().rename(columns={"LR": "Trips", "Freight": "Revenue"})
        st.dataframe(vr.style.format({"Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])
    else: st.info("Own fleet data not found.")

# --- LEDGERS ---
elif menu == "🏢 Party Ledger":
    st.header("🏢 Party Outstanding Ledger")
    b = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total"})
    p = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Paid"})
    l = pd.merge(b, p, on="Name", how="left").fillna(0)
    l["Outstanding"] = l["Total"] - l["Paid"]
    st.table(l.style.format({"Total": "₹{:.0f}", "Paid": "₹{:.0f}", "Outstanding": "₹{:.0f}"}))

elif menu == "🤝 Broker Ledger":
    st.header("🤝 Market Broker Payable Ledger")
    h = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not h.empty:
        w = h.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total"})
        p = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Paid"})
        bl = pd.merge(w, p, on="Name", how="left").fillna(0)
        bl["Balance"] = bl["Total"] - bl["Paid"]
        st.table(bl.style.format({"Total": "₹{:.0f}", "Paid": "₹{:.0f}", "Balance": "₹{:.0f}"}))

# --- TRANSACTIONS & EXPENSES ---
elif menu == "💰 Transactions":
    st.header("💰 Payment/Receipt Entry")
    with st.form("trans_pay"):
        nm = st.selectbox("Select Party/Broker", df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist())
        cat = st.selectbox("Category", ["Party", "Broker"])
        am = st.number_input("Amount", 0.0)
        mo = st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Record Transaction"):
            if save_ws("payments", [str(date.today()), nm, cat, am, mo]): st.success("Recorded!"); st.rerun()

elif menu == "🏢 Office Expense":
    st.header("🏢 Admin & Office Expenses")
    with st.form("adm_exp"):
        ec = st.selectbox("Category", ["Rent", "Salary", "Stationary", "Electricity", "Other"])
        ea = st.number_input("Amount", 0.0); er = st.text_input("Remarks")
        if st.form_submit_button("Save Expense"):
            if save_ws("admin", [str(date.today()), ec, ea, er]): st.success("Saved!"); st.rerun()
