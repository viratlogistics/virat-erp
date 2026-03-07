import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. SETTINGS & CONNECTION ---
st.set_page_config(page_title="Virat Logistics Master ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_client():
    info = json.loads(st.secrets["gcp_service_account"]["json_key"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(info, scopes=scope))

client = get_client()
SHEET_NAME = "Virat_Logistics_Data"
sh = client.open(SHEET_NAME)

# --- 2. DATA UTILITIES ---
def load_ws(name):
    try:
        df = pd.DataFrame(sh.worksheet(name).get_all_records())
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save_ws(name, row): sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')

def update_ws(name, lr, row):
    ws = sh.worksheet(name); cell = ws.find(str(lr))
    if cell: ws.update(f'A{cell.row}:X{cell.row}', [row], value_input_option='USER_ENTERED')

def delete_ws(name, lr):
    ws = sh.worksheet(name); cell = ws.find(str(lr))
    if cell: ws.delete_rows(cell.row)

# --- 3. DATA LOADING & NUMERIC ---
df_t = load_ws("trips")
df_p = load_ws("payments")
df_a = load_ws("admin")
df_d = load_ws("drivers")

for c in ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp"]:
    if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
if not df_d.empty:
    for c in ["Advance", "Salary"]: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').fillna(0)

# --- 4. PDF GENERATOR ---
def gen_pdf(name, trips, pmts, bal, lbl):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"VIRAT LOGISTICS - {lbl} LEDGER: {name}", ln=1, align='C')
    pdf.ln(5); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(230,230,230)
    pdf.cell(30, 10, "Date", 1, 0, 'C', 1); pdf.cell(40, 10, "Ref", 1, 0, 'C', 1); pdf.cell(60, 10, "Detail", 1, 0, 'C', 1); pdf.cell(30, 10, "Debit", 1, 0, 'C', 1); pdf.cell(30, 10, "Credit", 1, 1, 'C', 1)
    pdf.set_font("Arial", '', 8)
    for _, r in trips.iterrows():
        amt = r['Freight'] if lbl == "Party" else r['HiredCharges']
        pdf.cell(30, 8, str(r['Date']), 1); pdf.cell(40, 8, str(r['LR']), 1); pdf.cell(60, 8, f"{r['Vehicle']}", 1)
        pdf.cell(30, 8, f"{amt}" if lbl=="Party" else "0", 1); pdf.cell(30, 8, "0" if lbl=="Party" else f"{amt}", 1, 1)
    for _, p in pmts.iterrows():
        pdf.cell(30, 8, str(p['Date']), 1); pdf.cell(40, 8, "PYMT", 1); pdf.cell(60, 8, p['Mode'], 1)
        pdf.cell(30, 8, "0" if lbl=="Party" else f"{p['Amount']}", 1); pdf.cell(30, 8, f"{p['Amount']}" if lbl=="Party" else "0", 1, 1)
    pdf.set_font("Arial", 'B', 10); pdf.cell(130, 10, "BALANCE DUE", 1, 0, 'R', 1); pdf.cell(60, 10, f"Rs. {bal:,.2f}", 1, 1, 'C', 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTH & NAVIGATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    u, p = st.sidebar.text_input("User"), st.sidebar.text_input("Pass", type="password")
    if st.sidebar.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

menu = st.sidebar.selectbox("MENU", ["Dashboard", "Add LR", "LR Manager", "Monthly Bill", "Party Ledger", "Broker Ledger", "Driver Management", "Vehicle Profit", "P&L Statement", "Record Payment", "Office Expense"])

# --- 6. DASHBOARD (CASH & FUND FLOW) ---
if menu == "Dashboard":
    p_in = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_out = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    adm = df_a["Amount"].sum()
    st.title("📊 Cash & Fund Flow Dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Collected", f"₹{p_in:,.0f}")
    c2.metric("Cash Paid", f"₹{(b_out+adm):,.0f}")
    c3.metric("Net Cashflow", f"₹{(p_in - b_out - adm):,.0f}")
    st.divider(); f1, f2 = st.columns(2)
    f1.metric("Receivables ( लेना है )", f"₹{(df_t['Freight'].sum() - p_in):,.0f}")
    f2.metric("Payables ( देना है )", f"₹{(df_t['HiredCharges'].sum() - b_out):,.0f}")

# --- 7. ADD LR ---
elif menu == "Add LR":
    st.header("📝 Create New Consignment")
    v_type = st.radio("Type", ["Own", "Hired"], horizontal=True)
    with st.form("a_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: d, party = st.date_input("Date"), st.text_input("Party*")
        with c2: v_no, fl, tl = st.text_input("Vehicle No*"), st.text_input("From"), st.text_input("To")
        with c3: fr, h_c, br = st.number_input("Freight*"), st.number_input("Hired Chg"), st.text_input("Broker")
        if st.form_submit_button("Save"):
            prof = (fr - h_c) if v_type == "Hired" else fr
            row = [str(d), f"LR-{len(df_t)+1001}", v_type, party, "", "", "", "", "", "", "", 0, v_no, "Driver", br, fl, tl, fr, h_c, 0, 0, 0, 0, prof]
            save_ws("trips", row); st.success("Saved!"); st.rerun()

# --- 8. LR MANAGER (EDIT/DEL/PRINT) ---
elif menu == "LR Manager":
    sq = st.text_input("Search LR/Vehicle")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"{r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"ed_{i}"):
                up, uv = st.text_input("Party", r['Party']), st.text_input("Vehicle", r['Vehicle'])
                uf, uh = st.number_input("Freight", value=float(r['Freight'])), st.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("Update"):
                    upd = list(r.values); upd[3], upd[12], upd[17], upd[18] = up, uv, uf, uh
                    update_ws("trips", r['LR'], upd); st.success("Updated!"); st.rerun()
            if st.button(f"🗑️ Delete {r['LR']}", key=f"del_{i}"):
                delete_ws("trips", r['LR']); st.warning("Deleted!"); st.rerun()

# --- 9. MONTHLY BILL (SELECTION) ---
elif menu == "Monthly Bill":
    sp = st.selectbox("Party", df_t["Party"].unique())
    m_df = df_t[df_t['Party'] == sp].copy()
    m_df.insert(0, "Select", True)
    ed = st.data_editor(m_df, hide_index=True)
    sel = ed[ed["Select"] == True]
    if not sel.empty: st.metric("Total Selected", f"₹{sel['Freight'].sum():,.0f}")

# --- 10. DRIVER MANAGEMENT (ADVANCE & SALARY) ---
elif menu == "Driver Management":
    st.header("👨‍✈️ Driver Dashboard")
    with st.form("d_f"):
        dn, stts = st.text_input("Driver Name"), st.selectbox("Status", ["Present", "Absent", "Leave"])
        adv, sal = st.number_input("Advance"), st.number_input("Salary")
        if st.form_submit_button("Record"):
            save_ws("drivers", [str(date.today()), dn, stts, adv, sal]); st.rerun()
    if not df_d.empty:
        ds = df_d.groupby("Name").agg({"Advance":"sum","Salary":"max","Status":lambda x:(x=="Present").sum()}).reset_index()
        ds["Earned"] = (ds["Salary"]/30)*ds["Status"]; ds["Balance"] = ds["Earned"] - ds["Advance"]
        st.dataframe(ds.style.format({"Salary":"₹{:.0f}","Advance":"₹{:.0f}","Earned":"₹{:.0f}","Balance":"₹{:.0f}"}))

# --- 11. LEDGERS ---
elif menu == "Party Ledger":
    sp = st.selectbox("Party", df_t["Party"].unique())
    p_t = df_t[df_t["Party"]==sp]; p_p = df_p[(df_p["Name"]==sp) & (df_p["Category"]=="Party")]
    bl = p_t["Freight"].sum() - p_p["Amount"].sum()
    st.download_button("📥 Download PDF", gen_pdf(sp, p_t, p_p, bl, "Party"), f"{sp}.pdf")
    st.write("### Trip Wise Details"); st.dataframe(p_t[["Date", "LR", "Vehicle", "Freight"]])
    st.write("### Payment History"); st.dataframe(p_p[["Date", "Amount", "Mode"]])

elif menu == "Broker Ledger":
    h_df = df_t[df_t["Type"].astype(str).str.lower()=="hired"]
    sb = st.selectbox("Broker", h_df["Broker"].unique() if not h_df.empty else [])
    if sb:
        b_t = h_df[h_df["Broker"]==sb]; b_p = df_p[(df_p["Name"]==sb) & (df_p["Category"]=="Broker")]
        bl = b_t["HiredCharges"].sum() - b_p["Amount"].sum()
        st.download_button("📥 PDF", gen_pdf(sb, b_t, b_p, bl, "Broker"), f"{sb}.pdf")
        st.dataframe(b_t[["Date", "LR", "Vehicle", "HiredCharges"]])

# --- 12. P&L & TRANSACTIONS ---
elif menu == "P&L Statement":
    r, h, a = df_t['Freight'].sum(), df_t['HiredCharges'].sum(), df_a['Amount'].sum()
    st.table({"Particulars":["Revenue","Market Payouts","Admin Exp","NET PROFIT"],"Amount":[r, h, a, (r-h-a)]})

elif menu == "Record Payment":
    with st.form("tr"):
        nm = st.selectbox("Name", list(set(df_t["Party"].unique().tolist() + df_t["Broker"].unique().tolist())))
        ct, am = st.selectbox("Type", ["Party", "Broker"]), st.number_input("Amount")
        if st.form_submit_button("Save"):
            save_ws("payments", [str(date.today()), nm, ct, am, "Cash"]); st.rerun()

elif menu == "Office Expense":
    with st.form("oe"):
        am, rem = st.number_input("Amount"), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            save_ws("admin", [str(date.today()), "Other", am, rem]); st.rerun()

elif menu == "Vehicle Profit":
    own = df_t[df_t["Type"].astype(str).str.lower()=="own"]
    if not own.empty:
        vr = own.groupby("Vehicle").agg({"LR":"count","Freight":"sum","Profit":"sum"}).reset_index()
        st.dataframe(vr)
