import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP v3.1", layout="wide")

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

# --- 2. UPDATED PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    
    # Header - Dynamic Branch
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(100, 8, lr_data.get('BrName', 'VIRAT LOGISTICS'), ln=0)
    pdf.set_font("Arial", '', 8)
    pdf.cell(90, 8, f"GST: {lr_data.get('BrGST', 'N/A')}", ln=1, align='R')
    
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.set_font("Arial", '', 7)
    pdf.multi_cell(190, 3, f"Address: {lr_data.get('BrAddr', 'N/A')}")
    
    # Notice Box (As per your file)
    pdf.set_y(25); pdf.set_x(110)
    pdf.set_font("Arial", 'B', 7)
    pdf.multi_cell(90, 3, "Notice: Without the consignee's written permission this consignment will not be diverted, re-routed, or rebooked.", 1)
    
    pdf.line(10, 38, 200, 38); pdf.ln(10)
    
    # Info Grid
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr_data.get('LR No', '')}", 1); pdf.cell(45, 8, f"Date: {lr_data.get('Date', '')}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr_data.get('Vehicle', '')}", 1); pdf.cell(50, 8, f"Risk: {lr_data.get('Risk', '')}", 1, ln=True)

    # Party Box
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 7); y_s = pdf.get_y()
    pdf.multi_cell(63, 4, f"{lr_data.get('Cnor', '')}\nGST: {lr_data.get('CnorGST', '')}\nAddr: {lr_data.get('CnorAddr', '')}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 4, f"{lr_data.get('Cnee', '')}\nGST: {lr_data.get('CneeGST', '')}\nAddr: {lr_data.get('CneeAddr', '')}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 4, f"{lr_data.get('BillP', '')}\nInv: {lr_data.get('InvNo', '')}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3))
    
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr_data.get('ShipTo', '')}", 1, ln=True)
    
    # Table
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight (N/C)", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8); pdf.cell(70, 10, lr_data.get('Material', ''), 1); pdf.cell(30, 10, lr_data.get('Pkg', ''), 1); pdf.cell(30, 10, f"{lr_data.get('NetWt',0)}/{lr_data.get('ChgWt',0)}", 1); pdf.cell(30, 10, f"{lr_data.get('From', '')}-{lr_data.get('To', '')}", 1)
    amt = f"Rs. {lr_data.get('Freight',0)}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)

    pdf.ln(5); pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, f"BANK: {lr_data.get('Bank', '')} | PaidBy: {lr_data.get('PaidBy', '')}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, f"For {lr_data.get('BrName', 'VIRAT LOGISTICS')}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. LOGIC ---
df_m = load("masters")
if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Professional Master Setup")
    m_type = st.radio("Category", ["Party", "Branch (My Company)", "Broker", "Vehicle", "Bank"], horizontal=True)
    with st.form("m_form_v3", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(f"{m_type} Name*"); gst = st.text_input("GST Number")
        with c2:
            contact = st.text_input("Contact"); address = st.text_area("Address")
        bank_info = st.text_input("A/C No & IFSC (For Bank only)") if m_type == "Bank" else ""
        if st.form_submit_button("Add Master"):
            if name: save("masters", [m_type, name, gst, address, contact, bank_info]); st.success("Saved!"); st.rerun()
    if not df_m.empty: st.dataframe(df_m[df_m['Type'] == m_type], use_container_width=True)

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry v3.1")
    if st.button("🆕 START NEW ENTRY"):
        st.session_state.reset_trigger += 1; st.session_state.pdf_ready = None; st.rerun()

    k = st.session_state.reset_trigger
    # Masters Filtering
    parties = df_m[df_m['Type'] == 'Party']
    branches = df_m[df_m['Type'] == 'Branch (My Company)']
    banks = df_m[df_m['Type'] == 'Bank']
    vehicles = df_m[df_m['Type'] == 'Vehicle']
    brokers = df_m[df_m['Type'] == 'Broker']

    st.markdown("### 🏢 Unit & Bank")
    cb1, cb2 = st.columns(2)
    with cb1: sel_br = st.selectbox("Select Our Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
    with cb2: sel_bank = st.selectbox("Select Bank*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")

    st.divider()
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_no = st.text_input("LR Number*", value=f"VL-{date.today().strftime('%y%m%d%H%M')}", key=f"lrno_{k}")
        is_new_p = st.checkbox("New Billing Party?")
        bill_pty = st.text_input("New Billing Party Name") if is_new_p else st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
    with cp2:
        is_new_cn = st.checkbox("New Consignor?")
        cnor = st.text_input("New Consignor Name") if is_new_cn else st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
        cnor_gst = st.text_input("Consignor GST (Manual)") if is_new_cn else ""
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")
    with cp3:
        is_new_ce = st.checkbox("New Consignee?")
        cnee = st.text_input("New Consignee Name") if is_new_ce else st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")

    # Fetch Data for selected items
    br_d = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
    bk_d = banks[banks['Name'] == sel_bank].iloc[0] if sel_bank != "Select" else {}
    cnor_d = parties[parties['Name'] == cnor].iloc[0] if not is_new_cn and cnor != "Select" else {}
    cnee_d = parties[parties['Name'] == cnee].iloc[0] if not is_new_ce and cnee != "Select" else {}

    with st.form(f"lr_form_{k}"):
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Own Vehicle*", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            ship_to = st.text_area("Ship-To Address", value=cnee_d.get('Address', ''))
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat, pkg = st.text_input("Material"), st.selectbox("Packaging", ["Drums", "Bags", "Boxes", "Loose"])
            inv_no = st.text_input("Inv No & Date")
        with c3:
            n_wt, c_wt = st.number_input("Net Weight"), st.number_input("Chg Weight")
            fr = st.number_input("Total Freight*", min_value=0.0)
            show_fr = st.checkbox("Show Freight in Print?", value=True)
            if v_cat == "Market Hired": hc = st.number_input("Hired Charges")
            else: hc = 0.0

        if st.form_submit_button("🚀 SAVE LR"):
            if sel_br != "Select" and bill_pty and fr > 0:
                # Save New Master on the fly
                if is_new_p: save("masters", ["Party", bill_pty, "", "", "", ""])
                if is_new_cn: save("masters", ["Party", cnor, cnor_gst, "", "", ""])
                
                row = [str(d), lr_no, v_cat, bill_pty, cnee, paid_by, n_wt, c_wt, pkg, risk, mat, "N/A", v_no, "Driver", "N/A", fl, tl, fr, hc, 0, 0, 0, 0, (fr-hc)]
                if save("trips", row):
                    st.success("✅ LR Saved!")
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Risk": risk,
                        "BrName": br_d.get('Name','VIRAT'), "BrGST": br_d.get('GST',''), "BrAddr": br_d.get('Address',''),
                        "BillP": bill_pty, "Cnor": cnor, "CnorGST": cnor_d.get('GST', cnor_gst), "CnorAddr": cnor_d.get('Address', ''),
                        "Cnee": cnee, "CneeGST": cnee_d.get('GST', ''), "CneeAddr": cnee_d.get('Address', ''),
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "From": fl, "To": tl, "Freight": fr,
                        "Bank": f"{bk_d.get('Name','')} {bk_d.get('BankDetails','')}", "PaidBy": paid_by, "InvNo": inv_no, "ShipTo": ship_to
                    }
            else: st.error("Branch, Billing Party and Freight are Mandatory!")

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, show_fr), f"LR_{lr_no}.pdf")
