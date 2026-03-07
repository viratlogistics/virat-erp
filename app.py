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
        # Get JSON key from Streamlit Secrets
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Connection Error (Check Secrets): {e}")
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
        # Cleaning: Remove hidden spaces from text columns
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

# --- 3. DATA REFRESH & NUMERIC CONVERSION ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")

    # Safety: Column validation
    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    
    # Numeric Casting
    num_t = ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp", "Other"]
    for c in num_t: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    else: df_p = pd.DataFrame(columns=cols_p)

    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    else: df_a = pd.DataFrame(columns=cols_a)
else:
    st.stop()

# --- 4. PDF ENGINE (PROFESSIONAL REPORTS) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(180, 0, 0)
        self.cell(190, 10, 'VIRAT LOGISTICS', ln=True, align='C')
        self.set_font('Arial', 'I', 10); self.set_text_color(0, 0, 0)
        self.cell(190, 5, 'Transport & Fleet Management Solutions', ln=True, align='C')
        self.ln(10)

def gen_lr_pdf(row):
    pdf = PDF(); pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, f" LR NO: {row['LR']}", 1); pdf.cell(95, 10, f" DATE: {row['Date']}", 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 10)
    pdf.cell(190, 10, f" BILLING PARTY: {row['Party']}", 1, ln=True)
    pdf.cell(95, 10, f" FROM: {row['From']}", 1); pdf.cell(95, 10, f" TO: {row['To']}", 1, ln=True)
    pdf.cell(95, 10, f" VEHICLE: {row['Vehicle']}", 1); pdf.cell(95, 10, f" MATERIAL: {row['Material']}", 1, ln=True)
    pdf.ln(10); pdf.set_font("Arial", 'B', 14)
    pdf.cell(140, 12, " GRAND TOTAL FREIGHT", 1, 0, 'R'); pdf.cell(50, 12, f" {row['Freight']}/-", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def gen_ledger_pdf(name, type_label, trips, payments, balance):
    pdf = PDF(); pdf.add_page()
    pdf.set_font("Arial", 'B', 14); pdf.cell(190, 10, f"ACCOUNT LEDGER: {name} ({type_label})", ln=True, align='C')
    pdf.ln(5); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230, 230, 230)
    pdf.cell(25, 10, "Date", 1, 0, 'C', 1); pdf.cell(35, 10, "LR/Ref", 1, 0, 'C', 1); pdf.cell(70, 10, "Description", 1, 0, 'C', 1); pdf.cell(30, 10, "Debit", 1, 0, 'C', 1); pdf.cell(30, 10, "Credit", 1, 1, 'C', 1)
    pdf.set_font("Arial", '', 8)
    for _, r in trips.iterrows():
        amt = r['Freight'] if type_label == "Party" else r['HiredCharges']
        pdf.cell(25, 8, str(r['Date']), 1); pdf.cell(35, 8, str(r['LR']), 1); pdf.cell(70, 8, f"{r['Vehicle']} | {r['From']}-{r['To']}", 1)
        if type_label == "Party": pdf.cell(30, 8, f"{amt:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
        else: pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{amt:,.0f}", 1, 1)
    for _, p in payments.iterrows():
        pdf.cell(25, 8, str(p['Date']), 1); pdf.cell(35, 8, "PYMT", 1); pdf.cell(70, 8, f"Payment via {p['Mode']}", 1)
        if type_label == "Party": pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1, 1)
        else: pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(130, 10, "CLOSING BALANCE", 1, 0, 'R', 1); pdf.cell(60, 10, f"Rs. {balance:,.2f}", 1, 1, 'C', 1)
    return pdf.output(dest='S').encode('latin-1')

