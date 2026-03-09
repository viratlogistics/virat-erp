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
st.set_page_config(page_title="Virat Logistics ERP v6.0", layout="wide")

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

# --- 2. PDF ENGINE (REPORTLAB) ---
def generate_lr_pdf(lr_data, show_fr):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    # Header Section
    elements.append(Paragraph(f"<b>{lr_data['BrName']}</b>", styles['Title']))
    elements.append(Paragraph(f"GST No: {lr_data['BrGST']} | {lr_data['BrCode']}", styles['Normal']))
    elements.append(Paragraph(f"Address: {lr_data['BrAddr']}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # Info Row
    info_data = [[f"LR No: {lr_data['LR No']}", f"Date: {lr_data['Date']}", f"Vehicle: {lr_data['Vehicle']}"]]
    t1 = Table(info_data, colWidths=[180, 150, 180])
    t1.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')]))
    elements.append(t1)
    elements.append(Spacer(1, 10))

    # Party Table
    party_data = [
        ["CONSIGNOR", "CONSIGNEE", "BILLING PARTY"],
        [Paragraph(f"{lr_data['Cnor']}<br/>GST: {lr_data['CnorGST']}", styles['Normal']), 
         Paragraph(f"{lr_data['Cnee']}<br/>GST: {lr_data['CneeGST']}", styles['Normal']), 
         Paragraph(f"{lr_data['Party']}", styles['Normal'])]
    ]
    t2 = Table(party_data, colWidths=[170, 170, 170])
    t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t2)
    elements.append(Spacer(1, 15))

    # Material Table
    fr_val = f"Rs. {lr_data['Freight']}" if show_fr else "T.B.B."
    mat_data = [
        ["Material", "Nag", "Weight", "From-To", "Freight"],
        [lr_data['Material'], lr_data['Articles'], lr_data['Weight'], f"{lr_data['From']}-{lr_data['To']}", fr_val]
    ]
    t3 = Table(mat_data, colWidths=[160, 50, 70, 130, 100])
    t3.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elements.append(t3)

    # Footer
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"<b>Bank:</b> {lr_data['Bank']} | <b>Paid By:</b> {lr_data['PaidBy']}", styles['Normal']))
    elements.append(Spacer(1, 40))
    elements.append(Table([["Consignor Sign", "", "For VIRAT LOGISTICS"]], colWidths=[200, 110, 200]))

    doc.build(elements)
    return buffer.getvalue()

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("Menu", ["Create LR", "LR Register", "Master Settings"])

