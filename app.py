import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import io
import json

# --- 1. CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP v5.2", layout="wide")

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

def update_trip_row(lr_no, updated_row):
    try:
        ws = sh.worksheet("trips")
        cell = ws.find(str(lr_no))
        ws.update(f"A{cell.row}:X{cell.row}", [updated_row])
        return True
    except: return False

# --- 2. PROFESSIONAL PDF ENGINE (ReportLab) ---
def generate_lr_pdf(lr_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, spaceAfter=2)
    elements = []

    # Header
    elements.append(Paragraph(f"<b>{lr_data.get('BrName', 'VIRAT LOGISTICS')}</b>", title_style))
    elements.append(Paragraph(f"GST No: {lr_data.get('BrGST', '')} | Branch: {lr_data.get('BrCode', '')}", styles['Normal']))
    elements.append(Paragraph(f"Address: {lr_data.get('BrAddr', '')}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # LR Info
    data = [[f"LR No: {lr_data['LR No']}", f"Date: {lr_data['Date']}", f"Vehicle: {lr_data['Vehicle']}"]]
    t1 = Table(data, colWidths=[180, 150, 180])
    t1.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')]))
    elements.append(t1)
    elements.append(Spacer(1, 10))

    # Parties
    party_data = [
        ["CONSIGNOR", "CONSIGNEE", "BILLING PARTY"],
        [Paragraph(lr_data.get('Cnor', ''), styles['Normal']), 
         Paragraph(lr_data.get('Cnee', ''), styles['Normal']), 
         Paragraph(lr_data.get('BillP', ''), styles['Normal'])]
    ]
    t2 = Table(party_data, colWidths=[170, 170, 170])
    t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t2)
    elements.append(Spacer(1, 10))

    # Material
    fr_val = f"Rs. {lr_data['Freight']}" if lr_data.get('ShowFr', True) else "T.B.B."
    mat_data = [
        ["Material", "Articles", "Weight", "Freight"],
        [lr_data['Material'], lr_data['Articles'], f"{lr_data['NetWt']}/{lr_data['ChgWt']}", fr_val]
    ]
    t3 = Table(mat_data, colWidths=[200, 80, 100, 130])
    t3.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elements.append(t3)

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"<b>Bank:</b> {lr_data.get('Bank', '')} | <b>Paid By:</b> {lr_data.get('PaidBy', '')}", styles['Normal']))
    elements.append(Spacer(1, 40))
    elements.append(Table([["Consignor Sign", "", "For VIRAT LOGISTICS"]], colWidths=[200, 110, 200]))

    doc.build(elements)
    return buffer.getvalue()

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

# Initialization
if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'edit_data' not in st.session_state: st.session_state.edit_data = {}

menu = st.sidebar.selectbox("Menu", ["Create LR", "LR Register", "Master Settings"])

if menu == "Master Settings":
    st.title("🏗️ MASTER SETTINGS")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    with st.form("m_form"):
        c1, c2 = st.columns(2)
        with c1: name = st.text_input("Name*"); gst = st.text_input("GST/Code")
        with c2: cont = st.text_input("Contact"); addr = st.text_area("Address")
        if st.form_submit_button("Save"):
            if name: save_row("masters", [m_type, name, gst, addr, cont, "", "", "", ""]); st.rerun()
    st.dataframe(df_m[df_m['Type'] == m_type] if not df_m.empty else [])

