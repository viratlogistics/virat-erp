import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONNECTION & LOAD ---
st.set_page_config(page_title="Virat Logistics ERP v3.3", layout="wide")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except: return None

sh = get_sh()

def load_data():
    try:
        ws = sh.worksheet("masters")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        # Agar sheet khali hai toh default columns ke sath return karega
        return pd.DataFrame(columns=['Type', 'Name', 'GST', 'Address', 'Contact', 'A_C_No', 'IFSC', 'Driver_Name', 'Driver_No'])

def save_row(sheet_name, row):
    try:
        sh.worksheet(sheet_name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. PROFESSIONAL PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    pdf = FPDF()
    pdf.add_page()
    # Branch Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(100, 8, lr_data.get('BrName', 'VIRAT LOGISTICS'), 0)
    pdf.set_font("Arial", '', 8)
    pdf.cell(90, 8, f"GST: {lr_data.get('BrGST', '')}", 0, 1, 'R')
    pdf.set_font("Arial", 'I', 8); pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.set_font("Arial", '', 7); pdf.multi_cell(190, 3, f"Address: {lr_data.get('BrAddr', '')}")
    pdf.line(10, 35, 200, 35); pdf.ln(10)
    
    # Info Row
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr_data.get('LR No', '')}", 1); pdf.cell(45, 8, f"Date: {lr_data.get('Date', '')}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr_data.get('Vehicle', '')}", 1); pdf.cell(50, 8, f"Risk: {lr_data.get('Risk', '')}", 1, ln=True)

    # Party Details
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 7); y_s = pdf.get_y()
    pdf.multi_cell(63, 4, f"{lr_data.get('Cnor', '')}\nGST: {lr_data.get('CnorGST', '')}\nAddr: {lr_data.get('CnorAddr', '')}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 4, f"{lr_data.get('Cnee', '')}\nGST: {lr_data.get('CneeGST', '')}\nAddr: {lr_data.get('CneeAddr', '')}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 4, f"{lr_data.get('BillP', '')}\nInv: {lr_data.get('InvNo', '')}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3))

    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr_data.get('ShipTo', '')}", 1, ln=True)
    
    # Product Table
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8); pdf.cell(70, 10, lr_data.get('Material', ''), 1); pdf.cell(30, 10, lr_data.get('Pkg', ''), 1); pdf.cell(30, 10, f"{lr_data.get('NetWt',0)}/{lr_data.get('ChgWt',0)}", 1); pdf.cell(30, 10, f"{lr_data.get('From', '')}-{lr_data.get('To', '')}", 1)
    amt = f"Rs. {lr_data.get('Freight',0)}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)

    pdf.ln(5); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 5, f"BANK: {lr_data.get('Bank', '')} | Paid By: {lr_data.get('PaidBy', '')}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, f"For {lr_data.get('BrName', '')}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. UI LOGIC ---
df_m = load_data()

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry"])

