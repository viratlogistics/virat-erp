import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. CONFIGURATION & CLOUD CONNECTION ---
st.set_page_config(page_title="Virat Logistics Master ERP", layout="wide", page_icon="🚚")

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

sh = None
if client:
    try: sh = client.open(SHEET_NAME)
    except: st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili."); st.stop()

# --- 2. DATA UTILITIES (LEAK-PROOF & CLEAN) ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # Cleaning: Remove spaces that break ledger matching
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

def save_ws(ws_name, row_list):
    try:
        ws = sh.worksheet(ws_name)
        ws.append_row(row_list, value_input_option='USER_ENTERED')
        return True
    except: return False

def update_ws(ws_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(ws_name)
        # Better Search: Exact match for LR No
        cell = ws.find(str(lr_no))
        if cell:
            # Update specific row with new data
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row], value_input_option='USER_ENTERED')
            return True
        return False
    except Exception as e:
        st.error(f"Update Error: {e}")
        return False

def delete_ws(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row)
            return True
        return False
    except: return False

# --- 3. DATA REFRESH & NUMERIC CONVERSION ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")

    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    
    num_t = ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp", "Other"]
    for c in num_t: df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    
    if not df_p.empty:
        df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    else: df_p = pd.DataFrame(columns=cols_p)

    if not df_a.empty:
        df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
    else: df_a = pd.DataFrame(columns=cols_a)
else: st.stop()

# --- 4. LOGIN ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP - Admin Login")
    with st.form("Login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Access"):
            if u == "admin" and p == "1234":
                st.session_state.login = True; st.rerun()
            else: st.error("Wrong Login")
    st.stop()