elif menu == "Create LR":
    st.title("📝 EDIT LR" if st.session_state.edit_mode else "📝 CREATE LR")
    if st.button("🆕 START NEW / CANCEL"):
        st.session_state.edit_mode = False; st.session_state.edit_data = {}
        st.session_state.reset_k += 1; st.rerun()

    k = st.session_state.reset_k
    ed = st.session_state.edit_data
    
    def get_list(t): return df_m[df_m['Type'] == t] if not df_m.empty else pd.DataFrame()
    branches = get_list('Branch'); banks = get_list('Bank'); parties = get_list('Party'); vehicles = get_list('Vehicle'); brokers = get_list('Broker')

    # Top Section
    st.markdown("### 🏢 Unit & Numbering")
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_br = st.selectbox("Branch*", ["Select"] + branches['Name'].tolist(), index=0 if not ed else branches['Name'].tolist().index(ed.get('Category','Select'))+1 if ed.get('Category') in branches['Name'].tolist() else 0, key=f"br_{k}")
        br_info = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
        br_code = br_info.get('GST', '01')
    with col2:
        v_cat = st.radio("Category*", ["Own Fleet", "Market Hired"], index=0 if ed.get('Trip_Type') != "Market Hired" else 1, horizontal=True, key=f"vcat_{k}")
        lr_mode = st.radio("Mode", ["Auto", "Manual"], horizontal=True, key=f"mode_{k}")
    with col3:
        next_ser = len(df_t) + 1
        auto_no = f"VIL/25-26/{br_code}/{next_ser:03d}"
        lr_no = st.text_input("LR No*", value=ed.get('LR_No', auto_no if lr_mode == "Auto" else ""), key=f"lrno_{k}")

    # Parties Section
    st.markdown("### 🤝 Party Selection")
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        bill_p = st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
        cnor = st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
    with cp2:
        cnee = st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        cnee_d = parties[parties['Name'] == cnee].iloc[0] if cnee != "Select" else {}
        sel_bank = st.selectbox("Bank*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")
    with cp3:
        risk = st.radio("Risk*", ["Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")
        paid_by = st.selectbox("Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")
        ship_to = st.text_area("Ship-To", value=cnee_d.get('Address', ''), key=f"st_{k}")

    # Form with Own/Hired logic
    with st.form(f"lr_form_{k}"):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Own Vehicle", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No")
            mat = st.text_input("Material")
        with f2:
            fl, tl = st.text_input("From"), st.text_input("To")
            art = st.number_input("Articles", min_value=1)
            pkg = st.selectbox("Pkg", ["Drums", "Bags", "Boxes", "Loose"])
        with f3:
            nw, cw = st.number_input("Net Wt"), st.number_input("Chg Wt")
            fr = st.number_input("Freight", min_value=0.0)
            show_fr = st.checkbox("Print Freight?", value=True)
            inv = st.text_input("Inv No")

        # Own/Hired Expenses
        st.markdown("---")
        if v_cat == "Own Fleet":
            e1, e2, e3 = st.columns(3)
            dsl = e1.number_input("Diesel")
            toll = e2.number_input("Toll")
            adv = e3.number_input("Adv")
            hc = 0.0
        else:
            hc = st.number_input("Hired Charges")
            dsl, toll, adv = 0, 0, 0

        if st.form_submit_button("SAVE BILTY"):
            if sel_br != "Select" and bill_p != "Select" and fr > 0:
                prof = (fr - hc) if v_cat == "Market Hired" else (fr - dsl - toll - adv)
                row = [str(d), lr_no, v_cat, bill_p, cnee, paid_by, nw, cw, pkg, risk, mat, art, v_no, "Driver", "OWN" if v_cat=="Own Fleet" else "Hired", fl, tl, fr, hc, dsl, adv, toll, 0, prof]
                
                res = update_trip_row(lr_no, row) if st.session_state.edit_mode else save_row("trips", row)
                if res:
                    st.success("✅ Saved!"); st.session_state.edit_mode = False; st.rerun()

elif menu == "LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR/Party")
    if not df_t.empty:
        df_f = df_t.copy()
        if search: df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        
        for i, row in df_f.iterrows():
            with st.expander(f"LR: {row['LR_No']} | {row['Consignee']} | ₹{row['Freight']}"):
                c1, c2, c3 = st.columns([1,1,4])
                if c1.button("✏️ Edit", key=f"e_{i}"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_data = row
                    st.rerun()
                
                # PDF Download in Register
                lr_pdf_data = {
                    "LR No": row['LR_No'], "Date": row['Date'], "Vehicle": row['Vehicle'], "Risk": row['Risk'], "Articles": row['Articles'],
                    "BrName": "VIRAT LOGISTICS", "BrCode": "01", "BrGST": "GST123", "BrAddr": "Kosamba",
                    "BillP": row['Billing_Party'], "Cnor": "Consignor", "Cnee": row['Consignee'],
                    "Material": row['Material'], "NetWt": row['Net_Weight'], "ChgWt": row['Charged_Weight'], "From": row['From'], "To": row['To'], "Freight": row['Freight'],
                    "Bank": "Bank Name", "PaidBy": row['Paid_By'], "InvNo": "Inv123", "ShipTo": "Address", "ShowFr": True
                }
                c2.download_button("📥 PDF", generate_lr_pdf(lr_pdf_data), f"LR_{row['LR_No']}.pdf", key=f"p_{i}")
