import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 1. CONFIG & GOOGLE SHEETS SETUP ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

def get_gspread_client():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Login Failed: {e}"); return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

sh = None
if client:
    try: sh = client.open(SHEET_NAME)
    except: st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili."); st.stop()

# --- HELPER FUNCTIONS ---
def load_from_gs(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        return pd.DataFrame(ws.get_all_records())
    except: return pd.DataFrame()

def save_to_gs(ws_name, row_data):
    try:
        ws = sh.worksheet(ws_name); ws.append_row(row_data, value_input_option='USER_ENTERED')
        return True
    except: return False

def update_gs_row(ws_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(ws_name); cell = ws.find(str(lr_no))
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row])
            return True
        return False
    except: return False

def delete_gs_row(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name); cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row); return True
        return False
    except: return False

# --- DATA LOADING & SAFETY ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_from_gs("trips")
    df_p = load_from_gs("payments")
    df_a = load_from_gs("admin")
    
    # Fill Missing Columns & Convert Numeric
    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    
    num_cols = ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp", "Other"]
    for c in num_cols: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    
    if not df_p.empty:
        for c in cols_p:
            if c not in df_p.columns: df_p[c] = 0 if c == "Amount" else ""
        df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    else: df_p = pd.DataFrame(columns=cols_p)

    if not df_a.empty:
        for c in cols_a:
            if c not in df_a.columns: df_a[c] = 0 if c == "Amount" else ""
        df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    else: df_a = pd.DataFrame(columns=cols_a)
else: st.stop()

