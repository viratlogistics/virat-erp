import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP v3.0", layout="wide")

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

# --- 2. ADVANCED PDF ENGINE (Dynamic Branch Header) ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    
    # Dynamic Branch Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(100, 8, lr_data['BrName'], ln=0)
    pdf.set_font("Arial", '', 8)
    pdf.cell(90, 8, f"GST: {lr_data['BrGST']}", ln=1, align='R')
    
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.set_font("Arial", '', 8)
    pdf.multi_cell(190, 4, f"Address: {lr_data['BrAddr']}")
    pdf.line(10, 35, 200, 35)
    
    # LR Info
    pdf.ln(8)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr_data['LR No']}", 1); pdf.cell(45, 8, f"Date: {lr_data['Date']}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr_data['Vehicle']}", 1); pdf.cell(50, 8, f"Risk: {lr_data['Risk']}", 1, ln=True)

    # Multi-Party Section
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 7)
    y_s = pdf.get_y()
    pdf.multi_cell(63, 4, f"{lr_data['Cnor']}\nGST: {lr_data['CnorGST']}\nAddr: {lr_data['CnorAddr']}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 4, f"{lr_data['Cnee']}\nGST: {lr_data['CneeGST']}\nAddr: {lr_data['CneeAddr']}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 4, f"{lr_data['BillP']}\nInv: {lr_data['InvNo']}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3))
    
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr_data['ShipTo']}", 1, ln=True)
    
    # Product Details
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8); pdf.cell(70, 10, lr_data['Material'], 1); pdf.cell(30, 10, lr_data['Pkg'], 1); pdf.cell(30, 10, f"{lr_data['NetWt']}/{lr_data['ChgWt']}", 1); pdf.cell(30, 10, f"{lr_data['From']}-{lr_data['To']}", 1)
    amt = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)

    pdf.ln(5); pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, f"BANK: {lr_data['Bank']} | Ins: {lr_data['InsBy']} | PaidBy: {lr_data['PaidBy']}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, f"For {lr_data['BrName']}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN LOGIC ---
df_m = load("masters")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

# --- UPDATED MASTER SETUP ---
if menu == "1. Masters Setup":
    st.header("🏗️ Professional Master Setup")
    m_type = st.radio("Category", ["Party", "Branch (My Company)", "Broker", "Vehicle", "Bank"], horizontal=True)
    
    with st.form("master_form_v3", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input(f"{m_type} Name*")
            gst = st.text_input("GST Number")
        with col2:
            contact = st.text_input("Contact Number")
            address = st.text_area("Full Address")
        
        # Bank specific fields
        bank_details = ""
        if m_type == "Bank":
            bank_details = st.text_input("A/C No & IFSC")

        if st.form_submit_button(f"Add {m_type}"):
            if name:
                # Store as JSON string or multi-column if needed. 
                # For simplicity, we save: Type, Name, GST, Address, Contact, BankDetails
                save("masters", [m_type, name, gst, address, contact, bank_details])
                st.success(f"{name} added to {m_type}!"); st.rerun()

    st.divider()
    st.subheader(f"Existing {m_type}s")
    if not df_m.empty:
        st.dataframe(df_m[df_m['Type'] == m_type], use_container_width=True)

# --- UPDATED LR ENTRY ---
elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry v3.0")
    if st.button("🆕 START NEW ENTRY"):
        st.session_state.reset_trigger += 1
        st.session_state.pdf_ready = None
        st.rerun()

    # Data Loading
    parties = df_m[df_m['Type'] == 'Party']
    branches = df_m[df_m['Type'] == 'Branch (My Company)']
    banks = df_m[df_m['Type'] == 'Bank']
    vehicles = df_m[df_m['Type'] == 'Vehicle']
    brokers = df_m[df_m['Type'] == 'Broker']

    k = st.session_state.reset_trigger
    
    st.markdown("### 🏢 Business Unit Selection")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        sel_br = st.selectbox("Select Our Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
    with col_b2:
        sel_bank = st.selectbox("Select Bank*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")

    # Fetching Branch Details for PDF
    br_info = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else None
    bk_info = banks[banks['Name'] == sel_bank].iloc[0] if sel_bank != "Select" else None

    st.markdown("---")
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_no = st.text_input("LR Number*", value=f"VL-{date.today().strftime('%y%m%d%H%M')}", key=f"lrno_{k}")
        bill_pty_name = st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
    
    with cp2:
        cnor_name = st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
        # Auto-fetch Consignor GST/Address
        cnor_data = parties[parties['Name'] == cnor_name].iloc[0] if cnor_name != "Select" else None
        cnee_name = st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        # Auto-fetch Consignee GST/Address
        cnee_data = parties[parties['Name'] == cnee_name].iloc[0] if cnee_name != "Select" else None

    with cp3:
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")
        ship_to = st.text_area("Specific Ship-To Address", value=cnee_data['Address'] if cnee_data is not None else "", key=f"st_{k}")

    with st.form(f"lr_form_v3_{k}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Vehicle*", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            mat = st.text_input("Material Name")
        with c2:
            fl, tl = st.text_input("From City"), st.text_input("To City")
            pkg = st.selectbox("Packaging", ["Drums", "Bags", "Boxes", "Loose"])
            inv_no = st.text_input("Inv No & Date")
        with c3:
            n_wt, c_wt = st.number_input("Net Weight"), st.number_input("Charged Weight")
            fr = st.number_input("Total Freight*", min_value=0.0)
            show_fr = st.checkbox("Show Freight in Print?", value=True)

        if st.form_submit_button("🚀 SAVE & GENERATE PDF"):
            if sel_br != "Select" and bill_pty_name != "Select" and fr > 0:
                row = [str(d), lr_no, v_cat, bill_pty_name, cnee_name, paid_by, n_wt, c_wt, pkg, risk, mat, "N/A", v_no, "Driver", "N/A", fl, tl, fr, 0, 0, 0, 0, 0, fr]
                if save("trips", row):
                    st.success("✅ LR Saved!")
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Risk": risk,
                        "BrName": br_info['Name'], "BrGST": br_info['GST'], "BrAddr": br_info['Address'],
                        "BillP": bill_pty_name, "Cnor": cnor_name, "CnorGST": cnor_data['GST'] if cnor_data is not None else "", "CnorAddr": cnor_data['Address'] if cnor_data is not None else "",
                        "Cnee": cnee_name, "CneeGST": cnee_data['GST'] if cnee_data is not None else "", "CneeAddr": cnee_data['Address'] if cnee_data is not None else "",
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "From": fl, "To": tl, "Freight": fr,
                        "Bank": f"{bk_info['Name']} - {bk_info['BankDetails']}" if bk_info is not None else "N/A",
                        "InsBy": "N/A", "PaidBy": paid_by, "InvNo": inv_no, "ShipTo": ship_to
                    }
            else: st.error("Branch, Billing Party and Freight are Mandatory!")

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, show_fr), f"LR_{lr_no}.pdf")
