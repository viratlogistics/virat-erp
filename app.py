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

# --- 1. CONNECTION & LOAD ---
st.set_page_config(page_title="Virat Logistics ERP v5.4", layout="wide")

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
        return df
    except: return pd.DataFrame()

def save_row(sheet_name, row):
    try:
        sh.worksheet(sheet_name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 2. PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph(f"<b>{lr_data.get('BrName', 'VIRAT LOGISTICS')}</b>", styles['Title']))
    elements.append(Paragraph(f"GST No: {lr_data.get('BrGST', '')}", styles['Normal']))
    elements.append(Paragraph(f"Address: {lr_data.get('BrAddr', '')}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # Grid Info
    data = [[f"LR No: {lr_data['LR No']}", f"Date: {lr_data['Date']}", f"Vehicle: {lr_data['Vehicle']}"]]
    t1 = Table(data, colWidths=[180, 150, 180])
    t1.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')]))
    elements.append(t1)
    elements.append(Spacer(1, 10))

    # Parties Section
    party_data = [
        ["CONSIGNOR", "CONSIGNEE", "BILLING PARTY"],
        [Paragraph(f"{lr_data.get('Cnor', '')}<br/>GST: {lr_data.get('CnorGST', '')}", styles['Normal']), 
         Paragraph(f"{lr_data.get('Cnee', '')}<br/>GST: {lr_data.get('CneeGST', '')}", styles['Normal']), 
         Paragraph(f"{lr_data.get('Party', '')}", styles['Normal'])]
    ]
    t2 = Table(party_data, colWidths=[170, 170, 170])
    t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t2)
    elements.append(Spacer(1, 15))

    # Material Table
    fr_val = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    mat_data = [
        ["Material", "Nag/Art", "Weight", "From - To", "Freight"],
        [lr_data['Material'], lr_data['Articles'], lr_data['Weight'], f"{lr_data['From']}-{lr_data['To']}", fr_val]
    ]
    t3 = Table(mat_data, colWidths=[160, 50, 80, 120, 100])
    t3.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elements.append(t3)

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"<b>Bank:</b> {lr_data.get('Bank', '')} | <b>Risk:</b> Owner Risk", styles['Normal']))
    elements.append(Spacer(1, 40))
    elements.append(Table([["Consignor Sign", "", "For VIRAT LOGISTICS"]], colWidths=[200, 110, 200]))

    doc.build(elements)
    return buffer.getvalue()

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

if 'reset_k' not in st.session_state: st.session_state.reset_k = 0

menu = st.sidebar.selectbox("Menu", ["Create LR", "LR Register", "Master Settings"])

if menu == "Master Settings":
    st.title("🏗️ Master Management")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    with st.form("master_v54"):
        c1, c2 = st.columns(2)
        with c1: name = st.text_input("Name*"); gst = st.text_input("GST/Code")
        with c2: cont = st.text_input("Contact"); addr = st.text_area("Address")
        if st.form_submit_button("Save Master"):
            if name: save_row("masters", [m_type, name, gst, addr, cont, "", "", "", ""]); st.rerun()
    st.dataframe(df_m[df_m['Type'] == m_type] if not df_m.empty else [])

elif menu == "Create LR":
    st.title("📝 CREATE LR")
    if st.button("🆕 START NEW ENTRY"):
        st.session_state.reset_k += 1; st.rerun()

    k = st.session_state.reset_k
    def get_list(t): return df_m[df_m['Type'] == t] if not df_m.empty else pd.DataFrame()
    branches = get_list('Branch'); banks = get_list('Bank'); parties = get_list('Party'); vehicles = get_list('Vehicle'); brokers = get_list('Broker')

    # --- TOP SECTION ---
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_br = st.selectbox("Select Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
        br_info = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
        br_code = br_info.get('GST', '01')
    with col2:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
    with col3:
        next_ser = len(df_t) + 1
        lr_no = st.text_input("LR No*", value=f"VIL/25-26/{br_code}/{next_ser:03d}", key=f"lrno_{k}")

    st.divider()
    # --- PARTIES SECTION ---
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        bill_p = st.selectbox("Billing Party (Party)*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
        cnor = st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
        cnor_d = parties[parties['Name'] == cnor].iloc[0] if cnor != "Select" else {}
    with cp2:
        cnee = st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        cnee_d = parties[parties['Name'] == cnee].iloc[0] if cnee != "Select" else {}
        sel_bank = st.selectbox("Select Bank*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")
    with cp3:
        fl, tl = st.text_input("From"), st.text_input("To")
        st_addr = st.text_area("Ship-To Address", value=cnee_d.get('Address', ''), key=f"st_{k}")

    # --- TRIP FORM ---
    with st.form(f"lr_form_{k}"):
        st.markdown("---")
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Vehicle*", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else st.text_input("Vehicle No*")
            mat = st.text_input("Material")
            art = st.number_input("Articles (Nag)", min_value=1)
        with f2:
            wt = st.number_input("Weight")
            fr = st.number_input("Freight", min_value=0.0)
            if v_cat == "Own Fleet":
                dsl = st.number_input("Diesel")
                toll = st.number_input("Toll")
            else:
                brk = st.selectbox("Broker", ["Select"] + brokers['Name'].tolist())
                hc = st.number_input("Hired Charges")
        with f3:
            show_fr = st.checkbox("Print Freight?", value=True)
            if v_cat == "Own Fleet":
                drv_ex = st.number_input("Driver Exp")
                oth = st.number_input("Other Exp")
            else:
                drv_ex, toll, dsl, oth = 0, 0, 0, 0

        if st.form_submit_button("🚀 SAVE & PRINT"):
            if sel_br != "Select" and bill_p != "Select" and v_no and fr > 0:
                h_c = hc if v_cat == "Market Hired" else 0.0
                prof = (fr - h_c) if v_cat == "Market Hired" else (fr - dsl - toll - drv_ex - oth)
                
                # Sheet Columns Order: Date, LR No, Type, Party, Consignor, Consignor_GST, Consignor_Add, Consignee, Consignee_GST, Consignee_Add, Material, Weight, Vehicle, Driver, Broker, From, To, Freight, HiredCharges, Diesel, DriverExp, Toll, Other, Profit
                row = [str(d), lr_no, v_cat, bill_p, cnor, cnor_d.get('GST', ''), cnor_d.get('Address', ''), cnee, cnee_d.get('GST', ''), cnee_d.get('Address', ''), mat, wt, v_no, "Driver", "OWN" if v_cat=="Own Fleet" else brk, fl, tl, fr, h_c, dsl, drv_ex, toll, oth, prof]
                
                if save_row("trips", row):
                    st.success("✅ Saved!"); st.session_state.pdf_data = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Material": mat, "Articles": art, "Weight": wt,
                        "BrName": sel_br, "BrGST": br_code, "BrAddr": br_info.get('Address', ''),
                        "Party": bill_p, "Cnor": cnor, "CnorGST": cnor_d.get('GST', ''), "Cnee": cnee, "CneeGST": cnee_d.get('GST', ''),
                        "From": fl, "To": tl, "Freight": fr, "Bank": sel_bank, "ShipTo": st_addr
                    }
                    st.session_state.show_fr = show_fr

    if 'pdf_data' in st.session_state:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_data, st.session_state.show_fr), f"LR_{st.session_state.pdf_data['LR No']}.pdf")

elif menu == "LR Register":
    st.title("📋 LR REGISTER")
    if not df_t.empty:
        search = st.text_input("Search LR/Party")
        df_f = df_t.copy()
        if search: df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        st.dataframe(df_f, use_container_width=True)