def gen_invoice_pdf(party, df_sel, total):
    pdf = PDF(); pdf.add_page()
    pdf.set_font("Arial", 'B', 14); pdf.cell(190, 10, f"MONTHLY INVOICE: {party}", ln=True, align='C')
    pdf.ln(5); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "Date", 1, 0, 'C', 1); pdf.cell(30, 10, "LR No", 1, 0, 'C', 1); pdf.cell(40, 10, "Vehicle", 1, 0, 'C', 1); pdf.cell(60, 10, "Route", 1, 0, 'C', 1); pdf.cell(30, 10, "Amount", 1, 1, 'C', 1)
    pdf.set_font("Arial", '', 9)
    for _, r in df_sel.iterrows():
        pdf.cell(30, 10, str(r['Date']), 1); pdf.cell(30, 10, str(r['LR']), 1); pdf.cell(40, 10, str(r['Vehicle']), 1); pdf.cell(60, 10, f"{r['From']}-{r['To']}", 1); pdf.cell(30, 10, str(r['Freight']), 1, 1)
    pdf.set_font("Arial", 'B', 12); pdf.cell(160, 12, "TOTAL BILLABLE ", 1, 0, 'R', 1); pdf.cell(30, 12, f"{total:,.0f}", 1, 1, 'C', 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Portal")
    with st.form("L"):
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Access ERP"):
            if u == "admin" and p == "1234":
                st.session_state.login = True; st.rerun()
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("Navigate Menu", ["📊 Dashboard", "➕ Add LR", "🔍 LR Manager (Edit/Del/Print)", "📅 Monthly Bill Builder", "🏢 Party Ledger (PDF)", "🤝 Broker Ledger (PDF)", "🚛 Vehicle Performance", "📈 Profit & Loss Account", "💰 Record Payment", "🏢 Office Expense"])

# --- DASHBOARD (CASH & FUND FLOW) ---
if menu == "📊 Dashboard":
    st.title("📊 Cash Flow & Fund Management")
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_exp = df_a["Amount"].sum()
    
    st.subheader("🌊 Cash Flow Summary (Actual Cash)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Collected", f"₹{p_rec:,.0f}")
    c2.metric("Cash Out (Expenses Paid)", f"₹{(b_paid + adm_exp):,.0f}")
    c3.metric("Net Cash in Hand", f"₹{(p_rec - b_paid - adm_exp):,.0f}")
    
    st.divider()
    st.subheader("📂 Fund Flow (Market Balance)")
    f1, f2 = st.columns(2)
    f1.metric("Paisa Lena Hai (Receivables)", f"₹{(df_t['Freight'].sum() - p_rec):,.0f}")
    f2.metric("Paisa Dena Hai (Payables)", f"₹{(df_t['HiredCharges'].sum() - b_paid):,.0f}")

# --- ADD LR ---
elif menu == "➕ Add LR":
    st.header("📝 Create New Consignment")
    v_type = st.radio("Trip Type", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("add_lr", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today()); lr_id = f"LR-{len(df_t)+1001}"
            pty = st.text_input("Party Name*"); cnm = st.text_input("Consignor")
            cadd = st.text_area("Consignor Address")
        with f2:
            eenm = st.text_input("Consignee"); v_no = st.text_input("Vehicle No*")
            fl, tl = st.text_input("From Location"), st.text_input("To Location")
        with f3:
            mat, wt = st.text_input("Material"), st.number_input("Weight (MT)", 0.0)
            fr = st.number_input("Freight Amount*", 0.0)
            br = st.text_input("Broker/Owner", disabled=(v_type=="Own Fleet"))
            if v_type == "Market Hired": h_c, dsl, de, tx, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else: h_c, dsl, de, tx, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save Trip"):
            if pty and v_no and fr > 0:
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                p_val = (fr - h_c) if t_val == "Hired" else (fr - (dsl+de+tx+ot))
                row = [str(d), lr_id, t_val, pty, cnm, "", cadd, eenm, "", "", mat, wt, v_no, "Driver", br, fl, tl, fr, h_c, dsl, de, tx, ot, p_val]
                if save_ws("trips", row): st.success("Saved Successfully!"); st.rerun()

# --- LR MANAGER (EDIT/DELETE/PRINT) ---
elif menu == "🔍 LR Manager (Edit/Del/Print)":
    st.header("🔍 Search and Manage Trip Records")
    sq = st.text_input("Search LR/Vehicle/Party")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"edit_f_{i}_{r['LR']}"):
                ec1, ec2, ec3 = st.columns(3)
                up = ec1.text_input("Party", r['Party']); uv = ec1.text_input("Vehicle", r['Vehicle'])
                ufl = ec2.text_input("From", r['From']); utl = ec2.text_input("To", r['To'])
                uf = ec3.number_input("Freight", value=float(r['Freight'])); uh = ec3.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("Update Records"):
                    upd = list(r.values); upd[3], upd[12], upd[15], upd[16], upd[17], upd[18] = up, uv, ufl, utl, uf, uh
                    upd[23] = (uf - uh) if r['Type']=="Hired" else (uf - (r['Diesel']+r['Toll']+r['DriverExp']+r['Other']))
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            c_p, c_d = st.columns(2)
            c_p.download_button("📥 Print PDF", gen_lr_pdf(r), f"{r['LR']}.pdf", key=f"pdf_bt_{i}")
            if c_d.button(f"🗑️ Delete {r['LR']}", key=f"del_bt_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# --- MONTHLY BILL BUILDER ---
elif menu == "📅 Monthly Bill Builder":
    st.header("📅 Monthly Invoice (Select Trips)")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'], errors='coerce')
        sp = st.selectbox("Select Billing Party", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy()
        m_df.insert(0, "Select", True)
        edited = st.data_editor(m_df, hide_index=True, key="meditor")
        sel_trips = edited[edited["Select"] == True]
        if not sel_trips.empty:
            tot = sel_trips["Freight"].sum()
            st.metric("Total Bill Amount", f"₹{tot:,.0f}")
            st.download_button("📥 Download Monthly Invoice PDF", gen_invoice_pdf(sp, sel_trips, tot), f"Invoice_{sp}.pdf")

# --- ACCOUNT LEDGERS (PDF) ---
elif menu == "🏢 Party Ledger (PDF)":
    st.header("🏢 Detailed Party Ledger Statement")
    sp = st.selectbox("Choose Party", df_t["Party"].unique())
    p_trips = df_t[df_t["Party"] == sp]
    p_pmts = df_p[(df_p["Name"] == sp) & (df_p["Category"] == "Party")]
    bal = p_trips["Freight"].sum() - p_pmts["Amount"].sum()
    st.subheader(f"Current Outstanding: ₹{bal:,.0f}")
    st.download_button("📥 Download Ledger PDF", gen_ledger_pdf(sp, "Party", p_trips, p_pmts, bal), f"Ledger_{sp}.pdf")
    st.dataframe(p_trips[["Date", "LR", "Vehicle", "Freight"]])

elif menu == "🤝 Broker Ledger (PDF)":
    st.header("🤝 Market Broker Ledger Statement")
    h_df = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    sb = st.selectbox("Choose Broker", h_df["Broker"].unique() if not h_df.empty else [])
    if sb:
        b_trips = h_df[h_df["Broker"] == sb]
        b_pmts = df_p[(df_p["Name"] == sb) & (df_p["Category"] == "Broker")]
        bal = b_trips["HiredCharges"].sum() - b_pmts["Amount"].sum()
        st.subheader(f"Total Payable: ₹{bal:,.0f}")
        st.download_button("📥 Download Broker PDF", gen_ledger_pdf(sb, "Broker", b_trips, b_pmts, bal), f"Broker_{sb}.pdf")
        st.dataframe(b_trips[["Date", "LR", "Vehicle", "HiredCharges"]])

# --- PROFIT & LOSS ---
elif menu == "📈 Profit & Loss Account":
    st.header("📉 Financial Performance Statement")
    rev = df_t['Freight'].sum(); hire = df_t['HiredCharges'].sum(); admin = df_a['Amount'].sum()
    st.table(pd.DataFrame({
        "Particulars": ["Gross Freight Revenue", "Market Hired Payouts (-)", "Direct Trip Costs (-)", "Office Admin Expenses (-)", "NET BUSINESS PROFIT"],
        "Amount": [f"₹{rev:,.0f}", f"₹{hire:,.0f}", f"₹{(df_t['Diesel'].sum()+df_t['Toll'].sum()):,.0f}", f"₹{admin:,.0f}", f"₹{(rev-hire-admin):,.0f}"]
    }))

# --- VEHICLE PERFORMANCE (OWN ONLY) ---
elif menu == "🚛 Vehicle Performance":
    st.header("🚛 Own Vehicle Performance Analysis")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index().rename(columns={"LR": "Trips", "Freight": "Revenue"})
        st.dataframe(vr.style.format({"Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])

# --- TRANSACTIONS ---
elif menu == "💰 Record Payment":
    st.header("💰 Money Receipt / Payment Entry")
    with st.form("pay"):
        nms = list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist()))
        snm = st.selectbox("Select Name", nms)
        cat = st.selectbox("Category", ["Party", "Broker"])
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Record Transaction"):
            if save_ws("payments", [str(date.today()), snm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "🏢 Office Expense":
    st.header("🏢 Admin Expenses")
    with st.form("oexp"):
        ct = st.selectbox("Category", ["Rent", "Salary", "Stationary", "Electricity", "Other"])
        am, rem = st.number_input("Amount", 0.0), st.text_input("Remarks")
        if st.form_submit_button("Save Expense"):
            if save_ws("admin", [str(date.today()), ct, am, rem]): st.success("Saved!"); st.rerun()
