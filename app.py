import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP v3.2", layout="wide")

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
        data = ws.get_all_records()
        if not data: return pd.DataFrame(columns=['Type', 'Name', 'GST', 'Address', 'Contact', 'A_C_No', 'IFSC', 'Driver_Name', 'Driver_No'])
        df = pd.DataFrame(data)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Type', 'Name', 'GST', 'Address', 'Contact', 'A_C_No', 'IFSC', 'Driver_Name', 'Driver_No'])

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(100, 8, lr_data.get('BrName', 'VIRAT LOGISTICS'), ln=0)
    pdf.set_font("Arial", '', 8)
    pdf.cell(90, 8, f"GST: {lr_data.get('BrGST', '')}", ln=1, align='R')
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.set_font("Arial", '', 7)
    pdf.multi_cell(190, 3, f"Address: {lr_data.get('BrAddr', '')}")
    pdf.line(10, 38, 200, 38); pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr_data.get('LR No', '')}", 1); pdf.cell(45, 8, f"Date: {lr_data.get('Date', '')}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr_data.get('Vehicle', '')}", 1); pdf.cell(50, 8, f"Risk: {lr_data.get('Risk', '')}", 1, ln=True)
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 7); y_s = pdf.get_y()
    pdf.multi_cell(63, 4, f"{lr_data.get('Cnor', '')}\nGST: {lr_data.get('CnorGST', '')}\nAddr: {lr_data.get('CnorAddr', '')}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 4, f"{lr_data.get('Cnee', '')}\nGST: {lr_data.get('CneeGST', '')}\nAddr: {lr_data.get('CneeAddr', '')}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 4, f"{lr_data.get('BillP', '')}\nInv: {lr_data.get('InvNo', '')}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3))
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr_data.get('ShipTo', '')}", 1, ln=True)
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8); pdf.cell(70, 10, lr_data.get('Material', ''), 1); pdf.cell(30, 10, lr_data.get('Pkg', ''), 1); pdf.cell(30, 10, f"{lr_data.get('NetWt',0)}/{lr_data.get('ChgWt',0)}", 1); pdf.cell(30, 10, f"{lr_data.get('From', '')}-{lr_data.get('To', '')}", 1)
    amt = f"Rs. {lr_data.get('Freight',0)}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 5, f"BANK: {lr_data.get('Bank', '')} | Driver: {lr_data.get('DrvName', '')} ({lr_data.get('DrvNo', '')})", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, f"For {lr_data.get('BrName', 'VIRAT LOGISTICS')}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN UI ---
