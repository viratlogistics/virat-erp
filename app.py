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

# --- 2. DATA UTILITIES (CLEAN & SECURE) ---
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
    except Exception as e:
        st.error(f"Update failed: {e}"); return False

def delete_ws(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row); return True
        return False
    except: return False

# --- 3. DATA LOADING ---
if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")
    df_d = load_ws("drivers") # New sheet for Driver Attendance/Salaries
    
    # Numeric Casting
    for c in ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp"]:
        if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
else: st.stop()

# --- 4. PDF ENGINE (LEDGER & REPORTS) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18); self.cell(190, 10, 'VIRAT LOGISTICS', ln=True, align='C')
        self.set_font('Arial', 'I', 10); self.cell(190, 5, 'Fleet Management & Logistics', ln=True, align='C'); self.ln(10)

def gen_ledger_pdf(name, type_label, trips, payments, balance):
    pdf = PDF(); pdf.add_page()
    pdf.set_font("Arial", 'B', 14); pdf.cell(190, 10, f"ACCOUNT LEDGER: {name} ({type_label})", ln=True)
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "Date", 1, 0, 'C', 1); pdf.cell(40, 10, "LR/Ref", 1, 0, 'C', 1); pdf.cell(60, 10, "Details", 1, 0, 'C', 1); pdf.cell(30, 10, "Debit", 1, 0, 'C', 1); pdf.cell(30, 10, "Credit", 1, 1, 'C', 1)
    pdf.set_font("Arial", '', 9)
    for _, r in trips.iterrows():
        amt = r['Freight'] if type_label == "Party" else r['HiredCharges']
        pdf.cell(30, 8, str(r['Date']), 1); pdf.cell(40, 8, str(r['LR']), 1); pdf.cell(60, 8, f"{r['Vehicle']}", 1)
        if type_label == "Party": pdf.cell(30, 8, f"{amt:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
        else: pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{amt:,.0f}", 1, 1)
    for _, p in payments.iterrows():
        pdf.cell(30, 8, str(p['Date']), 1); pdf.cell(40, 8, "PAYMENT", 1); pdf.cell(60, 8, p['Mode'], 1)
        if type_label == "Party": pdf.cell(30, 8, "0", 1); pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1, 1)
        else: pdf.cell(30, 8, f"{p['Amount']:,.0f}", 1); pdf.cell(30, 8, "0", 1, 1)
    pdf.cell(130, 10, "TOTAL BALANCE", 1, 0, 'R', 1); pdf.cell(60, 10, f"Rs. {balance:,.2f}", 1, 1, 'C', 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. UI & AUTH ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Portal")
    with st.form("L"):
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Access ERP"):
            if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard", "Add LR", "LR Manager", "Monthly Bill", "Party Ledger", "Broker Ledger", "Driver Management", "Vehicle Profit", "P&L Statement", "Transactions", "Office Expense"])

# DASHBOARD (CASH FLOW & FUND FLOW)
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm_exp = df_a["Amount"].sum()
    st.subheader("🌊 Cash Flow (Actual Cash)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Collected", f"₹{p_rec:,.0f}")
    c2.metric("Cash Outflow", f"₹{(b_paid + adm_exp):,.0f}")
    c3.metric("Balance Cash", f"₹{(p_rec - b_paid - adm_exp):,.0f}")
    st.divider(); st.subheader("📂 Fund Flow (Market Dues)")
    f1, f2 = st.columns(2)
    f1.metric("Paisa Lena Hai (Party)", f"₹{(df_t['Freight'].sum() - p_rec):,.0f}")
    f2.metric("Paisa Dena Hai (Broker)", f"₹{(df_t['HiredCharges'].sum() - b_paid):,.0f}")

# ADD LR
elif menu == "Add LR":
    st.header("📝 Create LR")
    v_type = st.radio("Type", ["Own", "Hired"], horizontal=True)
    with st.form("add_lr", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: d, party = st.date_input("Date"), st.text_input("Party*")
        with c2: v_no, fl, tl = st.text_input("Vehicle No*"), st.text_input("From"), st.text_input("To")
        with c3: fr, h_c, br = st.number_input("Freight*"), st.number_input("Hired Chg"), st.text_input("Broker")
        if st.form_submit_button("Save Trip"):
            if party and v_no:
                prof = (fr - h_c) if v_type == "Hired" else fr
                row = [str(d), f"LR-{len(df_t)+1001}", v_type, party, "", "", "", "", "", "", "", 0, v_no, "Driver", br, fl, tl, fr, h_c, 0, 0, 0, 0, prof]
                if save_ws("trips", row): st.success("Saved!"); st.rerun()

# LR MANAGER
elif menu == "LR Manager":
    st.header("🔍 Edit / Delete / Print LR")
    sq = st.text_input("Search LR/Vehicle")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"edit_{i}_{r['LR']}"):
                ec1, ec2 = st.columns(2)
                up = ec1.text_input("Party", r['Party']); uv = ec1.text_input("Vehicle", r['Vehicle'])
                uf = ec2.number_input("Freight", value=float(r['Freight'])); uh = ec2.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("Update Record"):
                    upd = list(r.values); upd[3], upd[12], upd[17], upd[18] = up, uv, uf, uh
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            c1, c2 = st.columns(2)
            if c1.button(f"🗑️ Delete {r['LR']}", key=f"del_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# PARTY LEDGER (DISPLAY FIX)
elif menu == "Party Ledger":
    st.header("🏢 Party Ledger Display")
    sp = st.selectbox("Choose Party", df_t["Party"].unique())
    p_trips = df_t[df_t["Party"] == sp]
    p_pmts = df_p[(df_p["Name"] == sp) & (df_p["Category"] == "Party")]
    bal = p_trips["Freight"].sum() - p_pmts["Amount"].sum()
    st.subheader(f"Total Outstanding: ₹{bal:,.0f}")
    st.download_button("📥 Download Ledger PDF", gen_ledger_pdf(sp, "Party", p_trips, p_pmts, bal), f"Ledger_{sp}.pdf", key="pdf_p")
    st.write("### Trip Wise Details")
    st.dataframe(p_trips[["Date", "LR", "Vehicle", "From", "To", "Freight"]], use_container_width=True)
    st.write("### Payment History")
    st.dataframe(p_pmts[["Date", "Amount", "Mode"]], use_container_width=True)

# BROKER LEDGER (DISPLAY FIX)
elif menu == "Broker Ledger":
    st.header("🤝 Broker Ledger Display")
    h_df = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not h_df.empty:
        sb = st.selectbox("Choose Broker", h_df["Broker"].unique())
        b_trips = h_df[h_df["Broker"] == sb]
        b_pmts = df_p[(df_p["Name"] == sb) & (df_p["Category"] == "Broker")]
        bal = b_trips["HiredCharges"].sum() - b_pmts["Amount"].sum()
        st.subheader(f"Payable Balance: ₹{bal:,.0f}")
        st.download_button("📥 Download PDF", gen_ledger_pdf(sb, "Broker", b_trips, b_pmts, bal), f"Broker_{sb}.pdf", key="pdf_b")
        st.write("### Hired Trip Details")
        st.dataframe(b_trips[["Date", "LR", "Vehicle", "From", "To", "HiredCharges"]], use_container_width=True)
        st.write("### Payment History")
        st.dataframe(b_pmts[["Date", "Amount", "Mode"]], use_container_width=True)

# DRIVER MANAGEMENT (NEW FEATURE)
elif menu == "Driver Management":
    st.header("👨‍✈️ Driver Salary & Attendance")
    with st.expander("➕ Record Driver Payment/Attendance"):
        with st.form("d_form"):
            dn, dt = st.text_input("Driver Name"), st.date_input("Date")
            at = st.selectbox("Status", ["Present", "Absent", "Leave"])
            adv = st.number_input("Advance Paid", 0.0)
            sal = st.number_input("Monthly Salary Fix", 0.0)
            if st.form_submit_button("Record Driver Data"):
                save_ws("drivers", [str(dt), dn, at, adv, sal])
                st.success("Driver Data Saved!"); st.rerun()
    if not df_d.empty:
        # Numeric casting for driver data
        df_d["Advance Paid"] = pd.to_numeric(df_d["Advance Paid"], errors='coerce').fillna(0)
        df_d["Monthly Salary Fix"] = pd.to_numeric(df_d["Monthly Salary Fix"], errors='coerce').fillna(0)
        st.write("### Driver Summary Report")
        d_summary = df_d.groupby("Driver Name").agg({"Advance Paid": "sum", "Monthly Salary Fix": "max", "Status": lambda x: (x == "Present").sum()}).reset_index()
        d_summary.columns = ["Driver Name", "Total Advance", "Monthly Salary", "Days Present"]
        d_summary["Earned Salary"] = (d_summary["Monthly Salary"] / 30) * d_summary["Days Present"]
        d_summary["Remaining Balance"] = d_summary["Earned Salary"] - d_summary["Total Advance"]
        st.dataframe(d_summary.style.format({"Monthly Salary": "₹{:.0f}", "Total Advance": "₹{:.0f}", "Earned Salary": "₹{:.0f}", "Remaining Balance": "₹{:.0f}"}))

# P&L STATEMENT
elif menu == "P&L Statement":
    st.header("📉 Profit & Loss")
    rev = df_t['Freight'].sum(); h_c = df_t['HiredCharges'].sum(); adm = df_a['Amount'].sum()
    st.table(pd.DataFrame({"Particulars": ["Total Revenue", "Market Payouts", "Admin Exp", "NET PROFIT"], "Amount": [rev, h_c, adm, (rev-h_c-adm)]}))

# VEHICLE PROFIT (OWN ONLY)
elif menu == "Vehicle Profit":
    st.header("🚛 Own Vehicle Performance")
    own = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index()
        st.dataframe(vr, use_container_width=True)

# TRANSACTIONS
elif menu == "Transactions":
    st.header("💰 Payment Entry")
    with st.form("p_pay"):
        nm = st.selectbox("Name", list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist())))
        cat, am = st.selectbox("Type", ["Party", "Broker"]), st.number_input("Amt")
        if st.form_submit_button("Save"):
            save_ws("payments", [str(date.today()), nm, cat, am, "Cash"]); st.rerun()

# OFFICE EXPENSE
elif menu == "Office Expense":
    st.header("🏢 Admin Expenses")
    with st.form("oe"):
        am, rem = st.number_input("Amt"), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            save_ws("admin", [str(date.today()), "Other", am, rem]); st.rerun()
