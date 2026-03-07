import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONFIG & CLOUD SYNC ---
st.set_page_config(page_title="Virat Master ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_sh():
    info = json.loads(st.secrets["gcp_service_account"]["json_key"])
    creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open("Virat_Logistics_Data")

sh = get_sh()

def load(name): 
    try: return pd.DataFrame(sh.worksheet(name).get_all_records()).apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

def save(name, row): sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')

def update(lr, row):
    ws = sh.worksheet("trips"); cell = ws.find(str(lr))
    if cell: ws.update(f'A{cell.row}:X{cell.row}', [row], value_input_option='USER_ENTERED')

# --- 2. DATA PROCESSING ---
df_t, df_p, df_a, df_d = load("trips"), load("payments"), load("admin"), load("drivers")
for c in ["Freight","HiredCharges","Profit","Diesel","Toll","DriverExp"]:
    if c in df_t.columns: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
if not df_d.empty:
    for c in ["Advance","Salary"]: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').fillna(0)

# --- 3. PDF ENGINE ---
def gen_pdf(name, trips, pmts, bal, lbl):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"VIRAT LOGISTICS - {lbl} LEDGER", ln=1, align='C')
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(230,230,230)
    pdf.cell(30,10,"Date",1); pdf.cell(40,10,"LR",1); pdf.cell(60,10,"Detail",1); pdf.cell(30,10,"Debit",1); pdf.cell(30,10,"Credit",1,1)
    pdf.set_font("Arial", '', 9)
    for _, r in trips.iterrows():
        a = r['Freight'] if lbl=="Party" else r['HiredCharges']
        pdf.cell(30,8,str(r['Date']),1); pdf.cell(40,8,str(r['LR']),1); pdf.cell(60,8,str(r['Vehicle']),1); pdf.cell(30,8,str(a) if lbl=="Party" else "0",1); pdf.cell(30,8,"0" if lbl=="Party" else str(a),1,1)
    for _, p in pmts.iterrows():
        pdf.cell(30,8,str(p['Date']),1); pdf.cell(40,8,"PYMT",1); pdf.cell(60,8,p['Mode'],1); pdf.cell(30,8,"0" if lbl=="Party" else str(p['Amount']),1); pdf.cell(30,8,str(p['Amount']) if lbl=="Party" else "0",1,1)
    pdf.cell(130,10,"BALANCE DUE",1); pdf.cell(60,10,f"Rs. {bal}",1,1,'C')
    return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTH & NAV ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    with st.sidebar:
        if st.text_input("User") == "admin" and st.text_input("Pass", type="password") == "1234":
            if st.button("Login"): st.session_state.login = True; st.rerun()
    st.warning("Sidebar se Login karein"); st.stop()

menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard","Add LR","LR Manager","Monthly Bill","P&L Report","Vehicle Profit","Driver Salary","Party Ledger","Broker Ledger","Entry"])

# --- 5. FEATURES ---
if menu == "Dashboard":
    p_in, b_out, adm = df_p[df_p["Category"]=="Party"]["Amount"].sum(), df_p[df_p["Category"]=="Broker"]["Amount"].sum(), df_a["Amount"].sum()
    st.title("📊 Financial Summary")
    c1,c2,c3 = st.columns(3); c1.metric("Cash In (Collected)",f"₹{p_in:,.0f}"); c2.metric("Cash Out (Expenses)",f"₹{(b_out+adm):,.0f}"); c3.metric("Net Cashflow",f"₹{(p_in-b_out-adm):,.0f}")
    st.divider(); f1,f2 = st.columns(2); f1.metric("Receivables (Lena Hai)",f"₹{(df_t['Freight'].sum()-p_in):,.0f}"); f2.metric("Payables (Dena Hai)",f"₹{(df_t['HiredCharges'].sum()-b_out):,.0f}")