# --- PDF GENERATOR ---
def generate_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20); pdf.cell(190, 10, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12); pdf.cell(95, 10, f"LR No: {row['LR']}", 1); pdf.cell(95, 10, f"Date: {row['Date']}", 1, ln=True)
    pdf.ln(5); pdf.cell(190, 10, f"Billing Party: {row['Party']}", 1, ln=True)
    pdf.cell(95, 10, f"Vehicle: {row['Vehicle']}", 1); pdf.cell(95, 10, f"Freight: Rs. {row['Freight']}", 1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIN ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

# --- MENU ---
menu = st.sidebar.selectbox("Main Menu", ["Dashboard", "Add LR", "LR Reports", "Monthly Bill", "Party Ledger", "Broker Ledger", "Party Receipt", "Broker Payment", "Admin Expense"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    t_rev = df_t["Freight"].sum()
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_work = df_t["HiredCharges"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Trip Profit", f"₹{df_t['Profit'].sum():,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Payable", f"₹{(b_work - b_paid):,.0f}")
    st.divider()
    st.metric("Admin Expenses", f"₹{df_a['Amount'].sum():,.0f}")

# --- ADD LR ---
elif menu == "Add LR":
    st.header("📝 New Trip Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d, party = st.date_input("Date", date.today()), st.text_input("Party*")
            con_nm, con_gst, con_add = st.text_input("Consignor"), st.text_input("Consignor GST"), st.text_area("Consignor Add")
        with c2:
            cee_nm, cee_gst, cee_add = st.text_input("Consignee"), st.text_input("Consignee GST"), st.text_area("Consignee Add")
            f_loc, t_loc, vehicle = st.text_input("From"), st.text_input("To"), st.text_input("Vehicle No*")
        with c3:
            mat, wt = st.text_input("Material"), st.number_input("Weight", 0.0)
            broker = st.text_input("Broker Name", disabled=(v_type=="Own"))
            freight = st.number_input("Freight*", 0.0)
            if v_type == "Hired": h_chg, dsl, de, tl, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else: h_chg, dsl, de, tl, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save Entry"):
            if party and vehicle:
                prof = (freight - h_chg) if v_type == "Hired" else (freight - (dsl+de+tl+ot))
                new_row = [str(d), f"LR-{len(df_t)+1001}", v_type, party, con_nm, con_gst, con_add, cee_nm, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
                if save_to_gs("trips", new_row): st.success("Saved!"); st.rerun()

# --- LR REPORTS (FULL EDIT & DELETE) ---
elif menu == "LR Reports":
    st.header("📋 LR Management (Edit/Delete)")
    if not df_t.empty:
        search = st.text_input("Search LR/Vehicle/Party")
        filtered = df_t[df_t.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        for i, row in filtered.iterrows():
            with st.expander(f"{row['LR']} | {row['Party']} | {row['Vehicle']}"):
                with st.form(f"edit_{row['LR']}"):
                    st.write("Edit Fields:")
                    ec1, ec2, ec3 = st.columns(3)
                    e_p = ec1.text_input("Party", row['Party'])
                    e_v = ec1.text_input("Vehicle", row['Vehicle'])
                    e_f = ec2.number_input("Freight", value=float(row['Freight']))
                    e_h = ec2.number_input("Hired Charges", value=float(row['HiredCharges']))
                    e_mat = ec3.text_input("Material", row['Material'])
                    e_wt = ec3.number_input("Weight", value=float(row['Weight']))
                    e_br = ec3.text_input("Broker", row['Broker'])
                    
                    if st.form_submit_button("Update Records"):
                        updated = list(row.values)
                        # Index update (Type based profit)
                        new_prof = (e_f - e_h) if row['Type'] == "Hired" else (e_f - (row['Diesel']+row['DriverExp']+row['Toll']+row['Other']))
                        updated[3], updated[12], updated[17], updated[18], updated[10], updated[11], updated[14], updated[23] = e_p, e_v, e_f, e_h, e_mat, e_wt, e_br, new_prof
                        if update_gs_row("trips", row['LR'], updated): st.success("Updated!"); st.rerun()
                
                if st.button(f"🗑️ Delete {row['LR']}", key=f"del_{i}"):
                    if delete_gs_row("trips", row['LR']): st.warning("Deleted!"); st.rerun()

# --- MONTHLY BILL ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Party Bill")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        p_name = st.selectbox("Select Party", df_t["Party"].unique())
        m_list = df_t['Date'].dt.strftime('%B %Y').unique()
        sel_m = st.selectbox("Select Month", m_list)
        m_df = df_t[(df_t['Party']==p_name) & (df_t['Date'].dt.strftime('%B %Y')==sel_m)]
        st.dataframe(m_df[["Date", "LR", "Vehicle", "From", "To", "Freight"]], use_container_width=True)
        if not m_df.empty: st.metric("Total Bill", f"₹{m_df['Freight'].sum():,.0f}")

# --- LEDGERS (BROKER FIX) ---
elif menu == "Party Ledger":
    st.header("🏢 Party Outstanding")
    if not df_t.empty:
        p_bill = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total_Bill"})
        p_paid = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Paid"})
        res = pd.merge(p_bill, p_paid, on="Name", how="left").fillna(0)
        res["Balance"] = res["Total_Bill"] - res["Total_Paid"]
        st.dataframe(res, use_container_width=True)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Payable Ledger")
    # Case-insensitive "Hired" check
    hired = df_t[df_t["Type"].str.lower() == "hired"]
    if not hired.empty:
        b_work = hired.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total_Work"})
        b_paid = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Paid"})
        res = pd.merge(b_work, b_paid, on="Name", how="left").fillna(0)
        res["Balance"] = res["Total_Work"] - res["Total_Paid"]
        st.dataframe(res, use_container_width=True)
    else: st.info("Hired vehicle data nahi mila. Add LR mein 'Hired' select karein.")

# --- PAYMENTS ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Entry")
    with st.form("pay"):
        nm = st.selectbox("Select Name", df_t[cat].unique() if not df_t.empty else [])
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save"):
            if save_to_gs("payments", [str(date.today()), nm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Admin Expense")
    with st.form("adm"):
        ct = st.selectbox("Category", ["Salary", "Rent", "Office", "Other"])
        am, rem = st.number_input("Amount", 0.0), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            if save_to_gs("admin", [str(date.today()), ct, am, rem]): st.success("Saved!"); st.rerun()
