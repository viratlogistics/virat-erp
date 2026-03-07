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
        st.error(f"❌ Login Failed: {e}")
        return None

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

# Columns structure (Sahi sequence jo Sheet se match karega)
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_from_gs("trips")
    df_p = load_from_gs("payments")
    df_a = load_from_gs("admin")
    
    # Missing columns safety
    for c in cols_t: 
        if c not in df_t.columns: df_t[c] = 0
    for c in cols_p: 
        if c not in df_p.columns: df_p[c] = 0
else:
    st.stop()

def save_to_gs(worksheet_name, row_data):
    try:
        ws = sh.worksheet(worksheet_name)
        ws.append_row(row_data, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error: {e}"); return False

# --- 2. LOGIN ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add LR", "Party Ledger", "Broker Ledger", "Party Receipt", "Broker Payment", "Admin Expense"])

# --- 3. DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    t_prof = pd.to_numeric(df_t["Profit"], errors='coerce').sum()
    t_rev = pd.to_numeric(df_t["Freight"], errors='coerce').sum()
    p_rec = pd.to_numeric(df_p[df_p["Category"]=="Party"]["Amount"], errors='coerce').sum()
    b_work = pd.to_numeric(df_t["HiredCharges"], errors='coerce').sum()
    b_paid = pd.to_numeric(df_p[df_p["Category"]=="Broker"]["Amount"], errors='coerce').sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Profit", f"₹{t_prof:,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Payable", f"₹{(b_work - b_paid):,.0f}")

# --- 4. ADD LR ---
elif menu == "Add LR":
    st.header("📝 New LR Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d, party = st.date_input("Date"), st.text_input("Billing Party*")
            consignor, con_gst, con_add = st.text_input("Consignor"), st.text_input("GST"), st.text_area("Address")
        with c2:
            consignee, cee_gst, cee_add = st.text_input("Consignee"), st.text_input("Consignee GST"), st.text_area("Consignee Add")
            f_loc, t_loc, vehicle = st.text_input("From"), st.text_input("To"), st.text_input("Vehicle No*")
        with c3:
            mat, wt = st.text_input("Material"), st.number_input("Weight", 0.0)
            broker = st.text_input("Broker", disabled=(v_type=="Own"))
            freight = st.number_input("Freight*", 0.0)
            if v_type == "Hired":
                h_chg, dsl, de, tl, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else:
                h_chg, dsl, de, tl, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save"):
            prof = (freight - (dsl+de+tl+ot)) if v_type == "Own" else (freight - h_chg)
            # Yahan sequence bilkul sheet ke columns jaisa hai
            new_row = [str(d), f"LR-{len(df_t)+1001}", v_type, party, consignor, con_gst, con_add, consignee, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
            if save_to_gs("trips", new_row): st.success("Saved!"); st.rerun()

# --- 5. LEDGERS (Fixing Type & Calculation) ---
elif menu == "Party Ledger":
    st.header("🏢 Party Outstanding")
    if not df_t.empty:
        df_t["Freight"] = pd.to_numeric(df_t["Freight"], errors='coerce').fillna(0)
        p_bill = df_t.groupby("Party")["Freight"].sum().reset_index()
        p_bill.columns = ["Name", "Total_Billing"]
        
        df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
        p_paid = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index()
        p_paid.columns = ["Name", "Total_Received"]
        
        ledger = pd.merge(p_bill, p_paid, on="Name", how="left").fillna(0)
        ledger["Balance"] = ledger["Total_Billing"] - ledger["Total_Received"]
        st.dataframe(ledger, use_container_width=True)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Outstanding")
    hired = df_t[df_t["Type"] == "Hired"]
    if not hired.empty:
        hired["HiredCharges"] = pd.to_numeric(hired["HiredCharges"], errors='coerce').fillna(0)
        b_work = hired.groupby("Broker")["HiredCharges"].sum().reset_index()
        b_work.columns = ["Name", "Total_Work"]
        
        df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
        b_paid = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index()
        b_paid.columns = ["Name", "Total_Paid"]
        
        ledger = pd.merge(b_work, b_paid, on="Name", how="left").fillna(0)
        ledger["Balance"] = ledger["Total_Work"] - ledger["Total_Paid"]
        st.dataframe(ledger, use_container_width=True)
    else: st.info("No Hired Trips found.")

# --- 6. PAYMENTS ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Entry")
    with st.form("p_form", clear_on_submit=True):
        # Dropdown for names from trips
        names = df_t[cat].unique() if not df_t.empty else []
        nm = st.selectbox("Name", names)
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save Payment"):
            if save_to_gs("payments", [str(date.today()), nm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Admin Expense")
    with st.form("a_form", clear_on_submit=True):
        ct, am, rem = st.selectbox("Type", ["Salary", "Rent", "Office", "Other"]), st.number_input("Amount"), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            save_to_gs("admin", [str(date.today()), ct, am, rem]); st.rerun()
