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

# --- 2. PROFESSIONAL PDF ENGINE (CRASH PROOF) ---
def generate_lr_pdf(lr, show_fr=True):
    pdf = FPDF()
    pdf.add_page()
    def s(v): return str(v) if v is not None else ""
    
    pdf.set_font("Arial", 'B', 18); pdf.cell(100, 8, s(lr.get('BrName', 'Virat Logistics')), ln=1)
    pdf.set_font("Arial", '', 8); pdf.cell(190, 4, f"Address: {s(lr.get('BrAddr', ''))}", ln=True)
    pdf.cell(190, 4, f"GST No: {s(lr.get('BrGST', ''))}", ln=True); pdf.ln(5)
    pdf.line(10, 35, 200, 35); pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {s(lr.get('LR No'))}", 1); pdf.cell(45, 8, f"Date: {s(lr.get('Date'))}", 1)
    pdf.cell(50, 8, f"Vehicle: {s(lr.get('Vehicle'))}", 1); pdf.cell(50, 8, f"Risk: {s(lr.get('Risk', 'At Owner Risk'))}", 1, ln=True)
    
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 8); y_s = pdf.get_y()
    pdf.multi_cell(63, 5, f"{s(lr.get('Consignor'))}\nGST: {s(lr.get('CnorGST'))}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 5, f"{s(lr.get('Consignee'))}\nGST: {s(lr.get('CneeGST'))}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 5, f"{s(lr.get('Party', lr.get('BillP')))}\nInv: {s(lr.get('InvNo'))}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3)); pdf.ln(2)
    
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {s(lr.get('ShipTo', 'N/A'))}", 1, ln=True)
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    
    pdf.set_font("Arial", '', 8)
    pdf.cell(70, 10, s(lr.get('Material')), 1); pdf.cell(30, 10, s(lr.get('Pkg')), 1); pdf.cell(30, 10, s(lr.get('Weight', lr.get('NetWt'))), 1); pdf.cell(30, 10, f"{s(lr.get('From'))}-{s(lr.get('To'))}", 1)
    
    amt = f"Rs. {s(lr.get('Freight'))}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True); pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 5, f"BANK: {s(lr.get('BankInfo', 'N/A'))} | Paid By: {s(lr.get('Paid_By', lr.get('PaidBy')))}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN APP ---
df_m = load("masters")
df_t = load("trips")

if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry", "3. LR Register"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Bank", "Branch"])
    with st.form("m_form"):
        n = st.text_input("Name"); g = st.text_input("GST/Account No"); a = st.text_area("Address")
        if st.form_submit_button("Add Master"):
            if n: save("masters", [m_type, n, g, a]); st.rerun()
    st.divider()
    if not df_m.empty:
        curr = df_m[df_m['Type'] == m_type]
        for i, r in curr.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{r['Name']}** | {r.get('GST','')}")
            if c2.button("🗑️", key=f"mdel_{i}"):
                sh.worksheet("masters").delete_rows(int(i) + 2); st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    if st.session_state.edit_idx is not None:
        st.warning(f"Editing Mode: Row {st.session_state.edit_idx}")
        ed = df_t.iloc[st.session_state.edit_idx]
        if st.button("Cancel Edit"): st.session_state.edit_idx = None; st.rerun()
    else: ed = {}

    k = st.session_state.reset_k
    def gl(t): return sorted(df_m[df_m['Type'] == t]['Name'].tolist()) if not df_m.empty else []
    
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        sel_br = st.selectbox("Branch*", ["Select"] + gl("Branch"), key=f"br_{k}")
        br_r = df_m[(df_m['Name'] == sel_br) & (df_m['Type'] == 'Branch')].iloc[0] if sel_br != "Select" else {}
        v_cat = st.radio("Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_no = st.text_input("LR No*", value=str(ed.get('LR No', f"VIL/25-26/{br_r.get('GST','01')}/{len(df_t)+1:03d}")), key=f"lrno_{k}")
    with cp2:
        bill_p = st.selectbox("Party*", ["Select"] + gl("Party"), key=f"bp_{k}")
        cn = st.text_input("Consignor", value=str(ed.get('Consignor', '')), key=f"cn_{k}")
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")
    with cp3:
        ce = st.text_input("Consignee", value=str(ed.get('Consignee', '')), key=f"ce_{k}")
        pb = st.selectbox("Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pb_{k}")
        bk = st.selectbox("Bank*", ["Select"] + gl("Bank"), key=f"bk_{k}")
        bk_r = df_m[(df_m['Name'] == bk) & (df_m['Type'] == 'Bank')].iloc[0] if bk != "Select" else {}

    with st.form(f"lr_form_{k}"):
        c1, c2, c3 = st.columns(3)
        dt = c1.date_input("Date", date.today())
        vn = c1.text_input("Vehicle", value=str(ed.get('Vehicle', '')))
        fl, tl = c2.text_input("From", value=str(ed.get('From', ''))), c2.text_input("To", value=str(ed.get('To', '')))
        mt = c2.text_input("Material", value=str(ed.get('Material', '')))
        nw = c3.number_input("Net Wt", value=float(ed.get('Weight', 0.0)))
        fr = c3.number_input("Freight", value=float(ed.get('Freight', 0.0)))
        show_fr = c3.checkbox("Show Freight in PDF?", value=True)
        
        if v_cat == "Own Fleet": dsl, toll, drv, hc = c1.number_input("Diesel"), c2.number_input("Toll"), c3.number_input("Adv"), 0.0
        else: hc, dsl, toll, drv = c1.number_input("Hired Charges"), 0, 0, 0

        if st.form_submit_button("🚀 SAVE LR"):
            row = [str(dt), lr_no, v_cat, bill_p, cn, "", "", ce, "", "", mt, nw, vn, "Driver", "OWN", fl, tl, fr, hc, dsl, drv, toll, 0, (fr-hc-dsl-toll-drv)]
            if st.session_state.edit_idx is not None:
                sh.worksheet("trips").delete_rows(int(st.session_state.edit_idx) + 2)
                st.session_state.edit_idx = None
            save("trips", row)
            st.session_state.pdf_ready = {"LR No": lr_no, "Date": str(dt), "Vehicle": vn, "Consignor": cn, "Consignee": ce, "Party": bill_p, "From": fl, "To": tl, "Material": mt, "Weight": nw, "Freight": fr, "Paid_By": pb, "BrName": sel_br, "BrAddr": br_r.get('Address',''), "BrGST": br_r.get('GST',''), "BankInfo": f"{bk} A/C:{bk_r.get('GST','')}", "show_fr": show_fr}
            st.success("Saved!"); st.rerun()

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, st.session_state.pdf_ready.get('show_fr', True)), f"LR_{st.session_state.pdf_ready['LR No']}.pdf")

elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR/Party")
    if not df_t.empty:
        df_f = df_t.copy()
        if search: df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        for i, row in df_f.iterrows():
            with st.expander(f"LR: {row['LR No']} | {row['Consignee']}"):
                c1, c2, c3 = st.columns(3)
                if c1.button("✏️ Edit", key=f"e_{i}"): st.session_state.edit_idx = i; st.rerun()
                if c2.button("🗑️ Delete", key=f"d_{i}"):
                    sh.worksheet("trips").delete_rows(int(i) + 2); st.rerun()
                st.download_button("📥 PDF", generate_lr_pdf(row.to_dict(), True), f"LR_{row['LR No']}.pdf", key=f"p_{i}")
        st.dataframe(df_f)
