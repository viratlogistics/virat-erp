import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONFIG & DATABASE ---
st.set_page_config(page_title="Virat Master ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_sh():
    info = json.loads(st.secrets["gcp_service_account"]["json_key"])
    creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open("Virat_Logistics_Data")

sh = get_sh()

def load(name):
    try:
        ws = sh.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save(name, row): sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')

# --- 2. DATA CLEANING ---
df_t, df_p, df_a, df_d = load("trips"), load("payments"), load("admin"), load("drivers")
for c in ["Freight","HiredCharges","Profit","Diesel","Toll","DriverExp"]:
    if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)

# --- 3. PDF GENERATOR ENGINE ---
def create_pdf(title, data_list, headers, total=None):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "VIRAT LOGISTICS", ln=1, align='C')
    pdf.set_font("Arial", 'B', 12); pdf.cell(190, 10, title, ln=1, align='C'); pdf.ln(5)
    pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230,230,230)
    col_width = 190 / len(headers)
    for h in headers: pdf.cell(col_width, 10, h, 1, 0, 'C', 1)
    pdf.ln(); pdf.set_font("Arial", '', 8)
    for row in data_list:
        for item in row: pdf.cell(col_width, 8, str(item), 1)
        pdf.ln()
    if total is not None:
        pdf.set_font("Arial", 'B', 10); pdf.cell(190 - col_width, 10, "CLOSING BALANCE", 1, 0, 'R'); pdf.cell(col_width, 10, f"{total}", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTH ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    with st.sidebar:
        if st.text_input("User") == "admin" and st.text_input("Pass", type="password") == "1234":
            if st.button("Login"): st.session_state.login = True; st.rerun()
    st.stop()

menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard","Add LR","LR Manager","Monthly Bill","P&L Account","Vehicle Profit","Driver Salary","Party Ledger","Broker Ledger","Record Payment"])

# --- 5. MODULES ---
if menu == "Dashboard":
    p_in, b_out = df_p[df_p["Category"]=="Party"]["Amount"].sum(), df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    st.title("📊 Cash & Fund Flow")
    c1,c2,c3 = st.columns(3)
    c1.metric("Cash Collected", f"₹{p_in:,.0f}")
    c2.metric("Expenses Paid", f"₹{(b_out+df_a['Amount'].sum()):,.0f}")
    c3.metric("Net Cashflow", f"₹{(p_in - b_out - df_a['Amount'].sum()):,.0f}")
    st.divider(); f1,f2 = st.columns(2)
    f1.metric("Receivables (Lena Hai)", f"₹{(df_t['Freight'].sum()-p_in):,.0f}")
    f2.metric("Payables (Dena Hai)", f"₹{(df_t['HiredCharges'].sum()-b_out):,.0f}")

elif menu == "Add LR":
    st.header("📝 Create New LR")
    v_type = st.radio("Trip Type", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        with c1: d, pty, fl = st.date_input("Date"), st.text_input("Party*"), st.text_input("From")
        with c2: v_no, tl, mat = st.text_input("Vehicle No*"), st.text_input("To"), st.text_input("Material")
        with c3:
            fr = st.number_input("Freight*", min_value=0.0)
            if v_type == "Market Hired":
                br, hc = st.text_input("Broker"), st.number_input("Hired Chg")
                dsl, tll, de = 0, 0, 0
            else:
                br, hc = "", 0
                dsl, tll, de = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Exp")
        if st.form_submit_button("SAVE"):
            pf = (fr-hc) if v_type=="Market Hired" else (fr-(dsl+tll+de))
            row = [str(d), f"LR-{len(df_t)+1001}", v_type, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, fl, tl, fr, hc, dsl, de, tll, 0, pf]
            save("trips", row); st.success("Saved!"); st.rerun()

elif menu == "LR Manager":
    st.header("🔍 LR Manager")
    sq = st.text_input("Search")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            pdf_data = [[r['Date'], r['LR'], r['Vehicle'], r['From'], r['To'], r['Freight']]]
            st.download_button("📥 Print LR", create_pdf("CONSIGNMENT NOTE", pdf_data, ["Date","LR","Veh","From","To","Amt"]), f"{r['LR']}.pdf", key=f"p_{i}")
            if st.button("Delete", key=f"d_{i}"):
                sh.worksheet("trips").delete_rows(sh.worksheet("trips").find(str(r['LR'])).row); st.rerun()

elif menu == "Monthly Bill":
    st.header("📅 Monthly Bill Builder")
    if not df_t.empty:
        sp = st.selectbox("Party", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy(); m_df.insert(0, "Select", True)
        ed = st.data_editor(m_df, hide_index=True); sel = ed[ed["Select"] == True]
        if not sel.empty:
            bill_data = sel[["Date","LR","Vehicle","Freight"]].values.tolist()
            st.download_button("📥 Download Bill PDF", create_pdf(f"BILL: {sp}", bill_data, ["Date","LR","Veh","Amt"], sel['Freight'].sum()), f"Bill_{sp}.pdf")

elif menu == "P&L Account":
    st.header("📉 Profit & Loss")
    rev, hire, adm = df_t['Freight'].sum(), df_t['HiredCharges'].sum(), df_a['Amount'].sum()
    fleet = df_t['Diesel'].sum() + df_t['Toll'].sum() + df_t['DriverExp'].sum()
    net = rev - hire - fleet - adm
    st.table(pd.DataFrame({"Description": ["Freight Revenue", "Hired Payouts", "Fleet Costs", "Admin Exp", "NET PROFIT"], "Amount": [rev, hire, fleet, adm, net]}))

elif menu == "Vehicle Profit":
    st.header("🚛 Own Vehicle Performance")
    # ONLY OWN FLEET
    own_df = df_t[df_t["Type"].str.contains("Own", case=False)]
    if not own_df.empty:
        v_r = own_df.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index()
        st.dataframe(v_r, use_container_width=True)
    else: st.info("No Own Vehicle Data")

elif menu == "Party Ledger" or menu == "Broker Ledger":
    cat = "Party" if "Party" in menu else "Broker"
    col = "Party" if cat=="Party" else "Broker"
    lbl = "Freight" if cat=="Party" else "HiredCharges"
    sp = st.selectbox("Select Name", df_t[col].unique() if col in df_t.columns else [])
    if sp:
        p_t = df_t[df_t[col]==sp]; p_p = df_p[(df_p["Name"]==sp) & (df_p["Category"]==cat)]
        bal = p_t[lbl].sum() - p_p["Amount"].sum()
        st.subheader(f"Balance Due: ₹{bal:,.0f}")
        
        # Prepare PDF Data: Combine Trips and Payments
        ledger_data = []
        for _, r in p_t.iterrows(): ledger_data.append([r['Date'], r['LR'], r['Vehicle'], r[lbl], 0])
        for _, p in p_p.iterrows(): ledger_data.append([p['Date'], "PAYMENT", p['Mode'], 0, p['Amount']])
        
        st.download_button("📥 Download Detailed Ledger PDF", create_pdf(f"LEDGER: {sp}", ledger_data, ["Date","Ref","Details","Debit","Credit"], bal), f"Ledger_{sp}.pdf")
        st.write("### Trip Details"); st.dataframe(p_t[["Date","LR","Vehicle",lbl]])
        st.write("### Payment Details"); st.dataframe(p_p[["Date","Amount","Mode"]])

elif menu == "Record Payment":
    with st.form("pay_f"):
        nm = st.selectbox("Name", list(set(df_t["Party"].tolist() + df_t["Broker"].tolist())))
        ct, am, md = st.selectbox("Cat", ["Party", "Broker"]), st.number_input("Amt"), st.selectbox("Mode", ["Cash","Bank"])
        if st.form_submit_button("Save"):
            save("payments", [str(date.today()), nm, ct, am, md]); st.rerun()
