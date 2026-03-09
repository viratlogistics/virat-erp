import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. SETTINGS & CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except: return None

sh = get_sh()

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

# PDF Generator (Same as before)
def generate_lr_pdf(lr_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "CONSIGNMENT NOTE (LR)", ln=True, align='C')
    pdf.ln(10)
    for key, value in lr_data.items():
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(40, 10, f"{key.upper()}:", 1)
        pdf.set_font("Arial", '', 10)
        pdf.cell(150, 10, str(value), 1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 2. MAIN LOGIC ---
df_m = load("masters")
df_t = load("trips")

menu = st.sidebar.selectbox("Modules", ["1. Masters Setup", "2. LR / Booking Entry"])

if menu == "2. LR / Booking Entry":
    st.header("📝 Consignment Entry (LR)")
    
    # Existing lists from Master
    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    broker_list = sorted(df_m[df_m['Type'] == 'Broker']['Name'].unique().tolist()) if not df_m.empty else []
    
    v_cat = st.radio("Trip Type", ["Own Fleet", "Market Hired"], horizontal=True)

    with st.form("lr_form"):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            d = st.date_input("LR Date", date.today())
            
            # --- SMART PARTY SELECTION ---
            new_pty_check = st.checkbox("New Party?")
            if new_pty_check:
                pty = st.text_input("Enter New Party Name*")
            else:
                pty = st.selectbox("Select Party*", ["Select"] + party_list)
            
            v_no = st.text_input("Vehicle No*")

        with c2:
            floc = st.text_input("From Location")
            tloc = st.text_input("To Location")
            mat = st.text_input("Material & Weight")

        with c3:
            fr = st.number_input("Total Freight*", min_value=0.0)
            
            if v_cat == "Market Hired":
                # --- SMART BROKER SELECTION ---
                new_brk_check = st.checkbox("New Broker?")
                if new_brk_check:
                    br = st.text_input("Enter New Broker Name*")
                else:
                    br = st.selectbox("Select Broker*", ["Select"] + broker_list)
                hc = st.number_input("Hired Charges")
            else:
                br, hc = "OWN", 0
        
        submitted = st.form_submit_button("🚀 SAVE & PRINT")

        if submitted:
            if pty and pty != "Select" and v_no and fr > 0:
                # 1. Agar nayi party hai, toh Master mein save karo
                if new_pty_check:
                    save("masters", ["Party", pty])
                
                # 2. Agar naya broker hai, toh Master mein save karo
                if v_cat == "Market Hired" and new_brk_check:
                    save("masters", ["Broker", br])
                
                # 3. LR No generate karo
                lr_id = f"LR-{date.today().strftime('%d%m')}-{v_no[-4:]}"
                
                # 4. Sheet mein Save karo (24 columns match)
                row = [str(d), lr_id, v_cat, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, floc, tloc, fr, hc, 0, 0, 0, 0, (fr-hc)]
                
                if save("trips", row):
                    st.success(f"LR {lr_id} Saved! Naya data Master mein update ho gaya.")
                    
                    # 5. PDF Button
                    lr_details = {'LR NO': lr_id, 'Date': str(d), 'Party': pty, 'Vehicle': v_no, 'Route': f"{floc} to {tloc}", 'Freight': fr}
                    st.download_button("🖨️ Download PDF", generate_lr_pdf(lr_details), f"{lr_id}.pdf", "application/pdf")
                    # Note: Rerun mandatory to refresh the dropdown list for next entry
                    st.info("Agli entry ke liye page ko refresh karein.")
                else:
                    st.error("Save failed!")
            else:
                st.warning("Details check karein!")
