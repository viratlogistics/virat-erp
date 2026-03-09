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

def delete_row(sheet_name, row_idx):
    try:
        sh.worksheet(sheet_name).delete_rows(row_idx + 2)
        return True
    except: return False

# --- 2. PROFESSIONAL PDF ENGINE ---
def generate_lr_pdf(lr, show_fr=True):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18); pdf.cell(100, 8, lr.get('BrName', 'Virat Logistics'), ln=1)
    pdf.set_font("Arial", '', 8); pdf.cell(190, 4, f"Address: {lr.get('BrAddr', '')}", ln=True)
    pdf.cell(190, 4, f"GST No: {lr.get('BrGST', '')}", ln=True); pdf.ln(5)
    pdf.line(10, 35, 200, 35); pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr.get('LR No', '')}", 1); pdf.cell(45, 8, f"Date: {lr.get('Date', '')}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr.get('Vehicle', '')}", 1); pdf.cell(50, 8, f"Risk: {lr.get('Risk', 'Owner Risk')}", 1, ln=True)
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 8); y_s = pdf.get_y()
    pdf.multi_cell(63, 5, f"{lr.get('Cnor', '')}\nGST: {lr.get('CnorGST', '')}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 5, f"{lr.get('Cnee', '')}\nGST: {lr.get('CneeGST', '')}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 5, f"{lr.get('BillP', '')}\nInv: {lr.get('InvNo', '')}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3)); pdf.ln(2)
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr.get('ShipTo', 'N/A')}", 1, ln=True)
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8); pdf.cell(70, 10, lr.get('Material', ''), 1); pdf.cell(30, 10, lr.get('Pkg', ''), 1); pdf.cell(30, 10, f"{lr.get('NetWt', 0)}/{lr.get('ChgWt', 0)}", 1); pdf.cell(30, 10, f"{lr.get('From', '')}-{lr.get('To', '')}", 1)
    amt = f"Rs. {lr.get('Freight', 0)}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True); pdf.ln(5)
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 5, f"BANK: {lr.get('BankInfo', 'N/A')} | Freight Paid By: {lr.get('PaidBy', 'N/A')}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN APP ---
df_m, df_t = load("masters"), load("trips")

if 'ed_lr_idx' not in st.session_state: st.session_state.ed_lr_idx = None
if 'reset' not in st.session_state: st.session_state.reset = 0

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry", "3. LR Register"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank", "Branch"])
    with st.form("m_form"):
        n = st.text_input("Name"); g = st.text_input("GST/A_C No"); a = st.text_area("Address")
        if st.form_submit_button("Save"):
            if n: save("masters", [m_type, n, g, a]); st.rerun()
    st.divider()
    if not df_m.empty:
        curr = df_m[df_m['Type'] == m_type]
        for i, r in curr.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{r['Name']}** | {r.get('GST','')}")
            if c2.button("🗑️", key=f"m_{i}"):
                if delete_row("masters", i): st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 LR Entry Form")
    if st.session_state.ed_lr_idx is not None:
        st.warning("Editing Mode Active"); ed_d = df_t.iloc[st.session_state.ed_lr_idx]
    else: ed_d = {}

    def gl(t): return sorted(df_m[df_m['Type'] == t]['Name'].tolist()) if not df_m.empty else []
    
    k = st.session_state.reset
    col1, col2, col3 = st.columns(3)
    with col1:
        s_br = st.selectbox("Branch*", ["Select"] + gl("Branch"), key=f"b_{k}")
        br_r = df_m[(df_m['Name'] == s_br) & (df_m['Type'] == 'Branch')].iloc[0] if s_br != "Select" else {}
        v_cat = st.radio("Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"v_{k}")
        l_no = st.text_input("LR No*", value=f"VIL/25-26/{br_r.get('GST','01')}/{len(df_t)+1:03d}" if not ed_d else ed_d['LR No'], key=f"ln_{k}")
    with col2:
        p_name = st.text_input("New Party") if st.checkbox("New Party?") else st.selectbox("Party*", ["Select"] + gl("Party"), key=f"p_{k}")
        cn, cn_g = st.text_input("Consignor", value=ed_d.get('Consignor','')), st.text_input("Cons_GST")
    with col3:
        ce, ce_g = st.text_input("Consignee", value=ed_d.get('Consignee','')), st.text_input("Cnee_GST")
        pb = st.selectbox("Paid By", ["Consignor", "Consignee", "Billing Party"], key=f"pb_{k}")
        bk = st.selectbox("Bank", ["Select"] + gl("Bank"), key=f"bk_{k}")

    with st.form("lr_form"):
        f1, f2, f3 = st.columns(3)
        dt = f1.date_input("Date", date.today()); vn = f1.text_input("Vehicle", value=ed_d.get('Vehicle',''))
        fl, tl = f2.text_input("From", value=ed_d.get('From','')), f2.text_input("To", value=ed_d.get('To',''))
        mt, pkg = f3.text_input("Material", value=ed_d.get('Material','')), f3.selectbox("Pkg", ["Bags", "Drums", "Loose"])
        nw, cw, fr = f1.number_input("Net Wt"), f2.number_input("Chg Wt"), f3.number_input("Freight", value=float(ed_d.get('Freight', 0)))
        
        if v_cat == "Own Fleet": dsl, toll, drv, hc = f1.number_input("Diesel"), f2.number_input("Toll"), f3.number_input("Adv"), 0.0
        else: hc, dsl, toll, drv = f1.number_input("Hired Charges"), 0, 0, 0

        if st.form_submit_button("🚀 SAVE LR"):
            row = [str(dt), l_no, v_cat, p_name, cn, cn_g, "", ce, ce_g, "", mt, nw, vn, "Driver", "OWN", fl, tl, fr, hc, dsl, drv, toll, 0, (fr-hc-dsl-toll-drv)]
            if save("trips", row): st.success("Saved!"); st.rerun()

elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    for i, r in df_t.iterrows():
        with st.expander(f"LR: {r['LR No']} | {r['Consignee']}"):
            c1, c2, c3 = st.columns(3)
            if c1.button("✏️ Edit", key=f"ed_{i}"): st.session_state.ed_lr_idx = i; st.rerun()
            if c2.button("🗑️ Delete", key=f"dl_{i}"): 
                if delete_row("trips", i): st.rerun()
            st.download_button("📥 PDF", generate_lr_pdf(r.to_dict()), f"LR_{r['LR No']}.pdf", key=f"pdf_{i}")
    st.dataframe(df_t)
