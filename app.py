import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 1. SETTINGS & CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP v2.0", layout="wide", page_icon="🚚")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except Exception as e:
        st.error(f"❌ Connection Error: {e}"); return None

sh = get_sh()

# Utility to load and save
def load(name):
    try:
        ws = sh.worksheet(name)
        return pd.DataFrame(ws.get_all_records())
    except: return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. DATA REFRESH ---
# Hum Masters pehle load karenge dropdowns ke liye
df_trips = load("trips")
# Note: Aapko apni sheet mein 'masters' naam ki tab banani hogi (Columns: Type, Name)
df_m = load("masters") 

# --- 3. UI SIDEBAR NAVIGATION ---
st.sidebar.title("🚛 Virat Logistics")
menu = st.sidebar.selectbox("Modules", [
    "1. Masters Setup", 
    "2. LR / Booking Entry", 
    "3. View Trip Records", 
    "4. Driver & Office Exp (Coming Soon)"
])

# --- MODULE 1: MASTER SETUP ---
if menu == "1. Masters Setup":
    st.header("🏗️ Master Data Setup")
    m_type = st.selectbox("Select Master Type", ["Party", "Broker", "Vehicle", "Driver", "Expense Head"])
    with st.form("master_form"):
        m_name = st.text_input(f"{m_type} Name / Number")
        if st.form_submit_button("Add to Master"):
            if m_name:
                save("masters", [m_type, m_name])
                st.success(f"{m_name} added to {m_type} list!"); st.rerun()

# --- MODULE 2: LR / BOOKING ENTRY ---
elif menu == "2. LR / Booking Entry":
    st.header("📝 Consignment Entry (LR)")
    
    # Dropdowns from Master
    parties = df_m[df_m['Type'] == 'Party']['Name'].tolist() if not df_m.empty else []
    brokers = df_m[df_m['Type'] == 'Broker']['Name'].tolist() if not df_m.empty else []
    vehicles = df_m[df_m['Type'] == 'Vehicle']['Name'].tolist() if not df_m.empty else []
    drivers = df_m[df_m['Type'] == 'Driver']['Name'].tolist() if not df_m.empty else []

    v_cat = st.radio("Trip Type", ["Own Fleet", "Market Hired"], horizontal=True)
    
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("LR Date", date.today())
            pty = st.selectbox("Select Party*", ["Select"] + parties)
            v_no = st.selectbox("Select Vehicle*", ["Select"] + vehicles) if v_cat == "Own Fleet" else st.text_input("Vehicle No*")
        with c2:
            fl = st.text_input("From Location")
            tl = st.text_input("To Location")
            mat = st.text_input("Material & Weight")
        with c3:
            fr = st.number_input("Total Freight Value*", min_value=0.0)
            if v_cat == "Market Hired":
                br = st.selectbox("Select Broker", ["Select"] + brokers)
                hc = st.number_input("Hired Charges (Market Rate)")
            else:
                br, hc = "OWN", 0
            
        if st.form_submit_button("🚀 SAVE LR & SYNC"):
            if pty != "Select" and v_no and fr > 0:
                lr_id = f"LR-{date.today().strftime('%y%m')}-{len(df_trips)+1001}"
                # Profit calculation base
                profit = (fr - hc) if v_cat == "Market Hired" else fr # Expenses Phase 2 mein minus honge
                
                # Column mapping to your 24-column sheet
                row = [str(d), lr_id, v_cat, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, fl, tl, fr, hc, 0, 0, 0, 0, profit]
                if save("trips", row):
                    st.success(f"LR {lr_id} Saved Successfully!"); st.rerun()
            else:
                st.error("Missing Mandatory Fields!")

# --- MODULE 3: VIEW RECORDS ---
elif menu == "3. View Trip Records":
    st.header("📂 All Trip Data")
    if not df_trips.empty:
        st.dataframe(df_trips, use_container_width=True)
    else:
        st.info("No records found.")
