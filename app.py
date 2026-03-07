import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONFIGURATION & CLOUD SYNC ---
st.set_page_config(page_title="Virat Logistics Ultimate ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except Exception as e:
        st.error(f"❌ Google Sheet Connection Fail: {e}")
        return None

sh = get_sh()

def load(name):
    try:
        ws = sh.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except Exception:
        st.warning(f"⚠️ Sheet '{name}' nahi mili. Please Sheet mein '{name}' tab banayein.")
        return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception:
        st.error(f"❌ Error: '{name}' sheet mein data save nahi hua. Kya aapne '{name}' tab banayi hai?")
        return False

# --- 2. DATA PROCESSING ---
df_t = load("trips")
df_p = load("payments")
df_a = load("admin")
df_d = load("drivers")

# Numeric Handling
num_cols = ["Freight", "HiredCharges", "Diesel", "Toll", "DriverExp", "Maintenance", "Hamali", "Penalty", "Advance", "Salary", "Amount"]
for df in [df_t, df_p, df_a, df_d]:
    for c in num_cols:
        if not df.empty and c in df.columns: 
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

# --- 3. PDF ENGINE ---
def create_pdf(title, data, headers, total=None):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, "VIRAT LOGISTICS", ln=1, align='C')
    pdf.set_font("Arial", 'B', 10); pdf.cell(190, 10, title, ln=1, align='C'); pdf.ln(5)
    pdf.set_font("Arial", 'B', 8); pdf.set_fill_color(230,230,230)
    cw = 190 / len(headers)
    for h in headers: pdf.cell(cw, 10, h, 1, 0, 'C', 1)
    pdf.ln(); pdf.set_font("Arial", '', 7)
    for row in data:
        for item in row: pdf.cell(cw, 8, str(item), 1)
        pdf.ln()
    if total is not None:
        pdf.set_font("Arial", 'B', 9); pdf.cell(190-cw, 10, "BALANCE", 1, 0, 'R'); pdf.cell(cw, 10, f"{total}", 1, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTH ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    with st.sidebar:
        if st.text_input("User") == "admin" and st.text_input("Pass", type="password") == "1234":
            if st.button("Access ERP"): st.session_state.login = True; st.rerun()
    st.warning("Please Login"); st.stop()

menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard", "Add LR", "LR Manager", "Driver Management", "Party Ledger", "Broker Ledger", "Vehicle Performance", "P&L Report", "Transactions"])

# --- 5. DASHBOARD (CASH & FUND FLOW) ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum() if not df_p.empty else 0
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum() if not df_p.empty else 0
    adm = df_a["Amount"].sum() if not df_a.empty else 0
    
    st.subheader("🌊 Cash Flow (Actual Cash)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Collected", f"₹{p_in:,.0f}")
    c2.metric("Total Cash Out", f"₹{(b_out+adm):,.0f}")
    c3.metric("Net Cashflow", f"₹{(p_in - b_out - adm):,.0f}")
    
    st.divider()
    st.subheader("📂 Fund Flow (Market Balance)")
    f1, f2 = st.columns(2)
    fr_total = df_t['Freight'].sum() if not df_t.empty else 0
    hr_total = df_t['HiredCharges'].sum() if not df_t.empty else 0
    f1.metric("Receivables (Lena Hai)", f"₹{(fr_total - p_in):,.0f}")
    f2.metric("Payables (Dena Hai)", f"₹{(hr_total - b_out):,.0f}")

# --- 6. ADD LR ---
elif menu == "Add LR":
    st.header("📝 Consignment Entry")
    v_type = st.radio("Category", ["Own Truck", "Market Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: d, pty, v_no = st.date_input("Date"), st.text_input("Party*"), st.text_input("Vehicle No*")
        with c2: fl, tl, mat = st.text_input("From"), st.text_input("To"), st.text_input("Material")
        with c3:
            fr = st.number_input("Freight*", min_value=0.0)
            if v_type == "Market Hired":
                br, hc = st.text_input("Broker"), st.number_input("Hired Chg")
                dsl, tll, de = 0, 0, 0
            else:
                br, hc = "OWN", 0
                dsl, tll, de = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Exp")
        
        if st.form_submit_button("SAVE"):
            prof = (fr - hc) if v_type == "Market Hired" else (fr - dsl - tll - de)
            row = [str(d), f"LR-{len(df_t)+1001}", v_type, pty, "", "", "", "", "", "", mat, 0, v_no, "Driver", br, fl, tl, fr, hc, dsl, de, tll, 0, prof]
            if save("trips", row): st.success("Saved!"); st.rerun()

# --- 7. LR MANAGER (EDIT/DELETE/PRINT) ---
elif menu == "LR Manager":
    sq = st.text_input("Search")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)] if not df_t.empty else pd.DataFrame()
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"ed_{i}"):
                up, uf, uh = st.text_input("Party", r['Party']), st.number_input("Freight", value=float(r['Freight'])), st.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("Update"):
                    upd = list(r.values); upd[3], upd[17], upd[18] = up, uf, uh
                    ws = sh.worksheet("trips"); ws.update(f'A{ws.find(str(r["LR"])).row}:X{ws.find(str(r["LR"])).row}', [upd]); st.rerun()
            pdf_data = [[r['Date'], r['LR'], r['Vehicle'], r['From'], r['To'], r['Freight']]]
            st.download_button("📥 Print LR", create_pdf("CONSIGNMENT NOTE", pdf_data, ["Date","LR","Veh","From","To","Amt"]), f"{r['LR']}.pdf", key=f"p_{i}")
            if st.button("Delete LR", key=f"d_{i}"):
                sh.worksheet("trips").delete_rows(sh.worksheet("trips").find(str(r["LR"])).row); st.rerun()

