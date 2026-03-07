import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Virat Logistics Master ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_gspread_client():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}"); return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"
sh = client.open(SHEET_NAME) if client else None

# --- 2. CORE DATABASE UTILITIES ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        df = pd.DataFrame(ws.get_all_records())
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save_ws(ws_name, row_list):
    try:
        sh.worksheet(ws_name).append_row(row_list, value_input_option='USER_ENTERED')
        return True
    except: return False

def update_ws(ws_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(ws_name); cell = ws.find(str(lr_no))
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row], value_input_option='USER_ENTERED')
            return True
        return False
    except: return False

def delete_ws(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name); cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row); return True
        return False
    except: return False

# --- 3. REFRESH & NUMERIC DATA ---
if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")
    df_d = load_ws("drivers")
    
    for c in ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp"]:
        if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    if not df_d.empty:
        for c in ["Advance", "Salary"]:
            if c in df_d.columns: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').fillna(0)

# --- 4. PDF GENERATOR ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16); self.cell(190, 10, 'VIRAT LOGISTICS', ln=True, align='C'); self.ln(5)

def gen_ledger_pdf(name, trips, pmts, balance, lbl):
    pdf = PDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, f"LEDGER STATEMENT: {name} ({lbl})", ln=True)
    pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "Date", 1, 0, 'C', 1); pdf.cell(40, 10, "Ref", 1, 0, 'C', 1); pdf.cell(60, 10, "Detail", 1, 0, 'C', 1); pdf.cell(30, 10, "Debit", 1, 0, 'C', 1); pdf.cell(30, 10, "Credit", 1, 1, 'C', 1)
    pdf.set_font("Arial", '', 8)
    for _, r in trips.iterrows():
        amt = r['Freight'] if lbl == "Party" else r['HiredCharges']
        pdf.cell(30, 8, str(r['Date']), 1); pdf.cell(40, 8, str(r['LR']), 1); pdf.cell(60, 8, f"{r['Vehicle']}", 1)
        pdf.cell(30, 8, f"{amt}" if lbl=="Party" else "0", 1); pdf.cell(30, 8, "0" if lbl=="Party" else f"{amt}", 1, 1)
    for _, p in pmts.iterrows():
        pdf.cell(30, 8, str(p['Date']), 1); pdf.cell(40, 8, "PYMT", 1); pdf.cell(60, 8, p['Mode'], 1)
        pdf.cell(30, 8, "0" if lbl=="Party" else f"{p['Amount']}", 1); pdf.cell(30, 8, f"{p['Amount']}" if lbl=="Party" else "0", 1, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(130, 10, "TOTAL BALANCE", 1, 0, 'R', 1); pdf.cell(60, 10, f"Rs. {balance:,.2f}", 1, 1, 'C', 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTH & NAVIGATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔐 Virat Logistics ERP Login")
    with st.form("L"):
        u, p = st.text_input("User ID"), st.text_input("Password", type="password")
        if st.form_submit_button("Enter"):
            if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard", "Add LR", "LR Manager", "Monthly Bill Builder", "Driver Management", "Party Ledger", "Broker Ledger", "Vehicle Performance", "P&L Statement", "Record Transaction", "Office Expense"])

# --- 6. DASHBOARD ---
if menu == "Dashboard":
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm = df_a["Amount"].sum()
    st.title("📊 Cash & Fund Flow")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Collected", f"₹{p_in:,.0f}")
    c2.metric("Expenses Paid", f"₹{(b_out+adm):,.0f}")
    c3.metric("Net Cashflow", f"₹{(p_in - b_out - adm):,.0f}")
    st.divider(); f1, f2 = st.columns(2)
    f1.metric("Paisa Lena Hai (Party)", f"₹{(df_t['Freight'].sum() - p_in):,.0f}")
    f2.metric("Paisa Dena Hai (Market)", f"₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# --- 7. ADD LR (COMPLETE FORM) ---
elif menu == "Add LR":
    st.header("📝 Consignment Entry")
    v_type = st.radio("Trip Category", ["Own", "Hired"], horizontal=True)
    with st.form("add_lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d, pty = st.date_input("Date"), st.text_input("Billing Party*")
            cnor, cnee = st.text_input("Consignor"), st.text_input("Consignee")
        with c2:
            v_no, d_nm = st.text_input("Vehicle No*"), st.text_input("Driver Name")
            fl, tl = st.text_input("From"), st.text_input("To")
        with c3:
            fr, hc = st.number_input("Freight*"), st.number_input("Hired Chg")
            br, mat = st.text_input("Broker"), st.text_input("Material")
        if st.form_submit_button("🚀 SAVE LR"):
            if pty and v_no and fr > 0:
                lr_id = f"LR-{len(df_t)+1001}"
                prof = (fr - hc) if v_type == "Hired" else fr
                row = [str(d), lr_id, v_type, pty, cnor, "", "", cnee, "", "", mat, 0, v_no, d_nm, br, fl, tl, fr, hc, 0, 0, 0, 0, prof]
                if save_ws("trips", row): st.success(f"{lr_id} Saved!"); st.rerun()

# --- 8. LR MANAGER (EDIT/DELETE) ---
elif menu == "LR Manager":
    st.header("🔍 Edit / Delete Trips")
    sq = st.text_input("Search LR/Vehicle/Party")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"ed_f_{i}_{r['LR']}"):
                ec1, ec2, ec3 = st.columns(3)
                up, uv = ec1.text_input("Party", r['Party']), ec1.text_input("Vehicle", r['Vehicle'])
                ufl, utl = ec2.text_input("From", r['From']), ec2.text_input("To", r['To'])
                uf, uh = ec3.number_input("Freight", value=float(r['Freight'])), ec3.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("💾 UPDATE"):
                    upd = list(r.values); upd[3], upd[12], upd[15], upd[16], upd[17], upd[18] = up, uv, ufl, utl, uf, uh
                    upd[23] = (uf-uh) if r['Type']=="Hired" else (uf - (r['Diesel']+r['Toll']+r['DriverExp']+r['Other']))
                    if update_ws("trips", r['LR'], upd): st.success("Updated!"); st.rerun()
            if st.button(f"🗑️ Delete Record {r['LR']}", key=f"del_{i}"):
                if delete_ws("trips", r['LR']): st.warning("Deleted!"); st.rerun()

# --- 9. DRIVER MANAGEMENT ---
elif menu == "Driver Management":
    st.header("👨‍✈️ Driver Salary Dashboard")
    with st.form("d_form"):
        dn, dt = st.text_input("Driver Name"), st.date_input("Date")
        stts = st.selectbox("Status", ["Present", "Absent", "Leave"])
        adv, sal = st.number_input("Advance Paid"), st.number_input("Fixed Monthly Salary")
        if st.form_submit_button("Record Entry"):
            save_ws("drivers", [str(dt), dn, stts, adv, sal]); st.rerun()
    if not df_d.empty:
        ds = df_d.groupby("Name").agg({"Advance":"sum","Salary":"max","Status":lambda x:(x=="Present").sum()}).reset_index()
        ds["Earned"] = (ds["Salary"]/30)*ds["Status"]; ds["Balance"] = ds["Earned"] - ds["Advance"]
        st.dataframe(ds.style.format({"Salary":"₹{:.0f}","Advance":"₹{:.0f}","Earned":"₹{:.0f}","Balance":"₹{:.0f}"}))

# --- 10. LEDGERS ---
elif menu == "Party Ledger":
    sp = st.selectbox("Select Party", df_t["Party"].unique())
    p_tr = df_t[df_t["Party"]==sp]; p_pm = df_p[(df_p["Name"]==sp) & (df_p["Category"]=="Party")]
    bal = p_tr["Freight"].sum() - p_pm["Amount"].sum()
    st.subheader(f"Total Outstanding: ₹{bal:,.0f}")
    st.download_button("📥 Download PDF", gen_ledger_pdf(sp, p_tr, p_pm, bal, "Party"), f"{sp}_Ledger.pdf", key="p_p_pdf")
    st.write("### Trip History"); st.dataframe(p_tr[["Date","LR","Vehicle","From","To","Freight"]], use_container_width=True)
    st.write("### Payment History"); st.dataframe(p_pm[["Date","Amount","Mode"]], use_container_width=True)

elif menu == "Broker Ledger":
    h_df = df_t[df_t["Type"].astype(str).str.lower()=="hired"]
    sb = st.selectbox("Select Broker", h_df["Broker"].unique() if not h_df.empty else [])
    if sb:
        b_tr = h_df[h_df["Broker"]==sb]; b_pm = df_p[(df_p["Name"]==sb) & (df_p["Category"]=="Broker")]
        bal = b_tr["HiredCharges"].sum() - b_pm["Amount"].sum()
        st.download_button("📥 PDF", gen_ledger_pdf(sb, b_tr, b_pm, bal, "Broker"), f"{sb}_Broker.pdf", key="b_b_pdf")
        st.dataframe(b_tr[["Date","LR","Vehicle","HiredCharges"]], use_container_width=True)

# --- 11. MONTHLY BILL BUILDER ---
elif menu == "Monthly Bill Builder":
    st.header("📅 Selection Monthly Invoice")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        sp = st.selectbox("Party Name", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy()
        m_df.insert(0, "Select", True)
        ed = st.data_editor(m_df, hide_index=True)
        sel = ed[ed["Select"] == True]
        if not sel.empty: st.metric("Selected Bill Total", f"₹{sel['Freight'].sum():,.0f}")

# --- 12. P&L & TRANSACTIONS ---
elif menu == "P&L Statement":
    rev, hire, adm = df_t['Freight'].sum(), df_t['HiredCharges'].sum(), df_a['Amount'].sum()
    st.table(pd.DataFrame({"Particulars":["Revenue","Market Payouts","Admin Exp","NET PROFIT"],"Amount":[rev, hire, adm, (rev-hire-adm)]}))

elif menu == "Record Transaction":
    with st.form("t_f"):
        nm = st.selectbox("Name", list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist())))
        ct, am = st.selectbox("Type", ["Party", "Broker"]), st.number_input("Amount")
        if st.form_submit_button("Record Transaction"):
            save_ws("payments", [str(date.today()), nm, ct, am, "Bank/Cash"]); st.rerun()

elif menu == "Office Expense":
    with st.form("o_e"):
        am, rem = st.number_input("Amount"), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            save_ws("admin", [str(date.today()), "Other", am, rem]); st.rerun()

elif menu == "Vehicle Performance":
    own = df_t[df_t["Type"].astype(str).str.lower()=="own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR":"count","Freight":"sum","Profit":"sum"}).reset_index()
        st.dataframe(vr, use_container_width=True)