elif menu == "Add LR":
    st.header("📝 Consignment Entry")
    v_t = st.radio("Vehicle", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("lr_f", clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        with c1: d, pty, cnor = st.date_input("Date"), st.text_input("Party*"), st.text_input("Consignor")
        with c2: v_n, fl, tl = st.text_input("Vehicle No*"), st.text_input("From"), st.text_input("To")
        with c3: fr = st.number_input("Freight*"); mat = st.text_input("Material")
            if v_t == "Market Hired": br, hc, dsl, tll, de = st.text_input("Broker"), st.number_input("Hired Chg"), 0, 0, 0
            else: br, hc, dsl, tll, de = "", 0, st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Exp")
        if st.form_submit_button("Save"):
            pf = (fr-hc) if v_t=="Market Hired" else (fr-(dsl+tll+de))
            row = [str(d), f"LR-{len(df_t)+1001}", v_t, pty, cnor, "", "", "", "", "", mat, 0, v_n, "Driver", br, fl, tl, fr, hc, dsl, de, tll, 0, pf]
            save("trips", row); st.success("Saved!"); st.rerun()

elif menu == "LR Manager":
    sq = st.text_input("Search")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"📄 {r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"ed_{i}"):
                up, uv, uf, uh = st.text_input("Party", r['Party']), st.text_input("Vehicle", r['Vehicle']), st.number_input("Freight", value=float(r['Freight'])), st.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("Update"):
                    upd = list(r.values); upd[3], upd[12], upd[17], upd[18] = up, uv, uf, uh
                    update(r['LR'], upd); st.success("OK"); st.rerun()
            if st.button("Delete", key=f"del_{i}"): sh.worksheet("trips").delete_rows(sh.worksheet("trips").find(str(r['LR'])).row); st.rerun()

elif menu == "Monthly Bill":
    st.header("📅 Selection Bill")
    if not df_t.empty:
        sp = st.selectbox("Party", df_t["Party"].unique())
        m_df = df_t[df_t['Party'] == sp].copy(); m_df.insert(0, "Select", True)
        ed = st.data_editor(m_df, hide_index=True); sel = ed[ed["Select"] == True]
        if not sel.empty: st.metric("Total Bill", f"₹{sel['Freight'].sum():,.0f}")

elif menu == "P&L Report":
    st.header("📉 Profit & Loss")
    r, h, a = df_t['Freight'].sum(), df_t['HiredCharges'].sum(), df_a['Amount'].sum()
    dsl = df_t['Diesel'].sum() + df_t['Toll'].sum() + df_t['DriverExp'].sum()
    st.columns(3)[0].metric("Revenue", f"₹{r:,.0f}"); st.columns(3)[1].metric("Direct Costs", f"₹{(h+dsl):,.0f}"); st.columns(3)[2].metric("NET PROFIT", f"₹{(r-h-dsl-a):,.0f}")
    st.table(pd.DataFrame({"Head": ["Revenue", "Hired Payouts", "Fleet Maintenance", "Admin Expense"], "Amt": [r, h, dsl, a]}))

elif menu == "Vehicle Profit":
    v_r = df_t[df_t["Vehicle"] != ""].groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index()
    st.dataframe(v_r, use_container_width=True); st.bar_chart(v_r.set_index("Vehicle")["Profit"])

elif menu == "Driver Salary":
    with st.form("d_f"):
        dn, dt, sl, ad = st.text_input("Driver"), st.date_input("Date"), st.number_input("Salary"), st.number_input("Advance")
        if st.form_submit_button("Record"): save("drivers", [str(dt), dn, "Present", ad, sl]); st.rerun()
    if not df_d.empty:
        ds = df_d.groupby("Name").agg({"Advance": "sum", "Salary": "max", "Date": "count"}).reset_index()
        ds["Earned"] = (ds["Salary"]/30)*ds["Date"]; ds["Balance"] = ds["Earned"] - ds["Advance"]
        st.dataframe(ds.rename(columns={"Date":"PresentDays"}), use_container_width=True)

elif menu == "Party Ledger" or menu == "Broker Ledger":
    cat = "Party" if "Party" in menu else "Broker"
    lbl = "HiredCharges" if cat=="Broker" else "Freight"
    df_f = df_t[df_t["Type"].str.lower()=="hired"] if cat=="Broker" else df_t
    sp = st.selectbox("Select", df_f[cat].unique())
    p_t = df_f[df_f[cat]==sp]; p_p = df_p[(df_p["Name"]==sp) & (df_p["Category"]==cat)]
    bl = p_t[lbl].sum() - p_p["Amount"].sum()
    st.subheader(f"Balance: ₹{bl:,.0f}")
    st.download_button("📥 PDF", gen_pdf(sp, p_t, p_p, bl, cat), f"{sp}.pdf")
    st.write("Trips:"); st.dataframe(p_t[["Date","LR","Vehicle",lbl]])
    st.write("Payments:"); st.dataframe(p_p[["Date","Amount","Mode"]])

elif menu == "Entry":
    with st.form("e"):
        nm, ct, am = st.text_input("Name"), st.selectbox("Cat", ["Party", "Broker"]), st.number_input("Amt")
        if st.form_submit_button("Save"): save("payments", [str(date.today()), nm, ct, am, "Cash"]); st.rerun()
