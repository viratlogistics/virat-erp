import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONNECTION & PDF ENGINE ---
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

def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    # Header Section
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 8, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True, align='C')
    pdf.set_font("Arial", '', 8)
    pdf.multi_cell(190, 4, "Plot No 130, Nr Manglam Werehouse, Kuwarda Road, Kosamba, Gujarat 394120", align='C')
    pdf.line(10, 32, 200, 32)
    
    # LR Info
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(60, 8, f"LR No: {lr_data['LR No']}", 1)
    pdf.cell(60, 8, f"Date: {lr_data['Date']}", 1)
    pdf.cell(70, 8, f"Vehicle: {lr_data['Vehicle']}", 1, ln=True)
    
    # Consignor/Consignee
    pdf.ln(2)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(95, 7, "CONSIGNOR (From)", 1, 0, 'C', True)
    pdf.cell(95, 7, "CONSIGNEE (To)", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 9)
    y_start = pdf.get_y()
    pdf.multi_cell(95, 6, f"Name: {lr_data['Party']}\nGST: {lr_data['Cnor_GST']}", 1, 'L')
    y_end1 = pdf.get_y()
    
    pdf.set_y(y_start)
    pdf.set_x(105)
    pdf.multi_cell(95, 6, f"Name: {lr_data['Cnee']}\nGST: {lr_data['Cnee_GST']}", 1, 'L')
    y_end2 = pdf.get_y()
    pdf.set_y(max(y_end1, y_end2))
    
    # Material Details
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(110, 8, "Material Description", 1)
    pdf.cell(40, 8, "Route", 1)
    pdf.cell(40, 8, "Freight", 1, ln=True)
    
    pdf.set_font("Arial", '', 9)
    pdf.cell(110, 10, str(lr_data['Material']), 1)
    pdf.cell(40, 10, f"{lr_data['From']}-{lr_data['To']}", 1)
    amt = f"Rs. {lr_data['Freight']}" if show_fr else "To be billed"
    pdf.cell(40, 10, amt, 1, ln=True)
    
    # Footer
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "Bank: BOB | A/C: 53480400000059 | IFSC: BARBOSARSUR", ln=True)
    pdf.ln(10)
    pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L')
    pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 2. MAIN LOGIC ---
df_m = load("masters")
menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

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
        st.table(df_m[df_m['Type'] == m_type][['Name']])

elif menu == "2. LR Entry":
    st.header("📝 Create New LR")
    
    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    broker_list = sorted(df_m[df_m['Type'] == 'Broker']['Name'].unique().tolist()) if not df_m.empty else []
    own_v = sorted(df_m[df_m['Type'] == 'Vehicle']['Name'].unique().tolist()) if not df_m.empty else []
    
    v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True)

    st.markdown("### 🏢 Party & Broker Selection")
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        is_new_p = st.checkbox("New Party?")
        pty = st.text_input("Consignor Name*") if is_new_p else st.selectbox("Consignor*", ["Select"] + party_list)
        cnor_gst = st.text_input("Consignor GST")
    with cp2:
        if v_cat == "Market Hired":
            is_new_b = st.checkbox("New Broker?")
            br = st.text_input("Broker Name*") if is_new_b else st.selectbox("Broker*", ["Select"] + broker_list)
        else: br = "OWN"
    with cp3:
        show_fr_in_pdf = st.checkbox("Show Freight in Print?", value=True)

    with st.form("lr_form"):
        c1, c2 = st.columns(2)
        with c1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Vehicle*", ["Select"] + own_v) if v_cat == "Own Fleet" else st.text_input("Vehicle No*")
            cnee = st.text_input("Consignee Name*")
            cnee_gst = st.text_input("Consignee GST")
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material")
            fr = st.number_input("Freight*", min_value=0.0)
            if v_cat == "Market Hired":
                hc = st.number_input("Hired Charges")
                dsl, toll, drv = 0.0, 0.0, 0.0
            else:
                hc = 0.0
                dsl, toll, drv = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Adv")
        
        submitted = st.form_submit_button("🚀 SAVE LR & PRINT")

    if submitted:
        if pty and pty != "Select" and v_no and v_no != "Select" and fr > 0:
            if is_new_p: save("masters", ["Party", pty])
            if v_cat == "Market Hired" and is_new_b: save("masters", ["Broker", br])
            
            lr_id = f"LR-{date.today().strftime('%d%m')}-{v_no[-4:]}"
            prof = (fr - hc) if v_cat == "Market Hired" else (fr - dsl - toll - drv)
            row = [str(d), lr_id, v_cat, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, fl, tl, fr, hc, dsl, drv, toll, 0, prof]
            
            if save("trips", row):
                st.success(f"LR {lr_id} Saved!")
                p_data = {"LR No": lr_id, "Date": str(d), "Party": pty, "Vehicle": v_no, "From": fl, "To": tl, "Material": mat, "Freight": fr, "Cnee": cnee, "Cnee_GST": cnee_gst, "Cnor_GST": cnor_gst}
                st.download_button("🖨️ Download PDF", generate_lr_pdf(p_data, show_fr_in_pdf), f"{lr_id}.pdf")
            else: st.error("Error Saving!")
        else: st.error("Fields missing!")
