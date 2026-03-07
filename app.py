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

def load_from_gs(worksheet_name):
    try:
        ws = sh.worksheet(worksheet_name)
        return pd.DataFrame(ws.get_all_records())
    except: return pd.DataFrame()

# --- EDIT & DELETE FUNCTIONS ---
def update_gs_row(worksheet_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(worksheet_name)
        cell = ws.find(lr_no)
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row])
            return True
        return False
    except Exception as e:
        st.error(f"Error updating: {e}"); return False

def delete_gs_row(worksheet_name, lr_no):
    try:
        ws = sh.worksheet(worksheet_name)
        cell = ws.find(lr_no)
        if cell:
            ws.delete_rows(cell.row)
            return True
        return False
    except Exception as e:
        st.error(f"Error deleting: {e}"); return False

# --- DATA LOADING ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
if sh:
    df_t = load_from_gs("trips")
    df_p = load_from_gs("payments")
    df_a = load_from_gs("admin")
    for c in cols_t:
        if c in df_t.columns:
            if any(x in c for x in ["Freight", "HiredCharges", "Profit", "Weight"]):
                df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
else: st.stop()

def save_to_gs(worksheet_name, row_data):
    try:
        ws = sh.worksheet(worksheet_name); ws.append_row(row_data, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- PDF GENERATOR ---
def generate_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20); pdf.cell(190, 10, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12); pdf.cell(95, 10, f"LR No: {row['LR']}", 1); pdf.cell(95, 10, f"Date: {row['Date']}", 1, ln=True)
    pdf.ln(5); pdf.cell(190, 10, f"Party: {row['Party']}", 1, ln=True)
    pdf.cell(100, 10, f"Vehicle: {row['Vehicle']}", 1); pdf.cell(90, 10, f"Freight: {row['Freight']}", 1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIN ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add LR", "LR Reports", "Monthly Bill", "Party Ledger", "Broker Ledger", "Party Receipt", "Broker Payment", "Admin Expense"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    t_rev = df_t["Freight"].sum()
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum() if not df_p.empty else 0
    b_work = df_t["HiredCharges"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum() if not df_p.empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Profit", f"₹{df_t['Profit'].sum():,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Payable", f"₹{(b_work - b_paid):,.0f}")

# --- ADD LR ---
elif menu == "Add LR":
    st.header("📝 New LR Entry")
    v_type = st.radio("Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: d, party = st.date_input("Date"), st.text_input("Party*")
        with c2: vehicle, f_loc, t_loc = st.text_input("Vehicle*"), st.text_input("From"), st.text_input("To")
        with c3: freight, h_chg = st.number_input("Freight*"), st.number_input("Hired Charges")
        if st.form_submit_button("Save"):
            prof = (freight - h_chg) if v_type == "Hired" else freight
            new_row = [str(d), f"LR-{len(df_t)+1001}", v_type, party, "", "", "", "", "", "", "", 0, vehicle, "Driver", "", f_loc, t_loc, freight, h_chg, 0, 0, 0, 0, prof]
            if save_to_gs("trips", new_row): st.success("Saved!"); st.rerun()

# --- LR REPORTS (EDIT & DELETE) ---
elif menu == "LR Reports":
    st.header("📋 LR Management")
    if not df_t.empty:
        for i, row in df_t.iterrows():
            with st.expander(f"{row['LR']} | {row['Party']} | {row['Vehicle']}"):
                with st.form(f"f_{row['LR']}"):
                    c1, c2 = st.columns(2)
                    edit_party = c1.text_input("Party", row['Party'])
                    edit_freight = c2.number_input("Freight", value=float(row['Freight']))
                    if st.form_submit_button("Update"):
                        updated = list(row.values)
                        updated[3], updated[17] = edit_party, edit_freight
                        if update_gs_row("trips", row['LR'], updated): st.success("Updated!"); st.rerun()
                
                if st.button(f"🗑️ Delete {row['LR']}", key=f"del_{i}"):
                    if delete_gs_row("trips", row['LR']): st.warning("Deleted!"); st.rerun()
                st.download_button("📥 PDF", generate_lr_pdf(row), f"{row['LR']}.pdf")

# --- OTHER MENUS ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Bill")
    if not df_t.empty:
        p_name = st.selectbox("Party", df_t["Party"].unique())
        m_df = df_t[df_t["Party"]==p_name]
        st.dataframe(m_df)

elif menu == "Party Ledger":
    st.header("🏢 Party Ledger")
    if not df_t.empty:
        p_bill = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total"})
        st.dataframe(p_bill)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Ledger")
    hired = df_t[df_t["Type"]=="Hired"]
    if not hired.empty:
        b_work = hired.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total"})
        st.dataframe(b_work)

elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Entry")
    with st.form("p"):
        nm = st.text_input("Name")
        am = st.number_input("Amount")
        if st.form_submit_button("Save"):
            save_to_gs("payments", [str(date.today()), nm, cat, am, "Cash"]); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Admin Expense")
    with st.form("a"):
        am = st.number_input("Amount")
        if st.form_submit_button("Save"):
            save_to_gs("admin", [str(date.today()), "Other", am, ""]); st.rerun()