# --- 5. NAVIGATION ---
menu = st.sidebar.selectbox("Main Menu", 
    ["Dashboard", "Add LR", "LR Manager (Edit/Del)", "Monthly Bill", 
     "Party Ledger", "Broker Ledger", "Vehicle Performance", "Party Receipt", 
     "Broker Payment", "Admin Expense"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    t_rev = df_t["Freight"].sum()
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_work = df_t["HiredCharges"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Trip Profit", f"₹{df_t['Profit'].sum():,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Payable", f"₹{(b_work - b_paid):,.0f}")
    st.divider()
    st.metric("Total Admin Expense", f"₹{df_a['Amount'].sum():,.0f}")

# --- ADD LR ---
elif menu == "Add LR":
    st.header("📝 Create LR")
    v_type = st.radio("Vehicle Type", ["Own Fleet", "Market Hired"], horizontal=True)
    with st.form("add_lr", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("Date", date.today())
            lr_id = f"LR-{len(df_t)+1001}"
            party = st.text_input("Party Name*")
            cnm, cgst = st.text_input("Consignor"), st.text_input("Consignor GST")
            cadd = st.text_area("Consignor Address")
        with f2:
            eenm, eegst = st.text_input("Consignee"), st.text_input("Consignee GST")
            eeadd = st.text_area("Consignee Address")
            v_no = st.text_input("Vehicle No*")
            floc, tloc = st.text_input("From"), st.text_input("To")
        with f3:
            mat, wt = st.text_input("Material"), st.number_input("Weight (MT)", 0.0)
            fr = st.number_input("Freight Amount*", 0.0)
            br = st.text_input("Broker/Market Name", disabled=(v_type=="Own Fleet"))
            if v_type == "Market Hired":
                h_chg = st.number_input("Hired Charges")
                dsl, de, tl, ot = 0, 0, 0, 0
            else:
                h_chg = 0
                dsl, de, tl, ot = st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save Trip"):
            if party and v_no and fr > 0:
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                calc_prof = (fr - h_chg) if t_val == "Hired" else (fr - (dsl+de+tl+ot))
                row = [str(d), lr_id, t_val, party, cnm, cgst, cadd, eenm, eegst, eeadd, mat, wt, v_no, "Driver", br, floc, tloc, fr, h_chg, dsl, de, tl, ot, calc_prof]
                if save_ws("trips", row): st.success("Saved Successfully!"); st.rerun()

# --- LR MANAGER (ACTUAL UPDATE FIX) ---
elif menu == "LR Manager (Edit/Del)":
    st.header("🔍 Edit or Delete Trip Records")
    if not df_t.empty:
        search_q = st.text_input("Search (LR / Vehicle / Party)")
        f_df = df_t[df_t.apply(lambda r: search_q.lower() in str(r).lower(), axis=1)]
        
        for idx, row in f_df.iterrows():
            with st.expander(f"Trip: {row['LR']} | {row['Vehicle']} | {row['Party']}"):
                with st.form(key=f"edit_form_{idx}_{row['LR']}"):
                    st.write("### Full Trip Edit")
                    e1, e2, e3 = st.columns(3)
                    u_date = e1.text_input("Date", str(row['Date']))
                    u_party = e1.text_input("Party", str(row['Party']))
                    u_cnm = e1.text_input("Consignor", str(row['Consignor']))
                    u_cgst = e1.text_input("Consignor GST", str(row['Consignor_GST']))
                    u_cadd = e1.text_area("Consignor Address", str(row['Consignor_Add']))
                    
                    u_eenm = e2.text_input("Consignee", str(row['Consignee']))
                    u_eegst = e2.text_input("Consignee GST", str(row['Consignee_GST']))
                    u_eeadd = e2.text_area("Consignee Address", str(row['Consignee_Add']))
                    u_vno = e2.text_input("Vehicle No", str(row['Vehicle']))
                    u_from = e2.text_input("From", str(row['From']))
                    u_to = e2.text_input("To", str(row['To']))
                    
                    u_mat = e3.text_input("Material", str(row['Material']))
                    u_wt = e3.number_input("Weight", value=float(row['Weight']))
                    u_fr = e3.number_input("Freight", value=float(row['Freight']))
                    u_hchg = e3.number_input("Hired Charges", value=float(row['HiredCharges']))
                    u_br = e3.text_input("Broker Name", str(row['Broker']))
                    u_dsl = e3.number_input("Diesel", value=float(row['Diesel']))
                    u_toll = e3.number_input("Toll", value=float(row['Toll']))

                    if st.form_submit_button("✅ Update This Record"):
                        # Recalculate Profit based on updated values
                        u_prof = (u_fr - u_hchg) if row['Type'] == "Hired" else (u_fr - (u_dsl + float(row['DriverExp']) + u_toll + float(row['Other'])))
                        
                        # Prepare the full 24-column row list
                        up_list = [
                            u_date, row['LR'], row['Type'], u_party, u_cnm, u_cgst, u_cadd,
                            u_eenm, u_eegst, u_eeadd, u_mat, u_wt, u_vno, row['Driver'],
                            u_br, u_from, u_to, u_fr, u_hchg, u_dsl, row['DriverExp'],
                            u_toll, row['Other'], u_prof
                        ]
                        
                        if update_ws("trips", row['LR'], up_list):
                            st.success(f"LR {row['LR']} Updated in Google Sheets!"); st.rerun()
                        else:
                            st.error("Sheet update failed. Check connection.")

                if st.button(f"🗑️ Delete Record {row['LR']}", key=f"del_btn_{idx}"):
                    if delete_ws("trips", row['LR']):
                        st.warning("Deleted!"); st.rerun()

# --- MONTHLY BILL ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Party Bill")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'], errors='coerce')
        sp = st.selectbox("Select Party", df_t["Party"].unique())
        m_list = df_t[df_t['Date'].notna()]['Date'].dt.strftime('%B %Y').unique()
        if len(m_list) > 0:
            sm = st.selectbox("Select Month", m_list)
            m_df = df_t[(df_t['Party'] == sp) & (df_t['Date'].dt.strftime('%B %Y') == sm)]
            st.dataframe(m_df[["Date", "LR", "Vehicle", "From", "To", "Freight"]], use_container_width=True)
            st.metric("Total Bill Amount", f"₹{m_df['Freight'].sum():,.0f}")

# --- LEDGERS ---
elif menu == "Party Ledger":
    st.header("🏢 Party Outstanding Ledger")
    if not df_t.empty:
        b = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total_Bill"})
        r = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Paid"})
        l = pd.merge(b, r, on="Name", how="left").fillna(0)
        l["Balance"] = l["Total_Bill"] - l["Total_Paid"]
        st.table(l.style.format({"Total_Bill": "₹{:.0f}", "Total_Paid": "₹{:.0f}", "Balance": "₹{:.0f}"}))

elif menu == "Broker Ledger":
    st.header("🤝 Broker Market Account")
    h_df = df_t[df_t["Type"].astype(str).str.strip().str.lower() == "hired"]
    if not h_df.empty:
        w = h_df.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total_Work"})
        p = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Paid"})
        bl = pd.merge(w, p, on="Name", how="left").fillna(0)
        bl["Outstanding"] = bl["Total_Work"] - bl["Total_Paid"]
        st.table(bl.style.format({"Total_Work": "₹{:.0f}", "Total_Paid": "₹{:.0f}", "Outstanding": "₹{:.0f}"}))

# --- VEHICLE PERFORMANCE (OWN ONLY) ---
elif menu == "Vehicle Performance":
    st.header("🚛 Own Vehicle Performance Report")
    own_fleet = df_t[df_t["Type"].astype(str).str.lower() == "own"]
    if not own_fleet.empty:
        vr = own_fleet.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index().rename(columns={"LR": "Trips", "Freight": "Revenue"})
        st.dataframe(vr.style.format({"Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])

# --- TRANSACTIONS ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if "Party" in menu else "Broker"
    st.header(f"💰 {cat} Entry")
    with st.form(f"pay_form_{cat}"):
        nms = df_t[cat].unique() if not df_t.empty else []
        snm = st.selectbox("Select Name", nms)
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Bank", "Cash", "Cheque"])
        if st.form_submit_button("Record"):
            if save_ws("payments", [str(date.today()), snm, cat, am, md]): st.success("Recorded!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Office Admin Expense")
    with st.form("exp_form"):
        ec = st.selectbox("Category", ["Rent", "Salary", "Stationary", "Electricity", "Other"])
        ea = st.number_input("Amount", 0.0); er = st.text_input("Remarks")
        if st.form_submit_button("Save"):
            if save_ws("admin", [str(date.today()), ec, ea, er]): st.success("Saved!"); st.rerun()
