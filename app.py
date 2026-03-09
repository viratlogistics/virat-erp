import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONFIG & CONNECTION ---
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

# --- 2. PROFESSIONAL PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18); pdf.cell(100, 8, "Virat Logistics", ln=0)
    pdf.set_font("Arial", '', 8); pdf.cell(90, 8, "Branch Code: 002", ln=1, align='R')
    pdf.set_font("Arial", 'I', 8); pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.line(10, 30, 200, 30); pdf.ln(8)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr_data['LR No']}", 1); pdf.cell(45, 8, f"Date: {lr_data['Date']}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr_data['Vehicle']}", 1); pdf.cell(50, 8, f"Risk: {lr_data['Risk']}", 1, ln=True)

    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 8); y_s = pdf.get_y()
    pdf.multi_cell(63, 5, f"{lr_data['Cnor']}\nGST: {lr_data['CnorGST']}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 5, f"{lr_data['Cnee']}\nGST: {lr_data['CneeGST']}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 5, f"{lr_data['BillP']}\nInv: {lr_data['InvNo']}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3))
    
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr_data['ShipTo']}", 1, ln=True)
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8); pdf.cell(70, 10, lr_data['Material'], 1); pdf.cell(30, 10, lr_data['Pkg'], 1); pdf.cell(30, 10, f"{lr_data['NetWt']}/{lr_data['ChgWt']}", 1); pdf.cell(30, 10, f"{lr_data['From']}-{lr_data['To']}", 1)
    amt = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 8); 
    pdf.cell(190, 5, f"BANK: {lr_data['Bank']} | Insurance Paid By: {lr_data['InsBy']} | Freight Paid By: {lr_data['PaidBy']}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN LOGIC ---
df_m = load("masters")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

def reset_form():
    st.session_state.reset_trigger += 1
    st.session_state.pdf_ready = None
    st.rerun()

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank"])
    with st.form("m_form", clear_on_submit=True):
        val = st.text_input(f"New {m_type}")
        if st.form_submit_button("Add Master"):
            if val: save("masters", [m_type, val]); st.success("Saved!"); st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    st.button("🆕 START NEW ENTRY (CLEAR ALL)", on_click=reset_form)

    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    bank_list = sorted(df_m[df_m['Type'] == 'Bank']['Name'].unique().tolist()) if not df_m.empty else []
    own_v = sorted(df_m[df_m['Type'] == 'Vehicle']['Name'].unique().tolist()) if not df_m.empty else []
    broker_list = sorted(df_m[df_m['Type'] == 'Broker']['Name'].unique().tolist()) if not df_m.empty else []

    k = st.session_state.reset_trigger
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_mode = st.radio("LR No Mode", ["Auto", "Manual"], horizontal=True, key=f"lrmode_{k}")
        lr_no = st.text_input("LR Number*", value=f"VL-{date.today().strftime('%y%m%d%H%M')}" if lr_mode == "Auto" else "", key=f"lrno_{k}")
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"risk_{k}")
    with cp2:
        bill_pty = st.selectbox("Billing Party*", ["Select"] + party_list, key=f"bp_{k}")
        cnor_name = st.text_input("Consignor Name*", key=f"cnor_{k}")
        cnor_gst = st.text_input("Consignor GST", key=f"cgst_{k}")
        ins_by = st.selectbox("Insurance Paid By*", ["N/A", "Consignor", "Consignee", "Transporter"], key=f"ins_{k}")
    with cp3:
        cnee_name = st.text_input("Consignee Name*", key=f"cnee_{k}")
        cnee_gst = st.text_input("Consignee GST", key=f"cngst_{k}")
        sel_bank = st.selectbox("Select Bank*", ["Select"] + bank_list, key=f"bank_{k}")
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"paidby_{k}")

    with st.form(f"lr_form_{k}"):
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Own Vehicle*", ["Select"] + own_v) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            br = "OWN" if v_cat == "Own Fleet" else st.selectbox("Broker*", ["Select"] + broker_list)
            ship_to = st.text_area("Ship To Address")
        with c2:
            fl, tl = st.text_input("From City"), st.text_input("To City")
            mat, pkg = st.text_input("Material"), st.selectbox("Packaging", ["Drums", "Bags", "Boxes", "Loose", "Pallets"])
            inv_no = st.text_input("Invoice No & Date")
        with c3:
            n_wt, c_wt = st.number_input("Net Wt", min_value=0.0), st.number_input("Chg Wt", min_value=0.0)
            fr = st.number_input("Total Freight*", min_value=0.0)
            show_fr_in_pdf = st.checkbox("Show Freight in Print?", value=True)
            if v_cat == "Own Fleet": dsl, toll, drv, hc = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Adv"), 0.0
            else: hc, dsl, toll, drv = st.number_input("Hired Charges"), 0.0, 0.0, 0.0

        if st.form_submit_button("🚀 SAVE LR"):
            if bill_pty != "Select" and v_no and fr > 0:
                prof = (fr - hc) if v_cat == "Market Hired" else (fr - dsl - toll - drv)
                row = [str(d), lr_no, v_cat, bill_pty, cnee_name, paid_by, n_wt, c_wt, pkg, risk, mat, ins_by, v_no, "Driver", br, fl, tl, fr, hc, dsl, drv, toll, 0, prof]
                if save("trips", row):
                    st.success(f"✅ LR {lr_no} Saved!")
                    st.session_state.pdf_ready = {"LR No": lr_no, "Date": str(d), "BillP": bill_pty, "Cnor": cnor_name, "CnorGST": cnor_gst, "Vehicle": v_no, "From": fl, "To": tl, "Material": mat, "Freight": fr, "Cnee": cnee_name, "CneeGST": cnee_gst, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "Risk": risk, "InsBy": ins_by, "Bank": sel_bank, "InvNo": inv_no, "ShipTo": ship_to, "PaidBy": paid_by}
                else: st.error("Save Error")

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, show_fr_in_pdf), f"LR_{lr_no}.pdf")
