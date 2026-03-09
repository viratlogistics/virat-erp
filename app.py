import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import io
import json

# --- 1. SETUP ---
st.set_page_config(page_title="Virat ERP v8.2", layout="wide")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except: return None

sh = get_sh()

def load_data(sheet):
    try: 
        df = pd.DataFrame(sh.worksheet(sheet).get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 2. PROFESSIONAL PDF ENGINE (CRASH-PROOF) ---
def generate_pro_pdf(lr):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []
    
    # Helper to convert everything to string to avoid AttributeError
    s = lambda x: str(x) if x is not None else ""
    
    # Header Section
    elements.append(Paragraph(f"<font size=20><b>{s(lr.get('BrName', 'VIRAT LOGISTICS'))}</b></font>", styles['Title']))
    elements.append(Paragraph(f"GST No: {s(lr.get('BrGST', ''))} | Branch: {s(lr.get('BrCode', ''))}", styles['Normal']))
    elements.append(Paragraph(f"Address: {s(lr.get('BrAddr', ''))}", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    # LR Info Table
    info_data = [
        [f"LR No: {s(lr.get('LR No'))}", f"Date: {s(lr.get('Date'))}", f"Vehicle: {s(lr.get('Vehicle'))}"]
    ]
    t1 = Table(info_data, colWidths=[180, 150, 180])
    t1.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')]))
    elements.append(t1)
    elements.append(Spacer(1, 10))

    # Party Table
    party_data = [
        ["CONSIGNOR", "CONSIGNEE", "BILLING PARTY"],
        [Paragraph(s(lr.get('Consignor', '')), styles['Normal']), 
         Paragraph(s(lr.get('Consignee', '')), styles['Normal']), 
         Paragraph(s(lr.get('Party', '')), styles['Normal'])]
    ]
    t2 = Table(party_data, colWidths=[170, 170, 170])
    t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(t2)
    elements.append(Spacer(1, 15))

    # Goods Table
    mat_data = [
        ["No", "Description of Goods", "Nag", "Weight", "Freight"],
        ["1", s(lr.get('Material', '')), s(lr.get('Articles', '0')), s(lr.get('Weight', '0')), f"Rs. {s(lr.get('Freight', '0'))}"]
    ]
    t3 = Table(mat_data, colWidths=[30, 200, 70, 90, 120])
    t3.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elements.append(t3)

    # Footer
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"<b>Route:</b> {s(lr.get('From', ''))} to {s(lr.get('To', ''))} | <b>Bank:</b> {s(lr.get('Bank', ''))}", styles['Normal']))
    elements.append(Spacer(1, 40))
    elements.append(Table([["Consignor Signature", "", "For VIRAT LOGISTICS"]], colWidths=[200, 110, 200]))

    doc.build(elements)
    return buffer.getvalue()

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'ed_m_data' not in st.session_state: st.session_state.ed_m_data = {}

menu = st.sidebar.selectbox("Menu", ["Create LR", "LR Register", "Master Settings"])

if menu == "Master Settings":
    st.title("🏗️ Master Management (Edit/Delete)")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    
    with st.form("m_v82", clear_on_submit=True):
        c1, c2 = st.columns(2)
        n = c1.text_input("Name*", value=st.session_state.ed_m_data.get('Name', ''))
        g = c1.text_input("GST No", value=st.session_state.ed_m_data.get('GST', ''))
        code = c2.text_input("Branch Code (BC-01)", value=st.session_state.ed_m_data.get('Code', ''))
        addr = c2.text_area("Address", value=st.session_state.ed_m_data.get('Address', ''))
        if st.form_submit_button("Save to Master"):
            if n: 
                sh.worksheet("masters").append_row([m_type, n, g, addr, code, "", "", "", ""])
                st.session_state.ed_m_data = {}
                st.success("Saved!"); st.rerun()
    
    st.divider()
    if not df_m.empty:
        curr_m = df_m[df_m['Type'] == m_type]
        for i, r in curr_m.iterrows():
            mc1, mc2, mc3 = st.columns([4, 1, 1])
            mc1.write(f"**{r['Name']}** | {r.get('Code', r.get('Branch Code', ''))}")
            if mc2.button("✏️ Edit", key=f"me_{i}"):
                st.session_state.ed_m_data = r.to_dict()
                st.rerun()
            if mc3.button("🗑️", key=f"md_{i}"):
                sh.worksheet("masters").delete_rows(sh.worksheet("masters").find(r['Name']).row); st.rerun()

elif menu == "Create LR":
    st.title("📝 CREATE LR")
    if st.button("🆕 RESET FORM"):
        st.session_state.reset_k += 1; st.rerun()

    k = st.session_state.reset_k
    def gl(t): return df_m[df_m['Type']==t]['Name'].tolist() if not df_m.empty else []

    c1, c2, c3 = st.columns(3)
    s_br = c1.selectbox("Branch*", ["Select"] + gl("Branch"), key=f"b_{k}")
    br_row = df_m[df_m['Name']==s_br] if s_br != "Select" else pd.DataFrame()
    b_c = br_row.get('Code', br_row.get('Branch Code', pd.Series(['XX']))).values[0] if not br_row.empty else "XX"
    v_cat = c2.radio("Trip Category*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
    l_no = c3.text_input("LR Number*", value=f"VIL/25-26/{b_c}/{len(df_t)+1:03d}", key=f"ln_{k}")

    st.divider()
    cp1, cp2, cp3 = st.columns(3)
    p = cp1.text_input("New Party") if cp1.checkbox("New Party?") else cp1.selectbox("Party*", ["Select"] + gl("Party"), key=f"p_{k}")
    cn = cp1.text_input("New Consignor") if cp1.checkbox("New Consignor?") else cp1.selectbox("Consignor*", ["Select"] + gl("Party"), key=f"cn_{k}")
    ce = cp2.text_input("New Consignee") if cp2.checkbox("New Consignee?") else cp2.selectbox("Consignee*", ["Select"] + gl("Party"), key=f"ce_{k}")
    pb = cp2.selectbox("Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pb_{k}")
    fr_loc, to_loc = cp3.text_input("From"), cp3.text_input("To")
    bk = cp3.selectbox("Bank Details", ["Select"] + gl("Bank"), key=f"bk_{k}")

    with st.form(f"f_{k}"):
        f1, f2, f3 = st.columns(3)
        dt = f1.date_input("Date", date.today())
        vn = f1.selectbox("Own Vehicle", ["Select"] + gl("Vehicle")) if v_cat == "Own Fleet" else f1.text_input("Market Vehicle No*")
        mt, art = f1.text_input("Material"), f2.number_input("Nag/Articles", min_value=1)
        wt, f_a = f2.number_input("Weight"), f3.number_input("Freight Amount*", min_value=0.0)
        
        if v_cat == "Market Hired":
            brk = st.text_input("New Broker") if st.checkbox("New Broker?") else st.selectbox("Broker", ["Select"] + gl("Broker"))
            hc = st.number_input("Hired Charges")
            dsl, toll, drv, oth = 0, 0, 0, 0
        else:
            dsl, toll, drv, oth, hc, brk = f1.number_input("Diesel"), f2.number_input("Toll"), f3.number_input("Driver Exp"), f3.number_input("Other"), 0, "OWN"

        if st.form_submit_button("SAVE & GENERATE PDF"):
            # Columns match your sheet order exactly
            row = [str(dt), l_no, v_cat, p, cn, "", "", ce, "", "", mt, wt, vn, "Driver", brk, fr_loc, to_loc, f_a, hc, dsl, drv, toll, oth, (f_a-hc-dsl-toll-drv-oth)]
            sh.worksheet("trips").append_row(row, value_input_option='USER_ENTERED')
            st.success(f"LR {l_no} Saved!")

elif menu == "LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR/Party/Vehicle")
    if not df_t.empty:
        df_f = df_t.copy()
        if search: df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        for i, r in df_f.iterrows():
            with st.expander(f"LR: {r.get('LR No', '')} | {r.get('Party', '')}"):
                c1, c2 = st.columns(2)
                # Create a clean dictionary for PDF to avoid AttributeErrors
                pdf_dict = {k: str(v) for k, v in r.to_dict().items()}
                pdf_dict['BrName'] = "VIRAT LOGISTICS"
                pdf_dict['BrAddr'] = "Kosamba/Kim, Gujarat"
                
                try:
                    pdf_bytes = generate_pro_pdf(pdf_dict)
                    c2.download_button("📥 Download PDF", pdf_bytes, f"LR_{r.get('LR No')}.pdf", key=f"pdf_{i}")
                except:
                    c2.error("PDF Error")
        st.dataframe(df_f)
