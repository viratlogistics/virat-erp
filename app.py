import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. CONFIGURATION ---
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
sh = client.open(SHEET_NAME) if client else None

# --- 2. CORE UTILITIES ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        df = pd.DataFrame(ws.get_all_records())
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save_ws(ws_name, row_list):
    try:
        sh.worksheet(ws_name).append_row(row_list, value_input_option='USER_ENTERED')
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

# --- 3. DATA REFRESH ---
if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")
    df_d = load_ws("drivers")
    for c in ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp"]:
        if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    if not df_d.empty:
        for c in ["Advance", "Salary"]:
            if c in df_d.columns: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').fillna(0)

# --- 4. PDF GENERATOR ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18); self.cell(190, 10, 'VIRAT LOGISTICS', ln=True, align='C'); self.ln(10)

def gen_ledger_pdf(name, trips, pmts, balance, lbl):
    pdf = PDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, f"LEDGER STATEMENT: {name} ({lbl})", ln=True)
    pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230,230,230)
    pdf.cell(30, 10, "Date", 1, 0, 'C', 1); pdf.cell(40, 10, "Ref", 1, 0, 'C', 1); pdf.cell(60, 10, "Detail", 1, 0, 'C', 1); pdf.cell(30, 10, "Debit", 1, 0, 'C', 1); pdf.cell(30, 10, "Credit", 1, 1, 'C', 1)
    pdf.set_font("Arial", '', 8)
    for _, r in trips.iterrows():
        amt = r['Freight'] if lbl == "Party" else r['HiredCharges']
        pdf.cell(30, 8, str(r['Date']), 1); pdf.cell(40, 8, str(r['LR']), 1); pdf.cell(60, 8, str(r['Vehicle']), 1)
        if lbl == "Party": pdf.cell(30, 8, f"{amt:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
        else: pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{amt:,.0f}", 1, 1)
    for _, p in pmts.iterrows():
        pdf.cell(30, 8, str(p['Date']), 1); pdf.cell(40, 8, "PYMT", 1); pdf.cell(60, 8, p['Mode'], 1)
        if lbl == "Party": pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1, 1)
        else: pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(130, 10, "BALANCE DUE", 1, 0, 'R', 1); pdf.cell(60, 10, f"Rs. {balance:,.2f}", 1, 1, 'C', 1)
    return pdf.output(dest='S').encode('latin-1')
    # --- 5. AUTHENTICATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Access")
    with st.form("L"):
        u, p = st.text_input("Admin ID"), st.text_input("Password", type="password")
        if st.form_submit_button("Enter ERP"):
            if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("🚀 NAVIGATION", ["Dashboard", "Add LR", "LR Manager", "Monthly Bill Builder", "Driver Management", "Party Ledger", "Broker Ledger", "P&L Statement", "Record Transaction", "Office Expense"])

# --- 7. DASHBOARD (CASH & FUND FLOW) ---
if menu == "Dashboard":
    st.title("📊 Cash Flow & Fund Management")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm = df_a["Amount"].sum()
    
    st.subheader("🌊 Cash Flow (Actual Cash In-Hand)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Collected (In)", f"₹{p_in:,.0f}")
    c2.metric("Cash Paid (Out)", f"₹{(b_out + adm):,.0f}")
    c3.metric("Balance Cash", f"₹{(p_in - b_out - adm):,.0f}")
    
    st.divider()
    st.subheader("📂 Fund Flow (Market Balance)")
    f1, f2 = st.columns(2)
    # RECEIVABLES: Freight Billed - Cash In
    f1.metric("Paisa Lena Hai (Receivables)", f"₹{(df_t['Freight'].sum() - p_in):,.0f}", delta="From Parties")
    # PAYABLES: Hired Cost - Cash Out
    f2.metric("Paisa Dena Hai (Payables)", f"₹{(df_t['HiredCharges'].sum() - b_out):,.0f}", delta="To Market/Brokers", delta_color="inverse")

