import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. SETTINGS & CLOUD CONNECTION ---
st.set_page_config(page_title="Virat Logistics Master ERP", layout="wide", page_icon="🚚")

@st.cache_resource
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

# --- 2. DATA UTILITIES (CLEAN & SECURE) ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns] # Headers clean karega
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
        if cell: ws.delete_rows(cell.row); return True
        return False
    except: return False

# --- 3. DATA REFRESH & NUMERIC ---
if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")
    df_d = load_ws("drivers")
    
    # Numeric Casting
    for c in ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp"]:
        if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    if not df_d.empty:
        for c in ["Advance", "Salary"]:
            if c in df_d.columns: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').fillna(0)
else: st.stop()

# --- 4. PDF ENGINE ---
def gen_pdf(name, trips, pmts, bal, lbl):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"VIRAT LOGISTICS - {lbl} LEDGER", ln=1, align='C')
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230,230,230)
    pdf.cell(30, 10, "Date", 1, 0, 'C', 1); pdf.cell(30, 10, "Ref", 1, 0, 'C', 1); pdf.cell(70, 10, "Detail", 1, 0, 'C', 1); pdf.cell(30, 10, "Debit", 1, 0, 'C', 1); pdf.cell(30, 10, "Credit", 1, 1, 'C', 1)
    pdf.set_font("Arial", '', 9)
    for _, r in trips.iterrows():
        pdf.cell(30, 8, str(r.get('Date','')), 1); pdf.cell(30, 8, str(r.get('LR','')), 1); pdf.cell(70, 8, f"{r.get('Vehicle','')}", 1)
        amt = r.get('Freight',0) if lbl=="Party" else r.get('HiredCharges',0)
        pdf.cell(30, 8, str(amt) if lbl=="Party" else "0", 1); pdf.cell(30, 8, "0" if lbl=="Party" else str(amt), 1, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(160, 10, "BALANCE", 1, 0, 'R', 1); pdf.cell(30, 10, f"{bal}", 1, 1, 'C', 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTH ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    u = st.sidebar.text_input("User"); p = st.sidebar.text_input("Pass", type="password")
    if st.sidebar.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard", "Add LR", "LR Manager", "Monthly Bill", "Party Ledger", "Broker Ledger", "Driver Management", "Vehicle Profit", "P&L Statement", "Payment Entry", "Office Expense"])

# --- 7. DASHBOARD (CASH & FUND FLOW) ---
if menu == "Dashboard":
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm = df_a["Amount"].sum()
    st.title("📊 Financial Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Collected (In)", f"₹{p_in:,.0f}")
    c2.metric("Cash Paid (Out)", f"₹{(b_out+adm):,.0f}")
    c3.metric("Net Cashflow", f"₹{(p_in - b_out - adm):,.0f}")
    st.divider(); f1, f2 = st.columns(2)
    f1.metric("Receivables (Parties Se Lena Hai)", f"₹{(df_t['Freight'].sum() - p_in):,.0f}")
    f2.metric("Payables (Broker Ko Dena Hai)", f"₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# --- 8. ADD LR (DYNAMIC TABS) ---
elif menu == "Add LR":
    st.header("📝 Create LR Entry")
    v_type = st.radio("Trip Category*", ["Own Fleet", "Market Hired"], horizontal=True)
    
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today()); pty = st.text_input("Billing Party*")
            cnor = st.text_input("Consignor"); cnee = st.text_input("Consignee")
        with c2:
            v_no = st.text_input("Vehicle No*"); d_nm = st.text_input("Driver Name")
            floc = st.text_input("From Location"); tloc = st.text_input("To Location")
        with c3:
            fr = st.number_input("Freight from Party*", min_value=0.0)
            mat = st.text_input("Material Details")
            # DYNAMIC FIELDS
            if v_type == "Market Hired":
                br = st.text_input("Broker Name*")
                h_c = st.number_input("Hired Charges*", min_value=0.0)
                dsl, tl, de = 0, 0, 0 # Auto-lock/Zero
            else:
                br, h_c = "", 0 # Auto-lock/Zero
                dsl = st.number_input("Diesel Expense", min_value=0.0)
                tl = st.number_input("Toll/Tax", min_value=0.0)
                de = st.number_input("Driver Expense", min_value=0.0)
        
        if st.form_submit_button("🚀 SAVE RECORD"):
            if pty and v_no and fr > 0:
                lr_id = f"LR-{len(df_t)+1001}"
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                p_val = (fr - h_c) if t_val == "Hired" else (fr - (dsl + tl + de))
                # Map to all 24 columns
                row = [str(d), lr_id, t_val, pty, cnor, "", "", cnee, "", "", mat, 0, v_no, d_nm, br, floc, tloc, fr, h_c, dsl, de, tl, 0, p_val]
                if save_ws("trips", row): st.success(f"LR {lr_id} Saved!"); st.rerun()

# --- 9. LR MANAGER (EDIT/DELETE) ---
elif menu == "LR Manager":
    st.header("🔍 Edit / Delete Records")
    sq = st.text_input("Search LR/Vehicle/Party")
    # Leak-proof filtering
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        lr_id = r.get('LR','N/A')
        with st.expander(f"📄 {lr_id} | {r.get('Vehicle','')} | {r.get('Party','')}"):
            with st.form(key=f"ed_{i}_{lr_id}"):
                ec1, ec2 = st.columns(2)
                up = ec1.text_input("Party", r.get('Party',''))
                uv = ec1.text_input("Vehicle", r.get('Vehicle',''))
                uf = ec2.number_input("Freight", value=float(r.get('Freight',0)))
                uh = ec2.number_input("Hired Chg", value=float(r.get('HiredCharges',0)))
                if st.form_submit_button("Update"):
                    upd = list(r.values); upd[3], upd[12], upd[17], upd[18] = up, uv, uf, uh
                    if update_ws("trips", lr_id, upd): st.success("Updated!"); st.rerun()
            if st.button(f"🗑️ Delete {lr_id}", key=f"del_{i}"):
                if delete_ws("trips", lr_id): st.warning("Deleted!"); st.rerun()

# --- 10. DRIVER MANAGEMENT ---
elif menu == "Driver Management":
    st.header("👨‍✈️ Driver Salary & Advance")
    with st.form("d_f"):
        dn = st.text_input("Driver Name"); dt = st.date_input("Date")
        stts = st.selectbox("Status", ["Present", "Absent", "Leave"])
        adv = st.number_input("Advance Paid"); sal = st.number_input("Monthly Salary")
        if st.form_submit_button("Record"):
            save_ws("drivers", [str(dt), dn, stts, adv, sal]); st.rerun()
    if not df_d.empty:
        ds = df_d.groupby("Name").agg({"Advance":"sum","Salary":"max","Status":lambda x:(x=="Present").sum()}).reset_index()
        ds["Earned"] = (ds["Salary"]/30)*ds["Status"]; ds["Balance"] = ds["Earned"] - ds["Advance"]
        st.dataframe(ds.style.format({"Balance":"₹{:.0f}"}), use_container_width=True)

# --- 11. LEDGERS ---
elif menu == "Party Ledger":
    sp = st.selectbox("Select Party", df_t["Party"].unique())
    p_t = df_t[df_t["Party"]==sp]; p_p = df_p[(df_p["Name"]==sp) & (df_p["Category"]=="Party")]
    bal = p_t["Freight"].sum() - p_p["Amount"].sum()
    st.download_button("📥 PDF", gen_pdf(sp, p_t, p_p, bal, "Party"), f"{sp}.pdf")
    st.write("### Trip History"); st.dataframe(p_t[["Date","LR","Vehicle","Freight"]])

elif menu == "Broker Ledger":
    h_df = df_t[df_t["Type"].astype(str).str.lower()=="hired"]
    sb = st.selectbox("Select Broker", h_df["Broker"].unique() if not h_df.empty else [])
    if sb:
        b_t = h_df[h_df["Broker"]==sb]; b_p = df_p[(df_p["Name"]==sb) & (df_p["Category"]=="Broker")]
        bal = b_t["HiredCharges"].sum() - b_p["Amount"].sum()
        st.download_button("📥 PDF", gen_pdf(sb, b_t, b_p, bal, "Broker"), f"{sb}.pdf")
        st.dataframe(b_t[["Date","LR","Vehicle","HiredCharges"]])

# --- 12. P&L & TRANSACTIONS ---
elif menu == "P&L Statement":
    rev, hire, adm = df_t['Freight'].sum(), df_t['HiredCharges'].sum(), df_a['Amount'].sum()
    st.table({"Desc":["Revenue","Payouts","Admin","NET PROFIT"],"Amt":[rev, hire, adm, (rev-hire-adm)]})

elif menu == "Payment Entry":
    with st.form("py"):
        nm = st.selectbox("Name", list(set(df_t["Party"].tolist()+df_t["Broker"].tolist())))
        ct, am = st.selectbox("Type", ["Party", "Broker"]), st.number_input("Amount")
        if st.form_submit_button("Save"):
            save_ws("payments", [str(date.today()), nm, ct, am, "Bank/Cash"]); st.rerun()
