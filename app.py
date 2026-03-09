import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide", page_icon="🚛")

@st.cache_resource
def get_sh():
    try:
        # Better error handling for secrets
        if "gcp_service_account" not in st.secrets:
            st.error("Google Secrets not found!")
            return None
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

sh = get_sh()

def load(name):
    try:
        ws = sh.worksheet(name)
        data = ws.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. IMPROVED PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    # Header
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(190, 10, "VIRAT LOGISTICS", ln=1, align='C')
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(190, 5, "Your Goods Are In Good Hands..", ln=True, align='C')
    pdf.line(10, 32, 200, 32)
    pdf.ln(10)

    # Info Grid
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(45, 10, f"LR No: {lr_data.get('LR No')}", 1)
    pdf.cell(45, 10, f"Date: {lr_data.get('Date')}", 1)
    pdf.cell(50, 10, f"Vehicle: {lr_data.get('Vehicle')}", 1)
    pdf.cell(50, 10, f"Risk: {lr_data.get('Risk')}", 1, ln=True)

    # Party Table
    pdf.ln(2)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(63, 7, "CONSIGNOR", 1, 0, 'C', True)
    pdf.cell(63, 7, "CONSIGNEE", 1, 0, 'C', True)
    pdf.cell(64, 7, "BILLING PARTY", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 9)
    # Using multi_cell with fixed heights for alignment
    curr_y = pdf.get_y()
    pdf.multi_cell(63, 6, f"{lr_data.get('Cnor')}\nGST: {lr_data.get('CnorGST')}", 1)
    y1 = pdf.get_y()
    
    pdf.set_xy(73, curr_y)
    pdf.multi_cell(63, 6, f"{lr_data.get('Cnee')}\nGST: {lr_data.get('CneeGST')}", 1)
    y2 = pdf.get_y()
    
    pdf.set_xy(136, curr_y)
    pdf.multi_cell(64, 6, f"{lr_data.get('BillP')}\nInv: {lr_data.get('InvNo')}", 1)
    y3 = pdf.get_y()
    
    pdf.set_y(max(y1, y2, y3) + 2)
    
    # Material Details
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(190, 8, f"SHIP TO: {lr_data.get('ShipTo')}", 1, ln=True)
    pdf.ln(2)
    
    pdf.set_fill_color(245, 245, 245)
    cols = [("Material", 70), ("Pkg", 30), ("Weight", 30), ("Route", 30), ("Amount", 30)]
    for txt, w in cols: pdf.cell(w, 8, txt, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_font("Arial", '', 9)
    pdf.cell(70, 12, str(lr_data.get('Material')), 1)
    pdf.cell(30, 12, str(lr_data.get('Pkg')), 1)
    pdf.cell(30, 12, f"{lr_data.get('NetWt')}/{lr_data.get('ChgWt')}", 1)
    pdf.cell(30, 12, f"{lr_data.get('From')}-{lr_data.get('To')}", 1)
    
    amt = f"Rs. {lr_data.get('Freight')}" if show_fr else "T.B.B."
    pdf.cell(30, 12, amt, 1, ln=True)

    # Footer
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, f"Bank: {lr_data.get('Bank')} | Ins: {lr_data.get('InsBy')} | Freight: {lr_data.get('PaidBy')}", ln=True)
    pdf.ln(15)
    pdf.cell(95, 5, "Authorized Signatory (Consignor)", 0, 0, 'L')
    pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    
    # Use 'latin-1' only if strictly necessary, but output as bytes
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 3. MAIN APP ---
df_m = load("masters")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.radio("Navigation", ["Dashboard", "LR Entry", "Masters Setup"])

if menu == "Dashboard":
    st.header("📊 Recent Shipments")
    df_trips = load("trips")
    if not df_trips.empty:
        st.dataframe(df_trips.tail(20), use_container_width=True)
    else:
        st.info("No data found in 'trips' worksheet.")

elif menu == "Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank"])
    with st.form("m_form"):
        val = st.text_input(f"New {m_type} Name")
        if st.form_submit_button("Add to Database"):
            if val: 
                save("masters", [m_type, val])
                st.success(f"{val} added!")
                st.rerun()

elif menu == "2. LR Entry":
    # (Existing LR Logic here with added safety checks for empty masters)
    st.header("📝 New Lorry Receipt")
    # ... (Keep your existing form logic)