if menu == "1. Masters Setup":
    st.header("🏗️ Professional Masters")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    with st.form("master_form_final", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(f"{m_type} Name*"); gst = st.text_input("GST No")
            drv_name = st.text_input("Driver Name") if m_type == "Vehicle" else ""
            ac_no = st.text_input("Account Number") if m_type == "Bank" else ""
        with c2:
            contact = st.text_input("Contact Number"); address = st.text_area("Address")
            drv_no = st.text_input("Driver Mobile") if m_type == "Vehicle" else ""
            ifsc = st.text_input("IFSC Code") if m_type == "Bank" else ""
        
        if st.form_submit_button("Add Master"):
            if name:
                new_row = [m_type, name, gst, address, contact, ac_no, ifsc, drv_name, drv_no]
                save_row("masters", new_row); st.success("Saved!"); st.rerun()
    st.dataframe(df_m[df_m['Type'] == m_type], use_container_width=True)

elif menu == "2. LR Entry":
    st.header("📝 Consignment Entry (Bilty)")
    if st.button("🆕 START NEW ENTRY"):
        st.session_state.reset_trigger += 1; st.session_state.pdf_ready = None; st.rerun()
    
    k = st.session_state.reset_trigger
    # Data extraction for dropdowns
    get_list = lambda t: df_m[df_m['Type'] == t]['Name'].tolist()
    br_list = get_list('Branch'); bk_list = get_list('Bank'); p_list = get_list('Party')
    v_list = get_list('Vehicle'); b_list = get_list('Broker')

    # UNIT & BANK SELECTION
    st.markdown("### 🏢 Unit Settings")
    sc1, sc2 = st.columns(2)
    with sc1: sel_br = st.selectbox("Our Branch*", ["Select"] + br_list, key=f"br_{k}")
    with sc2: sel_bank = st.selectbox("Select Bank*", ["Select"] + bk_list, key=f"bk_{k}")

    st.divider()
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_no = st.text_input("LR Number*", value=f"VL-{date.today().strftime('%y%m%d%H%M')}", key=f"lrno_{k}")
        is_new_p = st.checkbox("New Billing Party?")
        bill_pty = st.text_input("Enter Billing Party Name") if is_new_p else st.selectbox("Billing Party*", ["Select"] + p_list, key=f"bp_{k}")
    
    with cp2:
        is_new_cn = st.checkbox("New Consignor?")
        cnor = st.text_input("Enter Consignor Name") if is_new_cn else st.selectbox("Consignor*", ["Select"] + p_list, key=f"cn_{k}")
        risk = st.radio("Risk Type*", ["At Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")

    with cp3:
        is_new_ce = st.checkbox("New Consignee?")
        cnee = st.text_input("Enter Consignee Name") if is_new_ce else st.selectbox("Consignee*", ["Select"] + p_list, key=f"ce_{k}")
        # Auto-fetch address for ship-to
        cnee_row = df_m[df_m['Name'] == cnee].iloc[0] if not is_new_ce and cnee != "Select" else {}
        ship_to = st.text_area("Ship-To Address", value=cnee_row.get('Address', ''), key=f"st_{k}")

    with st.form(f"main_form_{k}"):
        st.markdown("---")
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Own Vehicle*", ["Select"] + v_list) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            br_name = "OWN" if v_cat == "Own Fleet" else st.selectbox("Broker", ["Select"] + b_list)
        with f2:
            fl, tl = st.text_input("From"), st.text_input("To")
            mat = st.text_input("Material"); pkg = st.selectbox("Packaging", ["Drums", "Bags", "Boxes", "Loose"])
        with f3:
            n_wt, c_wt = st.number_input("Net Weight"), st.number_input("Chg Weight")
            fr = st.number_input("Total Freight*", min_value=0.0)
            inv = st.text_input("Invoice Info"); show_fr = st.checkbox("Print Freight?", value=True)
            hc = st.number_input("Hired Charges") if v_cat == "Market Hired" else 0.0

        if st.form_submit_button("🚀 SAVE & PRINT BILTY"):
            if sel_br != "Select" and bill_pty and fr > 0:
                # Meta data fetching
                br_row = df_m[df_m['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
                bk_row = df_m[df_m['Name'] == sel_bank].iloc[0] if sel_bank != "Select" else {}
                cnor_row = df_m[df_m['Name'] == cnor].iloc[0] if not is_new_cn and cnor != "Select" else {}
                cnee_row = df_m[df_m['Name'] == cnee].iloc[0] if not is_new_ce and cnee != "Select" else {}
                
                # Auto-save new masters
                if is_new_p: save_row("masters", ["Party", bill_pty, "", "", "", "", "", "", ""])
                if is_new_cn: save_row("masters", ["Party", cnor, "", "", "", "", "", "", ""])

                row = [str(d), lr_no, v_cat, bill_pty, cnee, paid_by, n_wt, c_wt, pkg, risk, mat, "N/A", v_no, "Driver", br_name, fl, tl, fr, hc, 0, 0, 0, 0, (fr-hc)]
                if save_row("trips", row):
                    st.success("Bilty Saved!")
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Risk": risk,
                        "BrName": br_row.get('Name', ''), "BrGST": br_row.get('GST', ''), "BrAddr": br_row.get('Address', ''),
                        "BillP": bill_pty, "Cnor": cnor, "CnorGST": cnor_row.get('GST', ''), "CnorAddr": cnor_row.get('Address', ''),
                        "Cnee": cnee, "CneeGST": cnee_row.get('GST', ''), "CneeAddr": cnee_row.get('Address', ''),
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "From": fl, "To": tl, "Freight": fr,
                        "Bank": f"{bk_row.get('Name','')} A/C:{bk_row.get('A_C_No','')} IFSC:{bk_row.get('IFSC','')}",
                        "PaidBy": paid_by, "InvNo": inv, "ShipTo": ship_to
                    }
            else: st.error("Fields missing (Branch, Billing Party, Freight)!")

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, show_fr), f"LR_{lr_no}.pdf")
