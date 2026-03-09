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
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. PDF ENGINE ---
def generate_lr_pdf(lr_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "CONSIGNMENT NOTE (LR)", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    for key, value in lr_data.items():
        pdf.cell(50, 10, f"{key}:", 1)
        pdf.set_font("Arial", '', 10)
        pdf.cell(140, 10, str(value), 1, ln=True)
        pdf.set_font("Arial", 'B', 10)
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN NAVIGATION ---
menu = st.sidebar.selectbox("🚀 MODULES", ["1. Masters Setup", "2. LR / Booking Entry"])

# --- MODULE 1: MASTER SETUP (FIXED) ---
if menu == "1. Masters Setup":
    st.header("🏗️ Master Data Management")
    
    # Selection of type
    m_type = st.selectbox("Select Category", ["Party", "Broker", "Vehicle", "Driver"])
    
    # Form to add new
    with st.form("master_form", clear_on_submit=True):
        new_val = st.text_input(f"Enter New {m_type} Name/No.")
        if st.form_submit_button(f"Add {m_type}"):
            if new_val:
                save("masters", [m_type, new_val])
                st.success(f"{new_val} added!"); st.rerun()
    
    st.divider()
    
    # Display Current Masters
    st.subheader(f"Current {m_type} List")
    df_m = load("masters")
    if not df_m.empty:
        filtered_m = df_m[df_m['Type'] == m_type]
        if not filtered_m.empty:
            st.table(filtered_m[['Name']])
        else:
            st.info(f"No {m_type} found. Please add one.")
    else:
        st.warning("Master sheet is empty. Please add your first entry above.")

# --- MODULE 2: LR ENTRY (WITH PDF) ---
elif menu == "2. LR / Booking Entry":
    st.header("📝 Consignment Entry (LR)")
    df_m = load("masters")
    
    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    broker_list = sorted(df_m[df_m['Type'] == 'Broker']['Name'].unique().tolist()) if not df_m.empty else []
    
    v_cat = st.radio("Trip Type", ["Own Fleet", "Market Hired"], horizontal=True)

    with st.form("lr_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            new_pty = st.checkbox("New Party?")
            pty = st.text_input("New Party Name") if new_pty else st.selectbox("Select Party", ["Select"] + party_list)
            v_no = st.text_input("Vehicle No*")
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material/Weight")
        with c3:
            fr = st.number_input("Freight*", min_value=0.0)
            if v_type := v_cat == "Market Hired":
                new_brk = st.checkbox("New Broker?")
                br = st.text_input("New Broker") if new_brk else st.selectbox("Select Broker", ["Select"] + broker_list)
                hc = st.number_input("Hired Charges")
            else:
                br, hc = "OWN", 0
        
        if st.form_submit_button("🚀 SAVE & GENERATE PDF"):
            if pty and pty != "Select" and v_no and fr > 0:
                # Save New Master on-the-fly
                if new_pty: save("masters", ["Party", pty])
                if v_cat == "Market Hired" and "new_brk" in locals() and new_brk: save("masters", ["Broker", br])
                
                lr_id = f"LR-{date.today().strftime('%d%m')}-{v_no[-4:]}"
                row = [str(d), lr_id, v_cat, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, fl, tl, fr, hc, 0, 0, 0, 0, (fr-hc)]
                
                if save("trips", row):
                    st.success(f"LR {lr_id} Saved!")
                    lr_pdf_data = {"LR No": lr_id, "Date": str(d), "Party": pty, "Vehicle": v_no, "From": fl, "To": tl, "Freight": fr}
                    st.download_button("🖨️ Download PDF", generate_lr_pdf(lr_pdf_data), f"{lr_id}.pdf")
            else:
                st.error("Please fill required fields.")
