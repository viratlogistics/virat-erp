import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

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
    pdf.cell(190, 10, "CONSIGNMENT NOTE", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 11)
    for k, v in lr_data.items():
        pdf.cell(50, 10, f"{k}:", 1)
        pdf.cell(140, 10, str(v), 1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 3. UI LOGIC ---
df_m = load("masters")

menu = st.sidebar.selectbox("MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver"])
    with st.form("m_form", clear_on_submit=True):
        val = st.text_input(f"New {m_type} Name/No")
        if st.form_submit_button("Add Master"):
            if val: 
                save("masters", [m_type, val])
                st.success(f"{val} Saved!"); st.rerun()
    st.divider()
    if not df_m.empty:
        st.write(f"Existing {m_type}s:")
        st.table(df_m[df_m['Type'] == m_type][['Name']])

elif menu == "2. LR Entry":
    st.header("📝 Create New LR")
    
    # Pre-loading lists for dropdowns
    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    broker_list = sorted(df_m[df_m['Type'] == 'Broker']['Name'].unique().tolist()) if not df_m.empty else []
    own_vehicles = sorted(df_m[df_m['Type'] == 'Vehicle']['Name'].unique().tolist()) if not df_m.empty else []
    
    v_cat = st.radio("Trip Category*", ["Own Fleet", "Market Hired"], horizontal=True)

    # Placeholders for PDF button to avoid Form error
    pdf_placeholder = st.empty()

    with st.form("lr_form"):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            d = st.date_input("Date", date.today())
            new_p = st.checkbox("New Party?")
            if new_p:
                pty = st.text_input("Enter Party Name*")
            else:
                pty = st.selectbox("Select Party*", ["Select"] + party_list)
            
            if v_cat == "Own Fleet":
                v_no = st.selectbox("Select Own Vehicle*", ["Select"] + own_vehicles)
            else:
                v_no = st.text_input("Market Vehicle No*")
        
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material/Weight")
            fr = st.number_input("Total Freight*", min_value=0.0)

        with c3:
            if v_cat == "Market Hired":
                new_b = st.checkbox("New Broker?")
                if new_b:
                    br = st.text_input("Enter Broker Name*")
                else:
                    br = st.selectbox("Select Broker*", ["Select"] + broker_list)
                hc = st.number_input("Hired Charges")
                dsl, toll, drv_e = 0.0, 0.0, 0.0
            else:
                br, hc = "OWN", 0.0
                st.write("**Trip Expenses**")
                dsl = st.number_input("Diesel Expense")
                toll = st.number_input("Toll/Tax")
                drv_e = st.number_input("Driver Advance")

        submitted = st.form_submit_button("🚀 SAVE LR DETAILS")

    # PDF Button logic OUTSIDE the form
    if submitted:
        if pty and pty != "Select" and v_no and v_no != "Select" and fr > 0:
            if new_p: save("masters", ["Party", pty])
            if v_cat == "Market Hired" and 'new_b' in locals() and new_b: save("masters", ["Broker", br])
            
            lr_id = f"LR-{date.today().strftime('%d%m')}-{v_no[-4:]}"
            prof = (fr - hc) if v_cat == "Market Hired" else (fr - dsl - toll - drv_e)
            
            row = [str(d), lr_id, v_cat, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, fl, tl, fr, hc, dsl, drv_e, toll, 0, prof]
            
            if save("trips", row):
                st.success(f"LR {lr_id} Saved Successfully!")
                pdf_data = {"LR No": lr_id, "Date": str(d), "Party": pty, "Vehicle": v_no, "Route": f"{fl}-{tl}", "Freight": fr}
                btn_pdf = generate_lr_pdf(pdf_data)
                st.download_button("🖨️ Download & Print LR", btn_pdf, f"{lr_id}.pdf", "application/pdf")
            else:
                st.error("Sheet Sync Failed!")
        else:
            st.error("Details check karein! Party, Vehicle aur Freight bharna zaroori hai.")