# --- 8. DRIVER MANAGEMENT (FIXED ERROR) ---
elif menu == "Driver Management":
    st.header("👨‍✈️ Driver Management")
    with st.form("d_f"):
        c1, c2 = st.columns(2)
        dn = c1.text_input("Driver Name"); dt = c1.date_input("Date")
        sal, adv, pen = c2.number_input("Monthly Salary"), c2.number_input("Advance"), c2.number_input("Penalty")
        if st.form_submit_button("Record Data"):
            if save("drivers", [str(dt), dn, "Present", adv, sal, pen]): st.success("Saved!"); st.rerun()
    
    if not df_d.empty:
        ds = df_d.groupby("Name").agg({"Advance":"sum", "Salary":"max", "Penalty":"sum", "Date":"count"}).reset_index()
        ds["Earned"] = (ds["Salary"]/30)*ds["Date"]
        ds["Due"] = ds["Earned"] - ds["Advance"] - ds["Penalty"]
        st.dataframe(ds.rename(columns={"Date":"Days"}), use_container_width=True)

# --- 9. VEHICLE PERFORMANCE (OWN ONLY) ---
elif menu == "Vehicle Performance":
    st.header("🚛 Own Vehicle Profitability")
    own = df_t[df_t["Type"].str.contains("Own", case=False, na=False)] if not df_t.empty else pd.DataFrame()
    if not own.empty:
        v_r = own.groupby("Vehicle").agg({"Freight":"sum", "Diesel":"sum", "Toll":"sum", "Profit":"sum"}).reset_index()
        st.dataframe(v_r, use_container_width=True)
        st.bar_chart(v_r.set_index("Vehicle")["Profit"])

# --- 10. LEDGERS (DETAILED) ---
elif "Ledger" in menu:
    cat = "Party" if "Party" in menu else "Broker"
    col = "Party" if cat=="Party" else "Broker"
    lbl = "Freight" if cat=="Party" else "HiredCharges"
    if not df_t.empty:
        sp = st.selectbox("Select Name", df_t[col].unique())
        p_t = df_t[df_t[col]==sp]; p_p = df_p[(df_p["Name"]==sp) & (df_p["Category"]==cat)]
        bal = p_t[lbl].sum() - p_p["Amount"].sum()
        st.subheader(f"Balance: ₹{bal:,.0f}")
        l_data = []
        for _, r in p_t.iterrows(): l_data.append([r['Date'], r['LR'], r['Vehicle'], r[lbl], 0])
        for _, p in p_p.iterrows(): l_data.append([p['Date'], "PAYMENT", p['Mode'], 0, p['Amount']])
        st.download_button("📥 PDF Ledger", create_pdf(f"LEDGER: {sp}", l_data, ["Date","Ref","Details","Debit","Credit"], bal), f"Ledger_{sp}.pdf")
        st.dataframe(p_t[["Date","LR","Vehicle",lbl]])

# --- 11. P&L REPORT ---
elif menu == "P&L Report":
    st.header("📉 P&L Statement")
    rev = df_t['Freight'].sum() if not df_t.empty else 0
    hire = df_t['HiredCharges'].sum() if not df_t.empty else 0
    adm = df_a['Amount'].sum() if not df_a.empty else 0
    fleet = (df_t['Diesel'].sum() + df_t['Toll'].sum() + df_t['DriverExp'].sum()) if not df_t.empty else 0
    
    st.columns(3)[0].metric("Revenue", f"₹{rev:,.0f}")
    st.columns(3)[1].metric("Total Costs", f"₹{(hire+fleet+adm):,.0f}")
    st.columns(3)[2].metric("Net Profit", f"₹{(rev-hire-fleet-adm):,.0f}")
    
    st.table(pd.DataFrame({
        "Description": ["Total Revenue", "Hired Payouts", "Fleet Maintenance", "Admin/Office Exp"],
        "Amount": [rev, hire, fleet, adm]
    }))

# --- 12. TRANSACTIONS ---
elif menu == "Transactions":
    with st.form("tr"):
        nm = st.selectbox("Name", list(set(df_t["Party"].tolist()+df_t["Broker"].tolist())))
        ct, am = st.selectbox("Type", ["Party", "Broker"]), st.number_input("Amount")
        if st.form_submit_button("Record"):
            if save("payments", [str(date.today()), nm, cat, am, "Cash"]): st.rerun()
