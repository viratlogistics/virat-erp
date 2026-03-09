import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
import io
import json

# --- 1. CONNECTION & CONFIG ---
st.set_page_config(page_title="Virat Logistics ERP v5.0", layout="wide")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except Exception as e:
        st.error(f"Google Sheet Connection Error: {e}")
        return None

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

# --- 2. ADVANCED PDF ENGINE (ReportLab) ---
def generate_lr_pdf_reportlab(lr_data, show_fr):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontSize=18, spaceAfter=2)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, alignment=0)
    
    elements = []

    # Header Section
    elements.append(Paragraph(f"<b>{lr_data['BrName']}</b>", title_style))
    elements.append(Paragraph(f"GST No: {lr_data['BrGST']}", header_style))
    elements.append(Paragraph(f"Address: {lr_data['BrAddr']}", header_style))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<hr/>", styles['Normal']))
    
    # LR Info Table
    info_data = [
        [f"LR No: {lr_data['LR No']}", f"Date: {lr_data['Date']}", f"Vehicle: {lr_data['Vehicle']}"]
    ]
    info_table = Table(info_data, colWidths=[180, 150, 180])
    info_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # Party Details Table
    party_data = [
        ["CONSIGNOR", "CONSIGNEE", "BILLING PARTY"],
        [Paragraph(f"{lr_data['Cnor']}<br/>GST: {lr_data['CnorGST']}", styles['Normal']),
         Paragraph(f"{lr_data['Cnee']}<br/>GST: {lr_data['CneeGST']}", styles['Normal']),
         Paragraph(f"{lr_data['BillP']}<br/>Inv: {lr_data['InvNo']}", styles['Normal'])]
    ]
    party_table = Table(party_data, colWidths=[170, 170, 170])
    party_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"<b>SHIP TO:</b> {lr_data['ShipTo']}", styles['Normal']))
    elements.append(Spacer(1, 15))

    # Material Table
    fr_val = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    mat_data = [
        ["Material", "Articles", "Pkg", "Weight", "Freight"],
        [lr_data['Material'], lr_data['Articles'], "Standard", f"{lr_data['NetWt']}/{lr_data['ChgWt']}", fr_val]
    ]
    mat_table = Table(mat_data, colWidths=[150, 70, 80, 100, 110])
    mat_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(mat_table)
    
    # Footer
    elements.append(Spacer(1, 20))
    footer_text = f"Bank: {lr_data['Bank']} | Paid By: {lr_data['PaidBy']} | Risk: {lr_data['Risk']}"
    elements.append(Paragraph(footer_text, styles['Normal']))
    elements.append(Spacer(1, 40))
    
    # Signatures
    sign_data = [["Consignor Signature", "", f"For {lr_data['BrName']}"]]
    sign_table = Table(sign_data, colWidths=[200, 110, 200])
    elements.append(sign_table)

    doc.build(elements)
    return buffer.getvalue()

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0

menu = st.sidebar.selectbox("Menu", ["Create LR", "LR Register", "Master Settings"])

