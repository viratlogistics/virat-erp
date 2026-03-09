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

def safe_float(val):
    try:
        if val == "" or val is None: return 0.0
        return float(str(val).replace(',', ''))
    except: return 0.0

# --- 2. UPDATED PDF ENGINE ---
def generate_lr_pdf(lr, show_fr=True):
    pdf = FPDF()
    pdf.add_page()
    def s(v): return str(v) if v is not None else ""
    
    pdf.set_font("Arial", 'B', 16); pdf.cell(100, 8, "VIRAT LOGISTICS", ln=1)
    pdf.set_font("Arial", '', 8); pdf.cell(190, 4, f"GST: {s(lr.get('BrGST', ''))}", ln=True); pdf.ln(5)
    pdf.line(10, 30, 200, 30); pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 8, f"LR No: {s(lr.get('LR No'))}", 1); pdf.cell(95, 8, f"Date: {s(lr.get('Date'))}", 1, ln=True)
    pdf.cell(95, 8, f"Vehicle: {s(lr.get('Vehicle'))}", 1); pdf.cell(95, 8, f"From-To: {s(lr.get('From'))}-{s(lr.get('To'))}", 1, ln=True)
    
    pdf.ln(2); pdf.cell(190, 6, "CONSIGNOR & CONSIGNEE DETAILS", 1, 1, 'C')
    pdf.set_font("Arial", '', 8)
    pdf.multi_cell(190, 5, f"Consignor: {s(lr.get('Consignor'))}\nAddress: {s(lr.get('CnorAddr'))}\nConsignee: {s(lr.get('Consignee'))}", 1)
    
    pdf.ln(2); pdf.set_font("Arial", 'B', 8)
    pdf.cell(40, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(20, 7, "Qty", 1); pdf.cell(30, 7, "N.Wt", 1); pdf.cell(30, 7, "C.Wt", 1); pdf.cell(40, 7, "Freight", 1, ln=True)
    
    pdf.set_font("Arial", '', 8)
    pdf.cell(40, 10, s(lr.get('Material')), 1); pdf.cell(30, 10, s(lr.get('Pkg')), 1); pdf.cell(20, 10, s(lr.get('Art')), 1); pdf.cell(30, 10, s(lr.get('Weight')), 1); pdf.cell(30, 10, s(lr.get('CWt')), 1)
    amt = f"Rs. {s(lr.get('Freight'))}" if show_fr else "T.B.B."
    pdf.cell(40, 10, amt, 1, ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN APP ---
df_m, df_t = load("masters"), load("trips")

if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'last_pdf' not in st.session_state: st.session_state.last_pdf = None

# Sidebar Menu (SIRF EK BAAR)
menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry", "3. LR Register", "4. Financial Ledger"])

# --- MENU 1: MASTERS ---
if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Bank", "Branch"])
    with st.form("m_form_new", clear_on_submit=True):
        n = st.text_input("Name"); g = st.text_input("GST/Account No"); a = st.text_area("Address")
        if st.form_submit_button("Add Master"):
            if n: save("masters", [m_type, n, g, a]); st.rerun()
    if not df_m.empty:
        curr = df_m[df_m['Type'] == m_type]
        st.dataframe(curr)

# --- MENU 2: LR ENTRY (COMPLETE FIX) ---
elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    k = st.session_state.reset_k
    def gl(t): return sorted(df_m[df_m['Type'] == t]['Name'].tolist()) if not df_m.empty else []

    with st.form(f"lr_final_form_{k}"):
        st.subheader("🚛 Trip & Party Info")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
            sel_broker = "OWN"
            if v_cat == "Market Hired":
                sel_broker = st.selectbox("Select Broker*", ["Select"] + gl("Broker"), key=f"brok_{k}")
            lr_no = st.text_input("LR No*", value=f"VIL/{len(df_t)+1:03d}", key=f"lr_{k}")
            vn = st.text_input("Vehicle No", key=f"veh_{k}")

        with c2:
            bill_p = st.selectbox("Billing Party (Master)*", ["Select"] + gl("Party"), key=f"bp_{k}")
            p_data = df_m[(df_m['Name'] == bill_p) & (df_m['Type'] == 'Party')].iloc[0] if bill_p != "Select" else {}
            cn = st.text_input("Consignor Name", value=str(p_data.get('Name', '')), key=f"cn_{k}")
            cn_gst = st.text_input("Consignor GST", value=str(p_data.get('GST', '')), key=f"cgst_{k}")
            cn_addr = st.text_area("Consignor Address", value=str(p_data.get('Address', '')), key=f"cadr_{k}", height=65)

        with c3:
            ce = st.text_input("Consignee Name", key=f"ce_{k}")
            ce_gst = st.text_input("Consignee GST", key=f"ceg_{k}")
            fl, tl = st.text_input("From City", key=f"fr_{k}"), st.text_input("To City", key=f"to_{k}")

        st.divider()
        st.subheader("📦 Consignment Details")
        f1, f2, f3 = st.columns(3)
        mt = f1.text_input("Material Name", key=f"mat_{k}")
        pkg = f1.selectbox("Packaging", ["Bags", "Drums", "Boxes", "Loose", "Pallets"], key=f"pkg_{k}")
        art = f2.number_input("Articles (Qty)", min_value=0, step=1, key=f"art_{k}")
        nw = f2.number_input("Net Weight", key=f"nw_{k}")
        cw = f3.number_input("Charged Weight", key=f"cw_{k}")
        fr = f3.number_input("Total Freight", key=f"frt_{k}")
        show_fr = st.checkbox("Show Freight in PDF?", value=True, key=f"shf_{k}")

        st.divider()
        st.subheader("💰 Expenses")
        if v_cat == "Own Fleet":
            e1, e2, e3 = st.columns(3)
            dsl = e1.number_input("Diesel", key=f"dsl_{k}")
            toll = e2.number_input("Toll", key=f"tol_{k}")
            drv = e3.number_input("Driver Adv", key=f"drv_{k}")
            hc = 0.0
        else:
            hc = st.number_input("Hired Charges", key=f"hc_{k}")
            dsl = toll = drv = 0.0

        if st.form_submit_button("🚀 SAVE LR & GENERATE"):
            # Columns: Date, LR_No, Type, Party, Cnor, CnorGST, CnorAddr, Cnee, CneeGST, Pkg, Mat, Art, Veh, Broker, From, To, Freight, CWt, NWt, Profit
            row = [str(date.today()), lr_no, v_cat, bill_p, cn, cn_gst, cn_addr, ce, ce_gst, pkg, mt, art, vn, sel_broker, fl, tl, fr, cw, nw, (fr-hc-dsl-toll-drv)]
            save("trips", row)
            st.session_state.last_pdf = {"LR No": lr_no, "Date": str(date.today()), "Vehicle": vn, "Consignor": cn, "CnorAddr": cn_addr, "Consignee": ce, "From": fl, "To": tl, "Material": mt, "Weight": nw, "Freight": fr, "Pkg": pkg, "Art": art, "CWt": cw}
            st.session_state.reset_k += 1; st.rerun()

    if st.session_state.last_pdf:
        st.success("✅ Saved!")
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.last_pdf), f"LR_{st.session_state.last_pdf['LR No']}.pdf")
        if st.button("New Entry"): st.session_state.last_pdf = None; st.rerun()

# --- MENU 3 & 4 (REGISTER & LEDGER) ---
elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    if not df_t.empty: st.dataframe(df_t)

elif menu == "4. Financial Ledger":
    st.title("💳 Financial Ledger")
    df_p = load("payments")
    with st.form("pay_entry_fixed"):
        all_n = sorted(df_m[df_m['Type'].isin(['Party', 'Broker'])]['Name'].unique().tolist()) if not df_m.empty else []
        p_name = st.selectbox("Select Name", ["Select"] + all_n)
        p_amt = st.number_input("Amount")
        p_type = st.radio("Type", ["Received", "Paid"], horizontal=True)
        if st.form_submit_button("Save Payment"):
            if p_name != "Select":
                save("payments", [str(date.today()), p_name, p_amt, p_type])
                st.success("Payment Saved!"); st.rerun()
