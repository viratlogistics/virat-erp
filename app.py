import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIG & GOOGLE SHEETS SETUP ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

# Google Sheets Connection Logic
def get_gspread_client():
    try:
        # Streamlit Secrets ko dictionary mein badalna
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Private key ke newline characters fix karna
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Login Failed (Check Secrets): {e}")
        return None

client = get_gspread_client()

# IMPORTANT: Sheet ka naam bilkul sahi likhein (Jaise Google Drive mein hai)
SHEET_NAME = "Virat_Logistics_Data" 

# Safe Sheet Opening
sh = None
if client:
    try:
        sh = client.open(SHEET_NAME)
    except Exception as e:
        st.error(f"❌ Google Sheet '{SHEET_NAME}' nahi mili. Check karein: \n1. Sheet ka naam sahi hai? \n2. Service Email ko 'Editor' banaya hai?")
        st.stop()

def load_from_gs(worksheet_name):
    try:
        ws = sh.worksheet(worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        # Agar sheet khali ho toh empty dataframe dena
        return pd.DataFrame()

def save_to_gs(worksheet_name, row_data):
    try:
        ws = sh.worksheet(worksheet_name)
        ws.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"Error saving to {worksheet_name}: {e}")
        return False

# Data Loading
if sh:
    df_t = load_from_gs("trips")
    df_p = load_from_gs("payments")
    df_a = load_from_gs("admin")
else:
    st.stop()

# --- 2. LOGIN (User: admin, Pass: 1234) ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP Login")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
        else: st.error("Wrong Login")
    st.stop()

# --- 3. SIDEBAR MENU ---
menu = st.sidebar.selectbox("Menu", [
    "Dashboard", "Add LR", "Monthly Bill", "Vehicle Profit", 
    "Party Receipt", "Broker Payment", "Admin Expense", 
    "LR Report", "Party Ledger", "Broker Ledger"
])

# (Baaki saare Add LR, Monthly Bill, Dashboard functions waise hi rahenge...)
# Bas Save aur Load ke liye load_from_gs aur save_to_gs use karna hai.

if menu == "Add LR":
    st.header(f"📝 New LR Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d, lr = st.date_input("Date", date.today()), "LR-" + str(len(df_t) + 1001)
            party, consignor, con_gst, con_add = st.text_input("Billing Party*"), st.text_input("Consignor"), st.text_input("Consignor GST"), st.text_area("Consignor Address")
        with c2:
            consignee, cee_gst, cee_add = st.text_input("Consignee"), st.text_input("Consignee GST"), st.text_area("Consignee Address")
            f_loc, t_loc, vehicle = st.text_input("From Location"), st.text_input("To Location"), st.text_input("Vehicle No*")
        with c3:
            mat, wt, broker = st.text_input("Material"), st.number_input("Weight", 0.0), st.text_input("Broker", disabled=(v_type=="Own"))
            freight = st.number_input("Freight*", 0.0)
            if v_type == "Hired": h_chg, dsl, de, tl, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else: h_chg, dsl, de, tl, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save to Sheets"):
            if party and vehicle:
                prof = (freight - (dsl+de+tl+ot)) if v_type == "Own" else (freight - h_chg)
                new_row = [str(d), lr, v_type, party, consignor, con_gst, con_add, consignee, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
                if save_to_gs("trips", new_row):
                    st.success("Saved Successfully!"); st.rerun()
