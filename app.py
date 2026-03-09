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
st.set_page_config(page_title="Virat Logistics ERP v6.1", layout="wide")

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

def delete_master_row(sheet_name, name):
    try:
        ws = sh.worksheet(sheet_name)
        cell = ws.find(name)
        ws.delete_rows(cell.row)
        return True
    except: return False

# --- 2. PDF ENGINE ---
def generate_lr_pdf(lr_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{lr_data.get('BrName', 'VIRAT LOGISTICS')}</b>", styles['Title']), Spacer(1, 10)]
    
    data = [
        ["LR No", lr_data.get('LR No'), "Date", lr_data.get('Date')],
        ["Consignor", lr_data.get('Cnor'), "Consignee", lr_data.get('Cnee')],
        ["Vehicle", lr_data.get('Vehicle'), "Material", lr_data.get('Material')],
        ["Freight", f"Rs. {lr_data.get('Freight')}", "Paid By", lr_data.get('PaidBy')]
    ]
    t = Table(data, colWidths=[100, 150, 100, 150])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (0,-1), colors.lightgrey)]))
    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

# Session States for Auto-Numbering and Edit
if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'edit_data' not in st.session_state: st.session_state.edit_data = {}

menu = st.sidebar.selectbox("Menu", ["Create LR", "LR Register", "Master Settings"])

# --- MASTER SETTINGS (WITH EDIT/DELETE) ---
if menu == "Master Settings":
    st.title("🏗️ Master Management")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    
    with st.form("master_v61"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name*")
        gst = c1.text_input("GST Number")
        code = c2.text_input("Branch Code (BC-01)")
        addr = c2.text_area("Address")
        if st.form_submit_button("Add to Master"):
            if name: save_row("masters", [m_type, name, gst, addr, code, "", "", "", ""]); st.rerun()

    st.markdown("---")
    st.subheader(f"Existing {m_type}s")
    if not df_m.empty:
        curr_m = df_m[df_m['Type'] == m_type]
        for i, m_row in curr_m.iterrows():
            mc1, mc2 = st.columns([4, 1])
            mc1.write(f"**{m_row['Name']}** | GST: {m_row['GST']} | Code: {m_row['Code']}")
            if mc2.button("🗑️ Delete", key=f"del_{m_type}_{i}"):
                if delete_master_row("masters", m_row['Name']): st.rerun()

# --- CREATE / EDIT LR ---
elif menu == "Create LR":
    st.title("📝 EDIT LR" if st.session_state.edit_mode else "📝 CREATE LR")
    if st.button("🆕 RESET / START NEW"):
        st.session_state.edit_mode = False; st.session_state.reset_k += 1; st.rerun()

    k = st.session_state.reset_k
    ed = st.session_state.edit_data if st.session_state.edit_mode else {}
    
    def get_list(t): return df_m[df_m['Type'] == t] if not df_m.empty else pd.DataFrame()
    branches = get_list('Branch'); parties = get_list('Party'); vehicles = get_list('Vehicle'); brokers = get_list('Broker')

    # Branch & Auto Numbering
    st.markdown("### 🏢 Unit Details")
    c1, c2, c3 = st.columns(3)
    sel_br = c1.selectbox("Select Branch*", ["Select"] + branches['Name'].tolist(), key=f"br_{k}")
    br_info = branches[branches['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
    bc = br_info.get('Code', 'XX')
    
    v_cat = c2.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, index=0 if ed.get('Type') != "Market Hired" else 1, key=f"vcat_{k}")
    
    # Auto-Numbering Logic (Changes instantly on branch select)
    next_no = f"VIL/25-26/{bc}/{len(df_t)+1:03d}"
    lr_no = c3.text_input("LR Number*", value=ed.get('LR No', next_no), key=f"lrno_{k}")

    st.divider()
    # Party Selection with NEW Checkboxes
    st.markdown("### 🤝 Party & Broker")
    cp1, cp2, cp3 = st.columns(3)
    
    with cp1:
        is_np = st.checkbox("New Party?")
        bill_p = st.text_input("Enter Party") if is_np else st.selectbox("Billing Party*", ["Select"] + parties['Name'].tolist(), key=f"bp_{k}")
        is_ncn = st.checkbox("New Consignor?")
        cnor = st.text_input("Enter Consignor") if is_ncn else st.selectbox("Consignor*", ["Select"] + parties['Name'].tolist(), key=f"cn_{k}")
    
    with cp2:
        is_nce = st.checkbox("New Consignee?")
        cnee = st.text_input("Enter Consignee") if is_nce else st.selectbox("Consignee*", ["Select"] + parties['Name'].tolist(), key=f"ce_{k}")
        paid_by = st.selectbox("Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pb_{k}")
    
    with cp3:
        fl, tl = st.text_input("From", value=ed.get('From', '')), st.text_input("To", value=ed.get('To', ''))
        risk = st.radio("Risk", ["Owner Risk", "Insured"], horizontal=True)

    with st.form(f"form_{k}"):
        st.markdown("---")
        f1, f2, f3 = st.columns(3)
        d = f1.date_input("Date", date.today())
        v_no = f1.selectbox("Vehicle*", ["Select"] + vehicles['Name'].tolist()) if v_cat == "Own Fleet" else f1.text_input("Market Vehicle No*")
        mat = f2.text_input("Material", value=ed.get('Material', ''))
        art = f2.number_input("Articles (Nag)", min_value=1)
        wt = f3.number_input("Weight", value=float(ed.get('Weight', 0.0)))
        fr = f3.number_input("Freight Amount*", min_value=0.0, value=float(ed.get('Freight', 0.0)))

        # Expenses & Broker Logic
        if v_cat == "Market Hired":
            is_nb = st.checkbox("New Broker?")
            brk = st.text_input("Broker Name") if is_nb else st.selectbox("Broker", ["Select"] + brokers['Name'].tolist())
            hc = st.number_input("Hired Charges")
            dsl, toll, drv_ex, oth = 0, 0, 0, 0
        else:
            dsl, toll, drv_ex, oth, hc, brk = f1.number_input("Diesel"), f2.number_input("Toll"), f3.number_input("Driver Exp"), 0, 0, "OWN"

        if st.form_submit_button("🚀 SAVE BILTY"):
            prof = (fr - hc) if v_cat == "Market Hired" else (fr - dsl - toll - drv_ex)
            row = [str(d), lr_no, v_cat, bill_p, cnor, "", "", cnee, "", "", mat, wt, v_no, "Driver", brk, fl, tl, fr, hc, dsl, drv_ex, toll, oth, prof]
            if save_row("trips", row):
                st.success("✅ Saved!"); st.rerun()

# --- REGISTER (EDIT & DOWNLOAD) ---
elif menu == "LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR/Party")
    df_f = df_t.copy()
    if search: df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
    
    for i, row in df_f.iterrows():
        with st.expander(f"LR: {row['LR No']} | {row['Consignee']} | ₹{row['Freight']}"):
            rc1, rc2 = st.columns(2)
            if rc1.button("✏️ Edit", key=f"reg_ed_{i}"):
                st.session_state.edit_mode = True
                st.session_state.edit_data = row
                st.rerun()
            
            pdf_bytes = generate_lr_pdf(row.to_dict())
            rc2.download_button("📥 Download PDF", pdf_bytes, f"LR_{row['LR No']}.pdf", key=f"reg_pdf_{i}")
    st.dataframe(df_f)