df_m = load("masters")

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    
    with st.form("m_form_v32", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(f"{m_type} Name/No*")
            if m_type in ["Party", "Branch"]:
                gst = st.text_input("GST Number")
            elif m_type == "Bank":
                ac_no = st.text_input("Account Number")
            elif m_type == "Vehicle":
                drv_name = st.text_input("Driver Name")
        
        with c2:
            contact = st.text_input("Contact Number")
            if m_type in ["Party", "Branch"]:
                address = st.text_area("Address")
            elif m_type == "Bank":
                ifsc = st.text_input("IFSC Code")
            elif m_type == "Vehicle":
                drv_no = st.text_input("Driver Mobile")

        if st.form_submit_button(f"Add {m_type}"):
            if name:
                # Type, Name, GST, Address, Contact, A_C_No, IFSC, Driver_Name, Driver_No
                new_row = [m_type, name, 
                           gst if 'gst' in locals() else "", 
                           address if 'address' in locals() else "", 
                           contact, 
                           ac_no if 'ac_no' in locals() else "", 
                           ifsc if 'ifsc' in locals() else "", 
                           drv_name if 'drv_name' in locals() else "", 
                           drv_no if 'drv_no' in locals() else ""]
                save("masters", new_row)
                st.success("Master Updated!"); st.rerun()

    st.dataframe(df_m[df_m['Type'] == m_type] if not df_m.empty else df_m)

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry v3.2")
    
    if st.button("🆕 START NEW ENTRY"):
        st.session_state.reset_trigger = st.session_state.get('reset_trigger', 0) + 1
        st.session_state.pdf_ready = None
        st.rerun()

    k = st.session_state.get('reset_trigger', 0)
    
    # Safe Filters
    def get_list(typ): return df_m[df_m['Type'] == typ] if not df_m.empty else pd.DataFrame()
    
    parties = get_list('Party'); branches = get_list('Branch'); banks = get_list('Bank')
    vehicles = get_list('Vehicle'); brokers = get_list('Broker')

    st.markdown("### 🏢 Business Unit & Bank")
    col_b1, col_b2 = st.columns(2)
    with col_b1: sel_br = st.selectbox("Select Our Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
    with col_b2: sel_bank = st.selectbox("Select Bank*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")

    st.divider()
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        v_cat = st.radio("Trip Type*", ["Own", "Market"], horizontal=True, key=f"vcat_{k}")
        lr_no = st.text_input("LR Number*", value=f"VL-{date.today().strftime('%y%m%d%H%M')}", key=f"lrno_{k}")
        bill_pty = st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
    
    with cp2:
        cnor = st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
        cnee = st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")

    with cp3:
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")
        # Fetch Address for Ship-To Auto-fill
        cnee_row = parties[parties['Name'] == cnee].iloc[0] if cnee != "Select" else {}
        ship_to = st.text_area("Ship-To Address", value=cnee_row.get('Address', ''), key=f"st_{k}")

    with st.form(f"lr_form_{k}"):
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            if v_cat == "Own":
                v_sel = st.selectbox("Vehicle*", ["Select"] + vehicles['Name'].tolist())
                v_row = vehicles[vehicles['Name'] == v_sel].iloc[0] if v_sel != "Select" else {}
                drv_n = v_row.get('Driver_Name', ''); drv_m = v_row.get('Driver_No', '')
            else:
                v_sel = st.text_input("Market Vehicle No*")
                drv_n = st.text_input("Driver Name"); drv_m = st.text_input("Driver Mobile")
        with c2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material"); pkg = st.selectbox("Pkg", ["Drums", "Bags", "Boxes", "Loose"])
        with c3:
            n_wt, c_wt = st.number_input("Net Weight"), st.number_input("Chg Weight")
            fr = st.number_input("Total Freight*", min_value=0.0)
            inv = st.text_input("Invoice Info")

        if st.form_submit_button("🚀 SAVE LR"):
            if sel_br != "Select" and bill_pty != "Select" and fr > 0:
                br_row = branches[branches['Name'] == sel_br].iloc[0]
                bk_row = banks[banks['Name'] == sel_bank].iloc[0] if sel_bank != "Select" else {}
                cn_row = parties[parties['Name'] == cnor].iloc[0] if cnor != "Select" else {}
                ce_row = parties[parties['Name'] == cnee].iloc[0] if cnee != "Select" else {}
                
                row = [str(d), lr_no, v_cat, bill_pty, cnee, paid_by, n_wt, c_wt, pkg, risk, mat, "N/A", v_sel, drv_n, "N/A", fl, tl, fr, 0, 0, 0, 0, 0, fr]
                if save("trips", row):
                    st.success("LR Saved!")
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_sel, "Risk": risk,
                        "BrName": br_row.get('Name',''), "BrGST": br_row.get('GST',''), "BrAddr": br_row.get('Address',''),
                        "BillP": bill_pty, "Cnor": cnor, "CnorGST": cn_row.get('GST',''), "CnorAddr": cn_row.get('Address',''),
                        "Cnee": cnee, "CneeGST": ce_row.get('GST',''), "CneeAddr": ce_row.get('Address',''),
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "From": fl, "To": tl, "Freight": fr,
                        "Bank": f"{bk_row.get('Name','')} A/C:{bk_row.get('A_C_No','')} IFSC:{bk_row.get('IFSC','')}",
                        "DrvName": drv_n, "DrvNo": drv_m, "PaidBy": paid_by, "InvNo": inv, "ShipTo": ship_to
                    }
            else: st.error("Fields missing!")

    if st.session_state.get('pdf_ready'):
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, True), f"LR_{lr_no}.pdf")
