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

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Virat ERP v7.0", layout="wide")

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

def save_row(sheet, row):
    try: sh.worksheet(sheet).append_row(row, value_input_option='USER_ENTERED'); return True
    except: return False

# --- 2. PDF ENGINE ---
def generate_pdf(lr):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>VIRAT LOGISTICS</b>", styles['Title']), Spacer(1, 10)]
    data = [
        ["LR No", lr.get('LR No',''), "Date", lr.get('Date','')],
        ["Party", lr.get('Party',''), "Vehicle", lr.get('Vehicle','')],
        ["Consignor", lr.get('Consignor',''), "Consignee", lr.get('Consignee','')],
        ["From-To", f"{lr.get('From','')}-{lr.get('To','')}", "Freight", f"Rs. {lr.get('Freight',0)}"]
    ]
    t = Table(data, colWidths=[100, 150, 100, 150])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black),('BACKGROUND',(0,0),(0,-1),colors.lightgrey)]))
    elements.append(t); doc.build(elements)
    return buffer.getvalue()

# --- 3. UI LOGIC ---
df_m = load_data("masters")
df_t = load_data("trips")

if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'ed_mode' not in st.session_state: st.session_state.ed_mode = False
if 'ed_data' not in st.session_state: st.session_state.ed_data = {}

menu = st.sidebar.selectbox("Menu", ["Create LR", "LR Register", "Master Settings"])

# --- MASTER SETTINGS ---
if menu == "Master Settings":
    st.title("🏗️ Master Management")
    m_type = st.radio("Category", ["Party", "Branch", "Vehicle", "Bank", "Broker"], horizontal=True)
    with st.form("m_v7"):
        c1, c2 = st.columns(2)
        n = c1.text_input("Name*"); g = c1.text_input("GST No")
        c = c2.text_input("Branch Code (e.g. BC-01)"); a = c2.text_area("Address")
        if st.form_submit_button("Save Master"):
            if n: save_row("masters", [m_type, n, g, a, c, "", "", "", ""]); st.rerun()
    st.divider()
    if not df_m.empty:
        for i, r in df_m[df_m['Type']==m_type].iterrows():
            mc1, mc2 = st.columns([5, 1])
            mc1.write(f"**{r['Name']}** | {r.get('GST','')} | {r.get('Code','')}")
            if mc2.button("🗑️", key=f"d_{i}"):
                sh.worksheet("masters").delete_rows(sh.worksheet("masters").find(r['Name']).row); st.rerun()

# --- CREATE LR ---
elif menu == "Create LR":
    st.title("📝 EDIT LR" if st.session_state.ed_mode else "📝 CREATE LR")
    if st.button("🆕 RESET FORM"):
        st.session_state.ed_mode = False; st.session_state.reset_k += 1; st.rerun()

    k, ed = st.session_state.reset_k, st.session_state.ed_mode
    def gl(t): return df_m[df_m['Type']==t]['Name'].tolist() if not df_m.empty else []

    # Branch & Instant Auto-Numbering
    c1, c2, c3 = st.columns(3)
    s_br = c1.selectbox("Branch*", ["Select"] + gl("Branch"), key=f"b_{k}")
    b_c = df_m[df_m['Name']==s_br]['Code'].values[0] if s_br != "Select" else "XX"
    v_c = c2.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"v_{k}")
    # Auto-number changes instantly when Branch changes
    l_no = c3.text_input("LR No*", value=st.session_state.ed_data.get('LR No', f"VIL/25-26/{b_c}/{len(df_t)+1:03d}"), key=f"ln_{k}")

    st.divider()
    cp1, cp2, cp3 = st.columns(3)
    # New Party / Broker logic
    p = cp1.text_input("New Party") if cp1.checkbox("New Party?") else cp1.selectbox("Party*", ["Select"] + gl("Party"), key=f"p_{k}")
    cn = cp1.text_input("New Consignor") if cp1.checkbox("New Consignor?") else cp1.selectbox("Consignor*", ["Select"] + gl("Party"), key=f"cn_{k}")
    ce = cp2.text_input("New Consignee") if cp2.checkbox("New Consignee?") else cp2.selectbox("Consignee*", ["Select"] + gl("Party"), key=f"ce_{k}")
    fr_l, to_l = cp3.text_input("From"), cp3.text_input("To")
    bk = cp3.selectbox("Bank", ["Select"] + gl("Bank"), key=f"bk_{k}")

    with st.form(f"f_{k}"):
        st.markdown("---")
        f1, f2, f3 = st.columns(3)
        dt = f1.date_input("Date", date.today())
        vn = f1.selectbox("Own Vehicle", ["Select"] + gl("Vehicle")) if v_c == "Own Fleet" else f1.text_input("Market Vehicle No")
        mt, art = f2.text_input("Material"), f2.number_input("Nag/Articles", min_value=1)
        wt, f_a = f3.number_input("Weight"), f3.number_input("Freight*", min_value=0.0)
        
        if v_c == "Market Hired":
            brk = st.text_input("New Broker") if st.checkbox("New Broker?") else st.selectbox("Broker", ["Select"] + gl("Broker"))
            hc = st.number_input("Hired Charges")
            dsl, drv, toll, oth = 0, 0, 0, 0
        else:
            dsl, drv, toll, oth, hc, brk = f1.number_input("Diesel"), f2.number_input("Driver Exp"), f3.number_input("Toll"), f3.number_input("Other"), 0, "OWN"

        if st.form_submit_button("SAVE BILTY"):
            prof = (f_a - hc) if v_c == "Market Hired" else (f_a - dsl - drv - toll - oth)
            # Match Sheet Order: Date, LR No, Type, Party, Consignor, Cons_GST, Cons_Add, Consignee, Cnee_GST, Cnee_Add, Material, Weight, Vehicle, Driver, Broker, From, To, Freight, HiredCharges, Diesel, DriverExp, Toll, Other, Profit
            row = [str(dt), l_no, v_c, p, cn, "", "", ce, "", "", mt, wt, vn, "Driver", brk, fr_l, to_l, f_a, hc, dsl, drv, toll, oth, prof]
            if save_row("trips", row): st.success("✅ Saved!"); st.rerun()

# --- REGISTER ---
elif menu == "LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR/Party")
    if not df_t.empty:
        df_f = df_t.copy()
        if search: df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        for i, r in df_f.iterrows():
            with st.expander(f"LR: {r['LR No']} | {r['Consignee']} | ₹{r['Freight']}"):
                rc1, rc2 = st.columns(2)
                if rc1.button("✏️ Edit", key=f"e_{i}"):
                    st.session_state.ed_mode, st.session_state.ed_data = True, r
                    st.rerun()
                rc2.download_button("📥 PDF", generate_pdf(r.to_dict()), f"LR_{r['LR No']}.pdf", key=f"p_{i}")
        st.dataframe(df_f)
