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

# --- 2. PROFESSIONAL PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(100, 8, "Virat Logistics", ln=0)
    pdf.set_font("Arial", '', 8)
    pdf.cell(90, 8, f"Branch Code: 002", ln=1, align='R')
    
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.set_font("Arial", '', 8)
    pdf.multi_cell(190, 4, "Plot No 130, Nr Manglam Werehouse, Kuwarda Road, Kosamba, Gujarat 394120")
    
    pdf.line(10, 35, 200, 35)
    
    # LR Info Row
    pdf.ln(8)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr_data['LR No']}", 1)
    pdf.cell(45, 8, f"Date: {lr_data['Date']}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr_data['Vehicle']}", 1)
    pdf.cell(50, 8, f"Risk: {lr_data['Risk']}", 1, ln=True)

    # Consignor / Consignee
    pdf.ln(2)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(95, 6, "CONSIGNOR", 1, 0, 'L', True)
    pdf.cell(95, 6, "CONSIGNEE", 1, 1, 'L', True)
    
    pdf.set_font("Arial", '', 8)
    y_s = pdf.get_y()
    pdf.multi_cell(95, 5, f"Name: {lr_data['Party']}\nGST: {lr_data['Cnor_GST']}\nInvoice: {lr_data['InvNo']}", 1, 'L')
    y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(105)
    pdf.multi_cell(95, 5, f"Name: {lr_data['Cnee']}\nGST: {lr_data['Cnee_GST']}\nBilling: {lr_data['PaidBy']}", 1, 'L')
    pdf.set_y(max(y_e1, pdf.get_y()))

    # Product Table
    pdf.ln(4)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(70, 7, "Product / Material", 1)
    pdf.cell(30, 7, "Packaging", 1)
    pdf.cell(30, 7, "Weight (N/C)", 1)
    pdf.cell(30, 7, "Route", 1)
    pdf.cell(30, 7, "Freight", 1, ln=True)

    pdf.set_font("Arial", '', 8)
    pdf.cell(70, 10, lr_data['Material'], 1)
    pdf.cell(30, 10, lr_data['Pkg'], 1)
    pdf.cell(30, 10, f"{lr_data['NetWt']}/{lr_data['ChgWt']}", 1)
    pdf.cell(30, 10, f"{lr_data['From']}-{lr_data['To']}", 1)
    amt = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)

    # Bank & Insurance Details
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, f"Insurance: {lr_data['InsBy']} | BANK: {lr_data['Bank']}", ln=True)
    
    pdf.set_font("Arial", '', 6)
    pdf.multi_cell(190, 3, "Terms: 1) Goods at owner's risk. 2) Jurisdiction at Kosamba court only.")
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(95, 5, "Consignor Signature", 0, 0, 'L')
    pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN LOGIC ---
df_m = load("masters")
menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank"])
    with st.form("m_form", clear_on_submit=True):
        val = st.text_input(f"New {m_type} Detail")
        if st.form_submit_button("Add Master"):
            if val: 
                save("masters", [m_type, val])
                st.success(f"{val} Saved!"); st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    
    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    bank_list = sorted(df_m[df_m['Type'] == 'Bank']['Name'].unique().tolist()) if not df_m.empty else []
    own_v = sorted(df_m[df_m['Type'] == 'Vehicle']['Name'].unique().tolist()) if not df_m.empty else []
    
    # Session State for keeping PDF visible
    if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        lr_mode = st.radio("LR Number*", ["Auto Generated", "Manual Entry"], horizontal=True)
        lr_val = f"VL-{date.today().strftime('%y%m%d')}" if lr_mode == "Auto Generated" else ""
        lr_no = st.text_input("LR Number*", value=lr_val)
        is_new_p = st.checkbox("New Consignor?")
        pty = st.text_input("Consignor Name*") if is_new_p else st.selectbox("Consignor*", ["Select"] + party_list)
        cnor_gst = st.text_input("Consignor GST")
    with cp2:
        risk_type = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True)
        ins_by = st.selectbox("Insurance Paid By", ["N/A", "Consignor", "Consignee", "Transporter"]) if risk_type == "Insured" else "N/A"
        sel_bank = st.selectbox("Select Bank*", ["Select"] + bank_list)
        inv_no = st.text_input("Invoice No & Date")
    with cp3:
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee"])
        show_fr_in_pdf = st.checkbox("Show Freight in Print?", value=True)
        if st.button("♻️ Reset Form"):
            st.session_state.pdf_ready = None
            st.rerun()

    with st.form("lr_form_final", clear_on_submit=False):
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Trip Date", date.today())
            v_no = st.selectbox("Vehicle*", ["Select"] + own_v) if st.radio("Vehicle Type", ["Own", "Market"]) == "Own" else st.text_input("Market Vehicle No*")
            cnee = st.text_input("Consignee Name*")
            cnee_gst = st.text_input("Consignee GST")
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material")
            pkg = st.selectbox("Pkg Type", ["Drums", "Bags", "Boxes", "Loose"])
        with c3:
            n_wt, c_wt = st.number_input("Net Weight"), st.number_input("Charged Weight")
            fr = st.number_input("Total Freight*", min_value=0.0)
            hc = st.number_input("Hired Charges (If Market)")

        submitted = st.form_submit_button("🚀 SAVE & LOCK LR")

    if submitted:
        if pty and lr_no and fr > 0:
            if is_new_p: save("masters", ["Party", pty])
            row = [str(d), lr_no, "Trip", pty, cnee, paid_by, n_wt, c_wt, pkg, risk_type, mat, ins_by, v_no, "Driver", "Broker", fl, tl, fr, hc, 0, 0, 0, 0, (fr-hc)]
            if save("trips", row):
                st.success(f"✅ LR {lr_no} Saved!")
                st.session_state.pdf_ready = {"LR No": lr_no, "Date": str(d), "Party": pty, "Vehicle": v_no, "From": fl, "To": tl, "Material": mat, "Freight": fr, "Cnee": cnee, "Cnee_GST": cnee_gst, "Cnor_GST": cnor_gst, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "PaidBy": paid_by, "Risk": risk_type, "InsBy": ins_by, "Bank": sel_bank, "InvNo": inv_no}
            else: st.error("Save Error")

    # Persistent Download Button
    if st.session_state.pdf_ready:
        st.divider()
        st.download_button("📥 DOWNLOAD BILTY PDF", generate_lr_pdf(st.session_state.pdf_ready, show_fr_in_pdf), f"{st.session_state.pdf_ready['LR No']}.pdf")
