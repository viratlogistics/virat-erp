import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# --- 1. SETTINGS & GOOGLE SHEETS CONNECTION ---
st.set_page_config(page_title="Virat Logistics Master ERP", layout="wide", page_icon="🚚")

def get_gspread_client():
    try:
        # Streamlit Secrets se JSON key uthana
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

sh = None
if client:
    try:
        sh = client.open(SHEET_NAME)
    except Exception:
        st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili. Check sharing with service email.")
        st.stop()

# --- 2. DATA UTILITIES (LOAD, SAVE, UPDATE, DELETE) ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        df = pd.DataFrame(ws.get_all_records())
        # Cleaning: Text se extra spaces hatana
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except:
        return pd.DataFrame()

def save_ws(ws_name, row_list):
    try:
        ws = sh.worksheet(ws_name)
        ws.append_row(row_list, value_input_option='USER_ENTERED')
        return True
    except: return False

def update_ws(ws_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row])
            return True
        return False
    except: return False

def delete_ws(ws_name, lr_no):
    try:
        ws = sh.worksheet(ws_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row)
            return True
        return False
    except: return False

# --- 3. DATA LOADING & NUMERIC CONVERSION ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")

    # Column Validation & Numeric Fix
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
else:
    st.stop()

# --- 4. PROFESSIONAL PDF ENGINE ---
def create_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 22); pdf.set_text_color(180, 0, 0)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 5, "Reliable Transport Solutions", ln=True, align='C')
    pdf.ln(10)
    
    # Header Info
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(95, 10, f" LR NO: {row['LR']}", 1, 0, 'L', True)
    pdf.cell(95, 10, f" DATE: {row['Date']}", 1, 1, 'L', True)
    
    # Party Info
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 8, " CONSIGNOR (SENDER)", 1, 0, 'L', True)
    pdf.cell(95, 8, " CONSIGNEE (RECEIVER)", 1, 1, 'L', True)
    pdf.set_font("Arial", '', 9)
    y_before = pdf.get_y()
    pdf.multi_cell(95, 6, f" {row['Consignor']}\n GST: {row['Consignor_GST']}\n Add: {row['Consignor_Add'][:50]}", 1)
    pdf.set_y(y_before); pdf.set_x(105)
    pdf.multi_cell(95, 6, f" {row['Consignee']}\n GST: {row['Consignee_GST']}\n Add: {row['Consignee_Add'][:50]}", 1)
    
    # Trip Info
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    headers = [("VEHICLE", 40), ("MATERIAL", 60), ("FROM", 45), ("TO", 45)]
    for txt, w in headers: pdf.cell(w, 10, txt, 1, 0, 'C', True)
    pdf.ln()
    pdf.set_font("Arial", '', 10)
    pdf.cell(40, 10, str(row['Vehicle']), 1, 0, 'C')
    pdf.cell(60, 10, str(row['Material']), 1, 0, 'C')
    pdf.cell(45, 10, str(row['From']), 1, 0, 'C')
    pdf.cell(45, 10, str(row['To']), 1, 1, 'C')
    
    # Freight
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(145, 12, "TOTAL FREIGHT AMOUNT ", 0, 0, 'R')
    pdf.cell(45, 12, f"Rs. {row['Freight']:,}/-", 1, 1, 'C', True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 5. LOGIN SYSTEM ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP - Authorized Access")
    with st.container():
        u = st.text_input("Admin Username")
        p = st.text_input("Security Password", type="password")
        if st.button("Enter Dashboard"):
            if u == "admin" and p == "1234":
                st.session_state.login = True
                st.rerun()
            else: st.error("Access Denied")
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("🚀 NAVIGATION", 
    ["📊 Dashboard", "➕ Create New LR", "🔍 LR Manager (Edit/Del)", "📅 Monthly Billing", 
     "🏢 Party Ledger", "🤝 Broker Ledger", "🚛 Vehicle Profit", "💰 Party Payment", 
     "💸 Broker Payout", "🏢 Office Expense"])

# --- 7. FEATURE: DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Financial Operations Control")
    
    # Calculations
    total_rev = df_t["Freight"].sum()
    party_paid = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    broker_work = df_t["HiredCharges"].sum()
    broker_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    trip_profit = df_t["Profit"].sum()
    office_exp = df_a["Amount"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gross Profit", f"₹{trip_profit:,.0f}")
    col2.metric("Party Receivables", f"₹{(total_rev - party_paid):,.0f}", delta_color="inverse")
    col3.metric("Broker Payables", f"₹{(broker_work - broker_paid):,.0f}")
    col4.metric("Net Cashflow", f"₹{(party_paid - broker_paid - office_exp):,.0f}")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Monthly Revenue Trend")
        if not df_t.empty:
            df_t['Date'] = pd.to_datetime(df_t['Date'])
            chart_data = df_t.groupby(df_t['Date'].dt.strftime('%m-%Y'))['Freight'].sum()
            st.bar_chart(chart_data)
    with c2:
        st.subheader("Expense Distribution")
        if not df_a.empty:
            exp_data = df_a.groupby("Category")["Amount"].sum()
            st.write(exp_data)

# --- 8. FEATURE: ADD LR ---
elif menu == "➕ Create New LR":
    st.header("📝 Consignment Entry (LR)")
    v_type = st.radio("Trip Type", ["Own Vehicle", "Hired Vehicle"], horizontal=True)
    
    with st.form("main_lr_form", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("LR Date", date.today())
            lr_id = f"LR-{len(df_t)+1001}"
            party = st.text_input("Billing Party Name*")
            c_nm = st.text_input("Consignor Name")
            c_add = st.text_area("Consignor Address", height=100)
            c_gst = st.text_input("Consignor GST")
        with f2:
            ce_nm = st.text_input("Consignee Name")
            ce_add = st.text_area("Consignee Address", height=100)
            ce_gst = st.text_input("Consignee GST")
            v_no = st.text_input("Vehicle Number*")
            from_l = st.text_input("From (Origin)")
            to_l = st.text_input("To (Destination)")
        with f3:
            mat = st.text_input("Material Desc")
            weight = st.number_input("Weight (MT)", 0.0)
            freight = st.number_input("Total Freight*", 0.0)
            broker = st.text_input("Broker/Owner Name", disabled=(v_type=="Own Vehicle"))
            
            if v_type == "Hired Vehicle":
                h_chg = st.number_input("Hired Charges (Market Rate)")
                dsl, de, tl, ot = 0, 0, 0, 0
            else:
                h_chg = 0
                dsl = st.number_input("Diesel Expense")
                de = st.number_input("Driver Expense")
                tl = st.number_input("Toll & Taxes")
                ot = st.number_input("Misc Expense")

        if st.form_submit_button("🚀 SAVE LR TO CLOUD"):
            if party and v_no and freight > 0:
                calc_profit = (freight - h_chg) if v_type == "Hired Vehicle" else (freight - (dsl+de+tl+ot))
                v_type_val = "Hired" if v_type == "Hired Vehicle" else "Own"
                
                new_data = [str(d), lr_id, v_type_val, party, c_nm, c_gst, c_add, ce_nm, ce_gst, ce_add, 
                            mat, weight, v_no, "Driver", broker, from_l, to_l, freight, h_chg, 
                            dsl, de, tl, ot, calc_profit]
                
                if save_ws("trips", new_data):
                    st.success(f"LR {lr_id} saved successfully!"); st.rerun()
            else:
                st.error("Please fill required fields (*) and Freight should be > 0")

# --- 9. FEATURE: LR MANAGER (EDIT/DEL) ---
elif menu == "🔍 LR Manager (Edit/Del)":
    st.header("🔍 Search, Edit or Delete Records")
    if not df_t.empty:
        search_q = st.text_input("Search by LR, Vehicle, Party or City")
        # Multi-column search logic
        mask = df_t.apply(lambda r: search_q.lower() in str(r).lower(), axis=1)
        f_df = df_t[mask]

        for idx, row in f_df.iterrows():
            with st.expander(f"📄 {row['LR']} | {row['Party']} | {row['Vehicle']} | {row['Date']}"):
                with st.form(f"full_edit_{row['LR']}"):
                    st.info(f"Editing Mode: {row['Type']} Vehicle Entry")
                    e1, e2, e3 = st.columns(3)
                    # Mapping saare 24 columns for Edit
                    u_date = e1.text_input("Date", row['Date'])
                    u_party = e1.text_input("Party", row['Party'])
                    u_cnm = e1.text_input("Consignor", row['Consignor'])
                    u_cgst = e1.text_input("Consignor GST", row['Consignor_GST'])
                    u_cadd = e1.text_area("Consignor Add", row['Consignor_Add'])
                    
                    u_cenm = e2.text_input("Consignee", row['Consignee'])
                    u_cegst = e2.text_input("Consignee GST", row['Consignee_GST'])
                    u_ceadd = e2.text_area("Consignee Add", row['Consignee_Add'])
                    u_vno = e2.text_input("Vehicle", row['Vehicle'])
                    u_from = e2.text_input("From", row['From'])
                    u_to = e2.text_input("To", row['To'])
                    
                    u_mat = e3.text_input("Material", row['Material'])
                    u_wt = e3.number_input("Weight", value=float(row['Weight']))
                    u_fr = e3.number_input("Freight", value=float(row['Freight']))
                    u_hchg = e3.number_input("Hired Charges", value=float(row['HiredCharges']))
                    u_br = e3.text_input("Broker", row['Broker'])
                    u_dsl = e3.number_input("Diesel", value=float(row['Diesel']))
                    u_toll = e3.number_input("Toll", value=float(row['Toll']))

                    if st.form_submit_button("✅ UPDATE RECORD"):
                        # Recalculate Profit
                        u_prof = (u_fr - u_hchg) if row['Type'] == "Hired" else (u_fr - (u_dsl + float(row['DriverExp']) + u_toll + float(row['Other'])))
                        
                        # Data prepare
                        up_list = list(row.values)
                        up_list[0], up_list[3], up_list[4], up_list[5], up_list[6] = u_date, u_party, u_cnm, u_cgst, u_cadd
                        up_list[7], up_list[8], up_list[9], up_list[12], up_list[15], up_list[16] = u_cenm, u_cegst, u_ceadd, u_vno, u_from, u_to
                        up_list[10], up_list[11], up_list[17], up_list[18], up_list[14], up_list[19], up_list[21], up_list[23] = u_mat, u_wt, u_fr, u_hchg, u_br, u_dsl, u_toll, u_prof
                        
                        if update_ws("trips", row['LR'], up_list):
                            st.success("Updated!"); st.rerun()

                c_del, c_pdf = st.columns([1, 4])
                if c_del.button(f"🗑️ DELETE {row['LR']}", key=f"del_btn_{idx}"):
                    if delete_ws("trips", row['LR']):
                        st.warning("Deleted!"); st.rerun()
                c_pdf.download_button("📥 DOWNLOAD PDF LR", create_lr_pdf(row), f"{row['LR']}.pdf")

# --- 10. FEATURE: MONTHLY BILLING ---
elif menu == "📅 Monthly Billing":
    st.header("📅 Party-wise Monthly Invoice Summary")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        parties = df_t["Party"].unique()
        sel_party = st.selectbox("Select Party", parties)
        
        months = df_t[df_t['Party'] == sel_party]['Date'].dt.strftime('%B %Y').unique()
        if len(months) > 0:
            sel_month = st.selectbox("Select Month", months)
            
            bill_df = df_t[(df_t['Party'] == sel_party) & (df_t['Date'].dt.strftime('%B %Y') == sel_month)]
            st.dataframe(bill_df[["Date", "LR", "Vehicle", "From", "To", "Material", "Weight", "Freight"]], use_container_width=True)
            
            total_bill = bill_df["Freight"].sum()
            st.info(f"Total Billing for {sel_party} in {sel_month}: ₹{total_bill:,.0f}")
        else:
            st.warning("No data for this party.")

# --- 11. FEATURE: LEDGERS ---
elif menu == "🏢 Party Ledger":
    st.header("🏢 Party Accounts (Outstanding)")
    if not df_t.empty:
        billing = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total_Billing"})
        receipts = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Received"})
        
        ledger = pd.merge(billing, receipts, on="Name", how="left").fillna(0)
        ledger["Balance_Due"] = ledger["Total_Billing"] - ledger["Total_Received"]
        st.table(ledger.style.format({"Total_Billing": "₹{:.0f}", "Total_Received": "₹{:.0f}", "Balance_Due": "₹{:.0f}"}))

elif menu == "🤝 Broker Ledger":
    st.header("🤝 Broker/Market Accounts")
    # Accuracy: Strict 'Hired' check
    hired_df = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not hired_df.empty:
        work = hired_df.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total_Payable"})
        paid = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Paid"})
        
        b_ledger = pd.merge(work, paid, on="Name", how="left").fillna(0)
        b_ledger["Net_Balance"] = b_ledger["Total_Payable"] - b_ledger["Total_Paid"]
        st.table(b_ledger.style.format({"Total_Payable": "₹{:.0f}", "Total_Paid": "₹{:.0f}", "Net_Balance": "₹{:.0f}"}))
    else:
        st.info("No Hired Vehicle entries found.")

# --- 12. FEATURE: VEHICLE PROFIT ---
elif menu == "🚛 Vehicle Profit":
    st.header("🚛 Vehicle Performance & Profitability")
    if not df_t.empty:
        # Grouping by Vehicle number
        v_report = df_t.groupby("Vehicle").agg({
            "LR": "count",
            "Freight": "sum",
            "Profit": "sum",
            "Weight": "sum"
        }).reset_index().rename(columns={"LR": "Trips", "Freight": "Total_Revenue", "Weight": "MT_Handled"})
        
        st.dataframe(v_report.style.format({"Total_Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.subheader("Vehicle-wise Profit Distribution")
        st.bar_chart(v_report.set_index("Vehicle")["Profit"])

# --- 13. FEATURE: TRANSACTIONS ---
elif menu in ["💰 Party Payment", "💸 Broker Payout"]:
    cat_type = "Party" if "Party" in menu else "Broker"
    st.header(f"💰 Record {cat_type} Transaction")
    with st.form("pay_form"):
        # Select Name from Existing list for accuracy
        names = df_t[cat_type].unique() if not df_t.empty else []
        sel_name = st.selectbox("Select Name", names)
        amt = st.number_input("Transaction Amount", 0.0)
        mode = st.selectbox("Mode", ["Bank Transfer", "Cash", "Cheque", "UPI"])
        if st.form_submit_button("Record Entry"):
            if sel_name and amt > 0:
                if save_ws("payments", [str(date.today()), sel_name, cat_type, amt, mode]):
                    st.success("Recorded!"); st.rerun()

elif menu == "🏢 Office Expense":
    st.header("🏢 Monthly Admin & Office Expenses")
    with st.form("exp_form"):
        e_cat = st.selectbox("Expense Type", ["Rent", "Salary", "Stationary", "Electricity", "Repair", "Tea/Snacks", "Other"])
        e_amt = st.number_input("Amount", 0.0)
        e_rem = st.text_input("Remarks (optional)")
        if st.form_submit_button("Save Expense"):
            if e_amt > 0:
                if save_ws("admin", [str(date.today()), e_cat, e_amt, e_rem]):
                    st.success("Expense Saved!"); st.rerun()