if menu == "Master Settings":
    st.title("🏗️ MASTER SETTINGS")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    with st.form("master_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(f"{m_type} Name*"); gst = st.text_input("GST / Branch Code (BC-01, BC-02)")
        with c2:
            contact = st.text_input("Contact"); address = st.text_area("Address")
        if st.form_submit_button("Save Master"):
            if name: 
                save_row("masters", [m_type, name, gst, address, contact, "", "", "", ""])
                st.success("Saved!"); st.rerun()
    st.dataframe(df_m[df_m['Type'] == m_type] if not df_m.empty else [])

elif menu == "Create LR":
    st.title("📝 CREATE LR")
    if st.button("🆕 START NEW ENTRY"):
        st.session_state.reset_trigger += 1; st.rerun()
    
    k = st.session_state.reset_trigger
    def get_list(t): return df_m[df_m['Type'] == t] if not df_m.empty else pd.DataFrame()
    branches = get_list('Branch'); banks = get_list('Bank'); parties = get_list('Party'); vehicles = get_list('Vehicle'); brokers = get_list('Broker')

    # Core Selection
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_br = st.selectbox("Select Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
        br_info = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
        bc_code = br_info.get('GST', '01')
    with col2:
        v_cat = st.radio("Category*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_mode = st.radio("Mode", ["Auto", "Manual"], horizontal=True, key=f"mode_{k}")
    with col3:
        fy = "25-26"
        next_ser = len(df_t) + 1 if not df_t.empty else 1
        auto_no = f"VIL/{fy}/{bc_code}/{next_ser:03d}" if sel_br != "Select" else ""
        lr_no = st.text_input("LR No*", value=auto_no if lr_mode == "Auto" else "", key=f"lrno_{k}")

    st.divider()
    # Party Selection
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        bill_pty = st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
        cnor = st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
        cnor_d = parties[parties['Name'] == cnor].iloc[0] if cnor != "Select" else {}
    with cp2:
        cnee = st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        cnee_d = parties[parties['Name'] == cnee].iloc[0] if cnee != "Select" else {}
        sel_bank = st.selectbox("Select Bank*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")
        bk_d = banks[banks['Name'] == sel_bank].iloc[0] if sel_bank != "Select" else {}
    with cp3:
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"rk_{k}")
        paid_by = st.selectbox("Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")
        ship_to = st.text_area("Ship-To Address", value=cnee_d.get('Address', ''), key=f"st_{k}")

    # Form with Own/Hired Logic
    with st.form(f"lr_form_{k}"):
        f1, f2, f3 = st.columns(3)
        with f1:
            date = st.date_input("Date", datetime.today())
            v_no = st.selectbox("Vehicle*", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else st.text_input("Vehicle No*")
            mat = st.text_input("Material")
        with f2:
            fl, tl = st.text_input("From"), st.text_input("To")
            articles = st.number_input("Articles/Nag", min_value=1)
            pkg = st.selectbox("Pkg", ["Drums", "Bags", "Boxes", "Loose"])
        with f3:
            n_wt, c_wt = st.number_input("Net Wt"), st.number_input("Chg Wt")
            freight = st.number_input("Freight", min_value=0.0)
            show_fr = st.checkbox("Print Freight?", value=True)
            inv = st.text_input("Inv No")

        # Own/Hired Expenses
        if v_cat == "Own Fleet":
            col_ex1, col_ex2, col_ex3 = st.columns(3)
            dsl = col_ex1.number_input("Diesel")
            toll = col_ex2.number_input("Toll")
            adv = col_ex3.number_input("Adv")
            h_c = 0.0
        else:
            h_c = st.number_input("Hired Charges")
            dsl, toll, adv = 0.0, 0.0, 0.0

        if st.form_submit_button("SAVE & GENERATE"):
            if sel_br != "Select" and bill_pty != "Select" and v_no and freight > 0:
                prof = (freight - h_c) if v_cat == "Market Hired" else (freight - dsl - toll - adv)
                row = [str(date), lr_no, v_cat, bill_pty, cnee, paid_by, n_wt, c_wt, pkg, risk, mat, articles, v_no, "Driver", "OWN" if v_cat=="Own Fleet" else "Hired", fl, tl, freight, h_c, dsl, adv, toll, 0, prof]
                if save_row("trips", row):
                    st.success("✅ Saved!")
                    lr_data_pdf = {
                        "LR No": lr_no, "Date": str(date), "Vehicle": v_no, "Risk": risk, "Articles": articles,
                        "BrName": br_info.get('Name',''), "BrGST": br_info.get('GST',''), "BrAddr": br_info.get('Address',''),
                        "BillP": bill_pty, "Cnor": cnor, "CnorGST": cnor_d.get('GST',''), "CnorAddr": cnor_d.get('Address',''),
                        "Cnee": cnee, "CneeGST": cnee_d.get('GST',''), "CneeAddr": cnee_d.get('Address',''),
                        "Material": mat, "NetWt": n_wt, "ChgWt": c_wt, "From": fl, "To": tl, "Freight": freight,
                        "Bank": f"{bk_d.get('Name','')} {bk_d.get('A_C_No','')}", "PaidBy": paid_by, "InvNo": inv, "ShipTo": ship_to
                    }
                    pdf_bytes = generate_lr_pdf_reportlab(lr_data_pdf, show_fr)
                    st.download_button("📥 DOWNLOAD PDF", pdf_bytes, f"LR_{lr_no}.pdf", "application/pdf")

elif menu == "LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR No / Party")
    if not df_t.empty:
        df_show = df_t.copy()
        if search:
            df_show = df_show[df_show.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        st.dataframe(df_show, use_container_width=True)