# --- 8. DRIVER MANAGEMENT (NEW) ---
elif menu == "Driver Management":
    st.header("👨‍✈️ Driver Dashboard (Salary & Advance)")
    with st.expander("➕ Record Driver Payment/Attendance"):
        with st.form("driver_form"):
            dn = st.text_input("Driver Name")
            dt = st.date_input("Date", date.today())
            stts = st.selectbox("Status", ["Present", "Absent", "Leave"])
            adv = st.number_input("Advance Paid", 0.0)
            sal = st.number_input("Fixed Monthly Salary", 0.0)
            if st.form_submit_button("Record Data"):
                save_ws("drivers", [str(dt), dn, stts, adv, sal])
                st.success("Driver Data Saved!"); st.rerun()
    
    if not df_d.empty:
        st.subheader("Driver Balance Report")
        # Logic: Advance sum, Max Salary (Fix), Count Present Days
        d_sum = df_d.groupby("Name").agg({"Advance": "sum", "Salary": "max", "Status": lambda x: (x == "Present").sum()}).reset_index()
        d_sum["Earned"] = (d_sum["Salary"] / 30) * d_sum["Status"]
        d_sum["Remaining"] = d_sum["Earned"] - d_sum["Advance"]
        
        st.dataframe(d_sum.style.format({
            "Salary": "₹{:.0f}", "Advance": "₹{:.0f}", "Earned": "₹{:.0f}", "Remaining": "₹{:.0f}"
        }), use_container_width=True)
        # --- 9. PARTY LEDGER (DETAILED DISPLAY & PDF) ---
elif menu == "Party Ledger":
    st.header("🏢 Detailed Party Ledger")
    if not df_t.empty:
        sp = st.selectbox("Choose Party", df_t["Party"].unique())
        p_trips = df_t[df_t["Party"] == sp]
        p_pmts = df_p[(df_p["Name"] == sp) & (df_p["Category"] == "Party")]
        
        # Calculation for Header
        bal = p_trips["Freight"].sum() - p_pmts["Amount"].sum()
        st.subheader(f"Total Outstanding: ₹{bal:,.0f}")
        
        # PDF Download Button
        st.download_button("📥 Download Ledger PDF", gen_ledger_pdf(sp, p_trips, p_pmts, bal, "Party"), f"Ledger_{sp}.pdf", key="p_pdf")
        
        # Displaying Detailed Tables
        st.write("### 🚛 Trip History")
        st.dataframe(p_trips[["Date", "LR", "Vehicle", "From", "To", "Freight"]], use_container_width=True)
        st.write("### 💰 Payment Received History")
        st.dataframe(p_pmts[["Date", "Amount", "Mode"]], use_container_width=True)

# --- 10. BROKER LEDGER (DETAILED DISPLAY & PDF) ---
elif menu == "Broker Ledger":
    st.header("🤝 Detailed Broker/Market Ledger")
    h_df = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not h_df.empty:
        sb = st.selectbox("Choose Broker", h_df["Broker"].unique())
        b_trips = h_df[h_df["Broker"] == sb]
        b_pmts = df_p[(df_p["Name"] == sb) & (df_p["Category"] == "Broker")]
        
        bal = b_trips["HiredCharges"].sum() - b_pmts["Amount"].sum()
        st.subheader(f"Total Payable: ₹{bal:,.0f}")
        
        st.download_button("📥 Download Broker PDF", gen_ledger_pdf(sb, b_trips, b_pmts, bal, "Broker"), f"Broker_{sb}.pdf", key="b_pdf")
        
        st.write("### 🚛 Hired Trip Details")
        st.dataframe(b_trips[["Date", "LR", "Vehicle", "From", "To", "HiredCharges"]], use_container_width=True)
        st.write("### 💰 Payout History")
        st.dataframe(b_pmts[["Date", "Amount", "Mode"]], use_container_width=True)

