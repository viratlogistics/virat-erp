import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONNECTION & LOAD ---
st.set_page_config(page_title="Virat Logistics ERP v4.2", layout="wide")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except: return None

sh = get_sh()

def load_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_row(sheet_name, row):
    try:
        sh.worksheet(sheet_name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. PROFESSIONAL PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(100, 8, lr_data.get('BrName', 'VIRAT LOGISTICS'), 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 8, f"GST No: {lr_data.get('BrGST', '')}", 0, 1, 'R') 
    
    pdf.set_font("Arial", 'I', 8); pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.set_font("Arial", '', 7); pdf.multi_cell(190, 3, f"Address: {lr_data.get('BrAddr', '')}")
    pdf.line(10, 35, 200, 35); pdf.ln(8)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(60, 8, f"LR No: {lr_data.get('LR No', '')}", 1); pdf.cell(60, 8, f"Date: {lr_data.get('Date', '')}", 1)
    pdf.cell(70, 8, f"Vehicle: {lr_data.get('Vehicle', '')}", 1, ln=True)

    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 7); y_s = pdf.get_y()
    pdf.multi_cell(63, 4, f"{lr_data.get('Cnor', '')}\nGST: {lr_data.get('CnorGST', '')}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 4, f"{lr_data.get('Cnee', '')}\nGST: {lr_data.get('CneeGST', '')}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 4, f"{lr_data.get('BillP', '')}\nInv: {lr_data.get('InvNo', '')}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3))

    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr_data.get('ShipTo', '')}", 1, ln=True)
    
    pdf.ln(4); pdf.set_font("Arial", 'B', 8)
    pdf.cell(50, 7, "Material", 1); pdf.cell(20, 7, "Nag", 1); pdf.cell(25, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(35, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8)
    pdf.cell(50, 10, lr_data.get('Material', ''), 1); pdf.cell(20, 10, str(lr_data.get('Articles', '')), 1); pdf.cell(25, 10, lr_data.get('Pkg', ''), 1); pdf.cell(30, 10, f"{lr_data.get('NetWt',0)}/{lr_data.get('ChgWt',0)}", 1); pdf.cell(35, 10, f"{lr_data.get('From', '')}-{lr_data.get('To', '')}", 1)
    
    amt = f"Rs. {lr_data.get('Freight',0)}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)

    pdf.ln(5); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 5, f"Risk: {lr_data.get('Risk', '')} | BANK: {lr_data.get('Bank', '')} | Paid By: {lr_data.get('PaidBy', '')}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, f"For {lr_data.get('BrName', '')}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Masters Setup")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    with st.form("master_v42", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(f"{m_type} Name/No*"); gst = st.text_input("GST / Branch Name")
        with c2:
            contact = st.text_input("Contact"); address = st.text_area("Address")
        if st.form_submit_button("Add Master"):
            if name: save_row("masters", [m_type, name, gst, address, contact, "", "", "", ""]); st.success("Saved!"); st.rerun()
    st.dataframe(df_m[df_m['Type'] == m_type] if not df_m.empty else [])

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry v4.2")
    if st.button("🆕 START NEW ENTRY"):
        st.session_state.reset_trigger += 1; st.session_state.pdf_ready = None; st.rerun()
    
    k = st.session_state.reset_trigger
    def get_list(t): return df_m[df_m['Type'] == t] if not df_m.empty else pd.DataFrame()
    branches = get_list('Branch'); banks = get_list('Bank'); parties = get_list('Party'); vehicles = get_list('Vehicle'); brokers = get_list('Broker')

    st.markdown("### 🏢 Core Details")
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        sel_br = st.selectbox("Select Our Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
        br_info = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
        br_code_for_lr = br_info.get('GST', '01') 
    with col_u2:
        v_cat = st.radio("Trip Category*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_mode = st.radio("LR No Mode", ["Auto", "Manual"], horizontal=True, key=f"lrmode_{k}")
    with col_u3:
        # --- AUTO NUMBERING LOGIC (KeyError Fix) ---
        fy = "25-26"
        branch_count = len(df_t) + 1 if not df_t.empty else 1
        auto_no = f"VIL/{fy}/{br_code_for_lr}/{branch_count:03d}" if sel_br != "Select" else ""
        lr_no = st.text_input("LR Number*", value=auto_no if lr_mode == "Auto" else "", key=f"lrno_{k}")

    st.divider()
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        bill_pty = st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
        cnor = st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
        cnor_d = parties[parties['Name'] == cnor].iloc[0] if cnor != "Select" else {}
        if v_cat == "Own Fleet": dsl = st.number_input("Diesel Expense", key=f"dsl_{k}")
        else: br_name = st.selectbox("Select Broker", ["Select"] + brokers['Name'].tolist(), key=f"brk_{k}")
    with cp2:
        cnee = st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        cnee_d = parties[parties['Name'] == cnee].iloc[0] if cnee != "Select" else {}
        sel_bank = st.selectbox("Select Bank*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")
        bk_d = banks[banks['Name'] == sel_bank].iloc[0] if sel_bank != "Select" else {}
        if v_cat == "Own Fleet": toll = st.number_input("Toll/Tax", key=f"toll_{k}")
        else: hc = st.number_input("Hired Charges", key=f"hc_{k}")
    with cp3:
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")
        ship_to = st.text_area("Ship-To Address", value=cnee_d.get('Address', ''), key=f"st_{k}")
        if v_cat == "Own Fleet": drv_adv = st.number_input("Driver Advance", key=f"drv_{k}")

    with st.form(f"main_form_v42_{k}"):
        st.markdown("---")
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Select Own Vehicle*", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            fl = st.text_input("From Location")
        with f2:
            tl = st.text_input("To Location")
            mat = st.text_input("Material")
            articles = st.number_input("Nag/Articles*", min_value=1)
        with f3:
            n_wt, c_wt = st.number_input("Net Wt"), st.number_input("Chg Wt")
            fr = st.number_input("Total Freight*", min_value=0.0)
            inv = st.text_input("Invoice Info")
            show_fr_check = st.checkbox("Print Freight Amount in PDF?", value=True)

        if st.form_submit_button("🚀 SAVE & PREPARE PDF"):
            if sel_br != "Select" and bill_pty != "Select" and v_no and fr > 0:
                h_c = hc if v_cat == "Market Hired" else 0.0
                d_s = dsl if v_cat == "Own Fleet" else 0.0
                t_l = toll if v_cat == "Own Fleet" else 0.0
                d_a = drv_adv if v_cat == "Own Fleet" else 0.0
                prof = (fr - h_c) if v_cat == "Market Hired" else (fr - d_s - t_l - d_a)
                
                row = [str(d), lr_no, v_cat, bill_pty, cnee, paid_by, n_wt, c_wt, "Pkg", risk, mat, articles, v_no, "Driver", "OWN" if v_cat=="Own Fleet" else br_name, fl, tl, fr, h_c, d_s, d_a, t_l, 0, prof]
                if save_row("trips", row):
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Risk": risk, "Articles": articles,
                        "BrName": br_info.get('Name',''), "BrGST": br_info.get('GST',''), "BrAddr": br_info.get('Address',''),
                        "BillP": bill_pty, "Cnor": cnor, "CnorGST": cnor_d.get('GST',''), 
                        "Cnee": cnee, "CneeGST": cnee_d.get('GST',''), "Material": mat, 
                        "Pkg": "Standard", "NetWt": n_wt, "ChgWt": c_wt, "From": fl, "To": tl, "Freight": fr,
                        "Bank": f"{bk_d.get('Name','')} {bk_d.get('A_C_No','')}", "PaidBy": paid_by, "ShipTo": ship_to, "ShowFr": show_fr_check
                    }
                    st.success(f"✅ LR {lr_no} Saved!")

    if st.session_state.pdf_ready:
        st.divider()
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, st.session_state.pdf_ready['ShowFr']), f"LR_{lr_no}.pdf")