if menu == "Master Settings":
    st.title("🏗️ Master Management")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    with st.form("master_v6"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Name*")
            gst = st.text_input("GST Number")
        with c2:
            code = st.text_input("Branch Code (BC-01 / BC-02)")
            addr = st.text_area("Address")
        if st.form_submit_button("Save"):
            if name: save_row("masters", [m_type, name, gst, addr, code, "", "", "", ""]); st.rerun()
    st.dataframe(df_m[df_m['Type'] == m_type] if not df_m.empty else [])

elif menu == "Create LR":
    st.title("📝 CREATE LR")
    if st.button("🆕 RESET FORM"):
        st.session_state.reset_k += 1; st.session_state.pdf_ready = None; st.rerun()

    k = st.session_state.reset_k
    def get_list(t): return df_m[df_m['Type'] == t] if not df_m.empty else pd.DataFrame()
    branches = get_list('Branch'); banks = get_list('Bank'); parties = get_list('Party'); vehicles = get_list('Vehicle'); brokers = get_list('Broker')

    # TOP: Branch & LR No
    st.markdown("### 🏢 Branch & Numbering")
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_br = st.selectbox("Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
        br_info = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
        bc = br_info.get('Code', 'XX')
    with col2:
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
    with col3:
        fy = "25-26"
        lr_no = st.text_input("LR No*", value=f"VIL/{fy}/{bc}/{len(df_t)+1:03d}" if sel_br != "Select" else "", key=f"lrno_{k}")

    st.divider()
    # PARTIES: New Party Logic & Freight Paid By
    st.markdown("### 🤝 Party Details")
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        new_p = st.checkbox("New Billing Party?", key=f"np_{k}")
        bill_p = st.text_input("Billing Party Name") if new_p else st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
        new_cn = st.checkbox("New Consignor?", key=f"ncn_{k}")
        cnor = st.text_input("Consignor Name") if new_cn else st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
        cn_gst = parties[parties['Name'] == cnor].iloc[0].get('GST', '') if not new_cn and cnor != "Select" else ""
    with cp2:
        new_ce = st.checkbox("New Consignee?", key=f"nce_{k}")
        cnee = st.text_input("Consignee Name") if new_ce else st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        ce_gst = parties[parties['Name'] == cnee].iloc[0].get('GST', '') if not new_ce and cnee != "Select" else ""
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")
    with cp3:
        sel_bank = st.selectbox("Bank Details*", ["Select"] + banks['Name'].tolist(), key=f"bk_{k}")
        fl, tl = st.text_input("From"), st.text_input("To")
        ship_to = st.text_area("Ship-To Address", value=parties[parties['Name'] == cnee].iloc[0].get('Address', '') if not new_ce and cnee != "Select" else "")

    # MAIN FORM: Expenses & Articles
    with st.form(f"form_{k}"):
        st.markdown("---")
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            v_no = st.selectbox("Vehicle*", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            mat = st.text_input("Material")
            art = st.number_input("Nag/Articles", min_value=1)
        with f2:
            wt = st.number_input("Weight")
            fr = st.number_input("Freight Amount*", min_value=0.0)
            if v_cat == "Market Hired":
                brk = st.selectbox("Select Broker", ["Select"] + brokers['Name'].tolist())
                hc = st.number_input("Hired Charges")
            else:
                dsl = st.number_input("Diesel")
                toll = st.number_input("Toll")
        with f3:
            show_fr = st.checkbox("Print Freight in PDF?", value=True)
            if v_cat == "Own Fleet":
                drv_ex = st.number_input("Driver Exp")
                oth = st.number_input("Other Exp")
            else:
                drv_ex, toll, dsl, oth, hc = 0, 0, 0, 0, hc

        if st.form_submit_button("🚀 SAVE & GENERATE PDF"):
            if sel_br != "Select" and bill_p != "Select" and fr > 0:
                h_c = hc if v_cat == "Market Hired" else 0.0
                p_val = (fr - h_c) if v_cat == "Market Hired" else (fr - dsl - toll - drv_ex - oth)
                # Exact Sheet Row: Date, LR No, Type, Party, Consignor, Consignor_GST, Consignor_Add, Consignee, Consignee_GST, Consignee_Add, Material, Weight, Vehicle, Driver, Broker, From, To, Freight, HiredCharges, Diesel, DriverExp, Toll, Other, Profit
                row = [str(d), lr_no, v_cat, bill_p, cnor, cn_gst, "", cnee, ce_gst, "", mat, wt, v_no, "Driver", "OWN" if v_cat=="Own Fleet" else brk, fl, tl, fr, h_c, dsl, drv_ex, toll, oth, p_val]
                if save_row("trips", row):
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Material": mat, "Articles": art, "Weight": wt,
                        "BrName": sel_br, "BrGST": br_info.get('GST', ''), "BrCode": bc, "BrAddr": br_info.get('Address', ''),
                        "Party": bill_p, "Cnor": cnor, "CnorGST": cn_gst, "Cnee": cnee, "CneeGST": ce_gst,
                        "From": fl, "To": tl, "Freight": fr, "Bank": sel_bank, "PaidBy": paid_by, "ShipTo": ship_to, "ShowFr": show_fr
                    }
                    st.success("✅ Saved!")

    if st.session_state.pdf_ready:
        st.divider()
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, st.session_state.pdf_ready['ShowFr']), f"LR_{st.session_state.pdf_ready['LR No']}.pdf")

elif menu == "LR Register":
    st.title("📋 LR REGISTER")
    st.dataframe(df_t, use_container_width=True)
