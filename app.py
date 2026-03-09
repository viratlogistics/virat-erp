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

# --- 2. PROFESSIONAL PDF ENGINE (Attached File Format) ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    
    # Header Section
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(190, 8, "Virat Logistics", ln=True, align='L')
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True, align='L')
    pdf.set_font("Arial", '', 8)
    pdf.multi_cell(90, 4, "Branch Code: 002\nPlot No 130, Nr Manglam Werehouse\nKuwarda Road, Kosamba, Gujarat 394120")
    
    # Notice Box (As per attached PDF)
    pdf.set_y(25)
    pdf.set_x(110)
    pdf.set_font("Arial", 'B', 7)
    pdf.multi_cell(90, 3, "Notice: Without the consignee's written permission this consignment will not be diverted, re-routed, or rebooked. Lorry Receipt will be delivered to the only consignee.", 1)
    
    pdf.line(10, 42, 200, 42)
    
    # LR Info Table
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
    pdf.multi_cell(95, 5, f"Name: {lr_data['Party']}\nGST: {lr_data['Cnor_GST']}\nBilling: {lr_data['PaidBy']}", 1, 'L')
    y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(105)
    pdf.multi_cell(95, 5, f"Name: {lr_data['Cnee']}\nGST: {lr_data['Cnee_GST']}\nInsurance: {lr_data['InsBy']}", 1, 'L')
    pdf.set_y(max(y_e1, pdf.get_y()))

    # Product Table
    pdf.ln(4)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(70, 7, "Product / Material", 1)
    pdf.cell(30, 7, "Pkg Type", 1)
    pdf.cell(30, 7, "Net/Chg Wt", 1)
    pdf.cell(30, 7, "Route", 1)
    pdf.cell(30, 7, "Freight", 1, ln=True)

    pdf.set_font("Arial", '', 8)
    pdf.cell(70, 10, lr_data['Material'], 1)
    pdf.cell(30, 10, lr_data['Pkg'], 1)
    pdf.cell(30, 10, f"{lr_data['NetWt']}/{lr_data['ChgWt']}", 1)
    pdf.cell(30, 10, f"{lr_data['From']}-{lr_data['To']}", 1)
    amt = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)

    # Bank Details Section
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, f"BANK DETAILS: {lr_data['Bank']}", ln=True)
    
    # Terms (Snippet from your file)
    pdf.set_font("Arial", '', 6)
    pdf.multi_cell(190, 3, "Terms: 1) Goods at owner's risk. 2) No claim for leakage/breakage. 3) Jurisdiction at Kosamba court only.")
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(95, 5, "Consignor Signature", 0, 0, 'L')
    pdf.cell(95, 5, "For VIRAT LOGISTICS (Auth. Sign)", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN LOGIC ---
df_m = load("masters")
menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank"])
    with st.form("m_form", clear_on_submit=True):
        val = st.text_input(f"New {m_type} Detail (Name/Bank Info)")
        if st.form_submit_button("Add Master"):
            if val: 
                save("masters", [m_type, val])
                st.success(f"{val} Saved!"); st.rerun()
    st.divider()
    if not df_m.empty: st.table(df_m[df_m['Type'] == m_type][['Name']])

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    
    party_list = sorted(df_m[df_m['Type'] == 'Party']['Name'].unique().tolist()) if not df_m.empty else []
    bank_list = sorted(df_m[df_m['Type'] == 'Bank']['Name'].unique().tolist()) if not df_m.empty else []
    own_v = sorted(df_m[df_m['Type'] == 'Vehicle']['Name'].unique().tolist()) if not df_m.empty else []
    
    # --- TOP SETTINGS ---
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True)
        is_new_p = st.checkbox("New Consignor?")
        pty = st.text_input("Consignor Name*") if is_new_p else st.selectbox("Consignor*", ["Select"] + party_list)
        cnor_gst = st.text_input("Consignor GST")
    with cp2:
        risk_type = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True)
        ins_paid_by = st.selectbox("Insurance Paid By", ["N/A", "Consignor", "Consignee", "Transporter"]) if risk_type == "Insured" else "N/A"
        sel_bank = st.selectbox("Select Bank for PDF*", ["Select"] + bank_list)
    with cp3:
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee"])
        show_fr_in_pdf = st.checkbox("Show Freight in Print?", value=True)
        if st.button("♻️ Reset Form"): st.rerun()

    with st.form("lr_form_pro", clear_on_submit=True):
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Vehicle*", ["Select"] + own_v) if v_cat == "Own Fleet" else st.text_input("Vehicle No*")
            cnee = st.text_input("Consignee Name*")
            cnee_gst = st.text_input("Consignee GST")
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material Name")
            pkg = st.selectbox("Packaging Type", ["Drums", "Bags", "Boxes", "Loose", "Pallets"])
        with c3:
            n_wt = st.number_input("Net Weight")
            c_wt = st.number_input("Charged Weight")
            fr = st.number_input("Freight*", min_value=0.0)
            if v_cat == "Own Fleet": dsl, toll, drv, hc = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Adv"), 0.0
            else: hc, dsl, toll, drv = st.number_input("Hired Charges"), 0.0, 0.0, 0.0

        submitted = st.form_submit_button("🚀 SAVE & GENERATE BILTY")

    if submitted:
        if pty and v_no and sel_bank != "Select" and fr > 0:
            if is_new_p: save("masters", ["Party", pty])
            lr_id = f"LR-{date.today().strftime('%d%m')}-{v_no[-4:]}"
            prof = (fr - hc) if v_cat == "Market Hired" else (fr - dsl - toll - drv)
            
            row = [str(d), lr_id, v_cat, pty, cnee, paid_by, n_wt, c_wt, pkg, risk_type, mat, ins_paid_by, v_no, "Driver", "OWN", fl, tl, fr, hc, dsl, drv, toll, 0, prof]
            
            if save("trips", row):
                st.success(f"LR {lr_id} Saved!")
                p_data = {"LR No": lr_id, "Date": str(d), "Party": pty, "Vehicle": v_no, "From": fl, "To": tl, "Material": mat, "Freight": fr, "Cnee": cnee, "Cnee_GST": cnee_gst, "Cnor_GST": cnor_gst, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "PaidBy": paid_by, "Risk": risk_type, "InsBy": ins_paid_by, "Bank": sel_bank}
                st.download_button("🖨️ Download Bilty PDF", generate_lr_pdf(p_data, show_fr_in_pdf), f"{lr_id}.pdf")
            else: st.error("Save Error")
