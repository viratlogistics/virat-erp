import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide", page_icon="🚚")

@st.cache_resource
def get_client():
    info = json.loads(st.secrets["gcp_service_account"]["json_key"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(info, scopes=scope))

client = get_client()
sh = client.open("Virat_Logistics_Data")

# --- 2. CORE UTILITIES ---
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

# Load Data
df_t = load_ws("trips"); df_p = load_ws("payments"); df_a = load_ws("admin"); df_d = load_ws("drivers")

# --- 3. NAVIGATION ---
menu = st.sidebar.selectbox("🚀 MENU", ["Dashboard", "Add LR", "LR Manager", "Driver Salary", "Party Ledger", "Broker Ledger", "P&L Statement", "Payment Entry"])

# --- 4. DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Virat Logistics Dashboard")
    rev = df_t["Freight"].apply(pd.to_numeric, errors='coerce').sum()
    hire = df_t["HiredCharges"].apply(pd.to_numeric, errors='coerce').sum()
    st.columns(3)[0].metric("Total Revenue", f"₹{rev:,.0f}")
    st.columns(3)[1].metric("Market Payables", f"₹{hire:,.0f}")
    st.columns(3)[2].metric("Gross Profit", f"₹{(rev-hire):,.0f}")

# --- 5. ADD LR (FULL DETAILS) ---
elif menu == "Add LR":
    st.header("📝 Create New Consignment (LR)")
    v_type = st.radio("Trip Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: 
            d, party = st.date_input("Date"), st.text_input("Billing Party*")
            cnor, cnee = st.text_input("Consignor Name"), st.text_input("Consignee Name")
        with c2:
            v_no, driver = st.text_input("Vehicle No*"), st.text_input("Driver Name")
            fl, tl = st.text_input("From"), st.text_input("To")
        with c3:
            fr, h_c = st.number_input("Freight (Party)"), st.number_input("Hired Charges (Broker)")
            br, mat = st.text_input("Broker Name"), st.text_input("Material Details")
        
        if st.form_submit_button("Save Trip"):
            lr_no = f"LR-{len(df_t)+1001}"
            prof = (fr - h_c) if v_type == "Hired" else fr
            # Matching all 24 columns of your sheet
            row = [str(d), lr_no, v_type, party, cnor, "", "", cnee, "", "", mat, 0, v_no, driver, br, fl, tl, fr, h_c, 0, 0, 0, 0, prof]
# --- 6. LR MANAGER (EDIT/DELETE) ---
elif menu == "LR Manager":
    st.header("🔍 Edit or Delete Trips")
    sq = st.text_input("Search LR/Vehicle")
    f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
    for i, r in f_df.iterrows():
        with st.expander(f"{r['LR']} | {r['Vehicle']} | {r['Party']}"):
            with st.form(key=f"ed_{i}"):
                up, uf = st.text_input("Party", r['Party']), st.number_input("Freight", value=float(r['Freight']))
                uv, uh = st.text_input("Vehicle", r['Vehicle']), st.number_input("Hired", value=float(r['HiredCharges']))
                if st.form_submit_button("Update"):
                    upd = list(r.values); upd[3], upd[17], upd[12], upd[18] = up, uf, uv, uh
                    update_ws("trips", r['LR'], upd); st.success("Updated!"); st.rerun()
            if st.button(f"🗑️ Delete {r['LR']}", key=f"del_{i}"):
                delete_ws("trips", r['LR']); st.warning("Deleted!"); st.rerun()

# --- 7. DRIVER SALARY ---
elif menu == "Driver Salary":
    st.header("👨‍✈️ Driver Accounts")
    with st.form("d_f"):
        dn, dt = st.text_input("Driver Name"), st.date_input("Date")
        adv, sal = st.number_input("Advance"), st.number_input("Salary")
        if st.form_submit_button("Save"):
            save_ws("drivers", [str(dt), dn, "Present", adv, sal]); st.rerun()
    if not df_d.empty:
        ds = df_d.groupby("Name").agg({"Advance":"sum","Salary":"max"}).reset_index()
        ds["Balance"] = ds["Salary"] - ds["Advance"]
        st.dataframe(ds)

# --- 8. LEDGERS ---
elif menu == "Party Ledger":
    sp = st.selectbox("Select Party", df_t["Party"].unique())
    p_t = df_t[df_t["Party"]==sp]; p_p = df_p[(df_p["Name"]==sp) & (df_p["Category"]=="Party")]
    st.write(f"### Outstanding: ₹{p_t['Freight'].sum() - p_p['Amount'].sum()}")
    st.dataframe(p_t[["Date", "LR", "Vehicle", "Freight"]])

elif menu == "Broker Ledger":
    sb = st.selectbox("Select Broker", df_t["Broker"].unique())
    b_t = df_t[df_t["Broker"]==sb]; b_p = df_p[(df_p["Name"]==sb) & (df_p["Category"]=="Broker")]
    st.write(f"### Payable: ₹{b_t['HiredCharges'].sum() - b_p['Amount'].sum()}")
    st.dataframe(b_t[["Date", "LR", "Vehicle", "HiredCharges"]])

# --- 9. PAYMENT & EXPENSE ---
elif menu == "Payment Entry":
    with st.form("pay"):
        nm = st.text_input("Name"); ct = st.selectbox("Type", ["Party", "Broker"]); am = st.number_input("Amount")
        if st.form_submit_button("Save"):
            save_ws("payments", [str(date.today()), nm, ct, am, "Cash"]); st.rerun()

elif menu == "P&L Statement":
    r, h = df_t['Freight'].sum(), df_t['HiredCharges'].sum()
    st.table({"Desc":["Revenue","Payouts","Net Profit"],"Amt":[r, h, (r-h)]})
            
            
            
            
            
            
            
            save_ws("trips", row); st.success(f"Saved {lr_no}!"); st.rerun()
