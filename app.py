import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

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

def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18); pdf.cell(100, 8, "Virat Logistics", ln=1)
    pdf.set_font("Arial", 'I', 8); pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.line(10, 25, 200, 25)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(60, 8, f"LR No: {lr_data['LR No']}", 1); pdf.cell(60, 8, f"Date: {lr_data['Date']}", 1); pdf.cell(70, 8, f"Vehicle: {lr_data['Vehicle']}", 1, ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"BILLING PARTY: {lr_data['BillP']}", 1, ln=True)
    pdf.cell(95, 6, f"CONSIGNOR: {lr_data['Cnor']}", 1); pdf.cell(95, 6, f"CONSIGNEE: {lr_data['Cnee']}", 1, ln=True)
    pdf.multi_cell(190, 5, f"SHIP TO: {lr_data['ShipTo']}", 1)
    pdf.ln(5)
    pdf.cell(80, 8, "Material", 1); pdf.cell(40, 8, "Weight (N/C)", 1); pdf.cell(70, 8, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.cell(80, 10, lr_data['Material'], 1); pdf.cell(40, 10, f"{lr_data['NetWt']}/{lr_data['ChgWt']}", 1)
    amt = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    pdf.cell(70, 10, amt, 1, ln=True)
    pdf.ln(10); pdf.cell(190, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 2. MAIN LOGIC ---
df_m = load("masters")
menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank"])
    with st.form("m_form", clear_on_submit=True):
        val = st.text_input(f"New {m_type}")
        if st.form_submit_button("Add"):
            if val: save("masters", [m_type, val]); st.success("Saved!"); st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")

    # --- RESET FUNCTION ---
    if st.button("🆕 START NEW ENTRY (CLEAR ALL)"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    bank_list = sorted(df_m[df_m['Type'] == 'Bank']['Name'].unique().tolist()) if not df_m.empty else []
    own_v = sorted(df_m[df_m['Type'] == 'Vehicle']['Name'].unique().tolist()) if not df_m.empty else []

    # UI Layout
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key="vcat")
        lr_no = st.text_input("LR Number*", key="lr_no_k")
        bill_pty = st.selectbox("Billing Party*", ["Select"] + party_list, key="bp_k")
    with cp2:
        cnor_name = st.text_input("Consignor Name*", key="cnor_k")
        cnee_name = st.text_input("Consignee Name*", key="cnee_k")
        sel_bank = st.selectbox("Select Bank*", ["Select"] + bank_list, key="bank_k")
    with cp3:
        ship_to = st.text_area("Ship To Address", key="ship_k")
        show_fr_in_pdf = st.checkbox("Show Freight in Print?", value=True, key="fr_pr_k")

    with st.form("lr_form_final"):
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Trip Date", date.today(), key="date_k")
            v_no = st.selectbox("Own Vehicle", ["Select"] + own_v) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No")
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material")
            pkg = st.selectbox("Pkg", ["Drums", "Bags", "Boxes", "Loose"])
        with c3:
            n_wt = st.number_input("Net Weight", min_value=0.0)
            c_wt = st.number_input("Charged Weight", min_value=0.0)
            fr = st.number_input("Total Freight*", min_value=0.0)
        
        submitted = st.form_submit_button("🚀 SAVE LR")

    if submitted:
        if bill_pty != "Select" and fr > 0:
            row = [str(d), lr_no, v_cat, bill_pty, cnee_name, "Paid", n_wt, c_wt, pkg, "Risk", mat, "N/A", v_no, "Driver", "OWN", fl, tl, fr, 0, 0, 0, 0, 0, fr]
            if save("trips", row):
                st.success(f"✅ LR {lr_no} Saved!")
                st.session_state.pdf_data = {"LR No": lr_no, "Date": str(d), "BillP": bill_pty, "Cnor": cnor_name, "Cnee": cnee_name, "Vehicle": v_no, "From": fl, "To": tl, "Material": mat, "Freight": fr, "NetWt": n_wt, "ChgWt": c_wt, "Pkg": pkg, "Bank": sel_bank, "ShipTo": ship_to}

    if "pdf_data" in st.session_state:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_data, show_fr_in_pdf), f"LR_{lr_no}.pdf")