# --- 11. LR MANAGER (FULL EDIT / DELETE) ---
elif menu == "LR Manager":
    st.header("🔍 Search, Edit or Delete Trips")
    sq = st.text_input("Search (LR No, Vehicle, or Party)")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"edit_lr_{i}_{r['LR']}"):
                ec1, ec2 = st.columns(2)
                up = ec1.text_input("Party", r['Party'])
                uv = ec1.text_input("Vehicle", r['Vehicle'])
                ufl = ec2.text_input("From", r['From'])
                utl = ec2.text_input("To", r['To'])
                uf = ec2.number_input("Freight", value=float(r['Freight']))
                uh = ec2.number_input("Hired Chg", value=float(r['HiredCharges']))
                
                if st.form_submit_button("✅ Update This Record"):
                    # Profit recalculation logic
                    new_prof = (uf - uh) if r['Type'] == "Hired" else (uf - (r['Diesel'] + r['Toll'] + r['DriverExp'] + r['Other']))
                    upd = list(r.values)
                    # Updating specific indices
                    upd[3], upd[12], upd[15], upd[16], upd[17], upd[18], upd[23] = up, uv, ufl, utl, uf, uh, new_prof
                    if update_ws("trips", r['LR'], upd): st.success("Updated in Sheets!"); st.rerun()
            
            if st.button(f"🗑️ Delete LR {r['LR']}", key=f"del_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Record Deleted!"); st.rerun()

# --- 12. MONTHLY BILL BUILDER (SELECTION) ---
elif menu == "Monthly Bill Builder":
    st.header("📅 Monthly Invoice Builder")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'], errors='coerce')
        sp = st.selectbox("Party Name", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy()
        
        st.write("Select Trips to Include in Bill:")
        m_df.insert(0, "Select", True)
        edited = st.data_editor(m_df, hide_index=True, key="bill_ed")
        
        sel_trips = edited[edited["Select"] == True]
        if not sel_trips.empty:
            total_bill = sel_trips['Freight'].sum()
            st.metric("Total Selected Freight", f"₹{total_bill:,.0f}")

# --- 13. P&L, TRANSACTIONS & EXPENSES ---
elif menu == "P&L Statement":
    st.header("📈 Profit & Loss Statement")
    rev = df_t['Freight'].sum(); hire = df_t['HiredCharges'].sum(); adm = df_a['Amount'].sum()
    st.table(pd.DataFrame({
        "Description": ["Total Revenue", "Market Payouts (-)", "Admin Expenses (-)", "NET PROFIT"],
        "Amount": [f"₹{rev:,.0f}", f"₹{hire:,.0f}", f"₹{adm:,.0f}", f"₹{(rev-hire-adm):,.0f}"]
    }))

elif menu == "Record Transaction":
    st.header("💰 Money Receipt / Payment")
    with st.form("tr_form"):
        nms = list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist()))
        snm = st.selectbox("Select Account Name", nms)
        cat = st.selectbox("Category", ["Party", "Broker"])
        am, md = st.number_input("Amount"), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Record Entry"):
            if save_ws("payments", [str(date.today()), snm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "Office Expense":
    st.header("🏢 Admin Expenses")
    with st.form("adm_form"):
        ct = st.selectbox("Category", ["Rent", "Salary", "Stationary", "Electricity", "Other"])
        am, rem = st.number_input("Amount"), st.text_input("Remarks")
        if st.form_submit_button("Save Expense"):
            if save_ws("admin", [str(date.today()), ct, am, rem]): st.success("Saved!"); st.rerun()

elif menu == "Vehicle Profit":
    st.header("🚛 Own Vehicle Performance")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        v_rep = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index()
        st.dataframe(v_rep.rename(columns={"LR": "Trips", "Freight": "Revenue"}), use_container_width=True)
        st.bar_chart(v_rep.set_index("Vehicle")["Profit"])
