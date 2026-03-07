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

# Custom CSS for better look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

def get_gspread_client():
    try:
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

# --- 2. DATA UTILITIES (LEAK-PROOF LOGIC) ---
def load_ws(ws_name):
    try:
        ws = sh.worksheet(ws_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # Cleaning: Remove hidden spaces from names/types that break ledgers
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        return df
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

# --- 3. DATA REFRESH & NUMERIC CONVERSION ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_ws("trips")
    df_p = load_ws("payments")
    df_a = load_ws("admin")

    # Safety: Create missing columns for older data
    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    
    # Accurate Numeric Casting
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

# --- 4. PDF GENERATOR ---
def create_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 24); pdf.set_text_color(180, 0, 0)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10); pdf.set_text_color(100, 100, 100)
    pdf.cell(190, 5, "Fast & Reliable Transport Services", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 12); pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 12, f" LR NO: {row['LR']}", 1, 0, 'L', True)
    pdf.cell(95, 12, f" DATE: {row['Date']}", 1, 1, 'L', True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 8, " CONSIGNOR (SENDER)", 1, 0, 'L', True)
    pdf.cell(95, 8, " CONSIGNEE (RECEIVER)", 1, 1, 'L', True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(95, 8, f" {row['Consignor']}\n GST: {row['Consignor_GST']}\n Add: {row['Consignor_Add']}", 1)
    pdf.set_y(pdf.get_y() - 24); pdf.set_x(105) # Manual alignment for multi-cell
    pdf.multi_cell(95, 8, f" {row['Consignee']}\n GST: {row['Consignee_GST']}\n Add: {row['Consignee_Add']}", 1)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "VEHICLE", 1, 0, 'C', True); pdf.cell(100, 10, "MATERIAL", 1, 0, 'C', True); pdf.cell(50, 10, "WT (MT)", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(40, 10, str(row['Vehicle']), 1, 0, 'C'); pdf.cell(100, 10, str(row['Material']), 1, 0, 'C'); pdf.cell(50, 10, str(row['Weight']), 1, 1, 'C')
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(140, 12, "TOTAL FREIGHT ", 0, 0, 'R'); pdf.cell(50, 12, f"Rs. {row['Freight']:,}/-", 1, 1, 'C', True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🔒 Virat Logistics Secure Portal")
    with st.form("Login"):
        u = st.text_input("User ID")
        p = st.text_input("Security Pin", type="password")
        if st.form_submit_button("Access ERP"):
            if u == "admin" and p == "1234":
                st.session_state.login = True; st.rerun()
            else: st.error("Wrong Credentials")
    st.stop()

# --- 6. NAVIGATION ---
menu = st.sidebar.selectbox("📂 MAIN NAVIGATION", 
    ["📊 Dashboard", "➕ Add New LR", "🔍 LR Manager (Edit/Del)", "📅 Monthly Bill", 
     "🏢 Party Ledger", "🤝 Broker Ledger", "🚛 Vehicle Profit", "💰 Party Receipt", 
     "💸 Broker Payment", "🏢 Office Expense"])

# --- 7. FEATURES ---

# DASHBOARD
if menu == "📊 Dashboard":
    st.title("📊 Enterprise Overview")
    
    t_rev = df_t["Freight"].sum()
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum()
    b_work = df_t["HiredCharges"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum()
    trip_prof = df_t["Profit"].sum()
    off_exp = df_a["Amount"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Net Trip Profit", f"₹{trip_prof:,.0f}")
    col2.metric("Party Receivables", f"₹{(t_rev - p_rec):,.0f}", delta=f"Total: ₹{t_rev:,.0f}")
    col3.metric("Broker Payables", f"₹{(b_work - b_paid):,.0f}", delta=f"Work: ₹{b_work:,.0f}", delta_color="inverse")
    
    st.divider()
    st.subheader("Business Metrics")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### Trip Types Distribution")
        st.bar_chart(df_t["Type"].value_counts())
    with c2:
        st.write("### Office Expenditure")
        st.metric("Total Office Cost", f"₹{off_exp:,.0f}")
        st.dataframe(df_a.groupby("Category")["Amount"].sum(), use_container_width=True)

# ADD LR
elif menu == "➕ Add New LR":
    st.header("📝 Consignment Booking")
    v_type = st.radio("Trip Type Selection", ["Own Fleet", "Market Hired"], horizontal=True)
    
    with st.form("add_lr", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            d = st.date_input("LR Date", date.today())
            lr_id = f"LR-{len(df_t)+1001}"
            party = st.text_input("Billing Party Name*")
            cnm, cgst = st.text_input("Consignor"), st.text_input("Consignor GST")
            cadd = st.text_area("Consignor Address")
        with f2:
            eenm, eegst = st.text_input("Consignee"), st.text_input("Consignee GST")
            eeadd = st.text_area("Consignee Address")
            v_no = st.text_input("Vehicle Number*")
            floc, tloc = st.text_input("From Location"), st.text_input("To Location")
        with f3:
            mat, wt = st.text_input("Material Name"), st.number_input("Weight (MT)", 0.0)
            fr = st.number_input("Total Freight*", 0.0)
            br = st.text_input("Broker/Market Name", disabled=(v_type=="Own Fleet"))
            if v_type == "Market Hired":
                h_chg = st.number_input("Hired Charges (Market)")
                dsl, de, tl, ot = 0, 0, 0, 0
            else:
                h_chg = 0
                dsl, de, tl, ot = st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")

        if st.form_submit_button("✅ SAVE & SYNC"):
            if party and v_no and fr > 0:
                t_val = "Hired" if v_type == "Market Hired" else "Own"
                calc_prof = (fr - h_chg) if t_val == "Hired" else (fr - (dsl+de+tl+ot))
                row = [str(d), lr_id, t_val, party, cnm, cgst, cadd, eenm, eegst, eeadd, mat, wt, v_no, "Driver", br, floc, tloc, fr, h_chg, dsl, de, tl, ot, calc_prof]
                if save_ws("trips", row): st.success(f"{lr_id} Saved!"); st.rerun()
            else: st.error("Please fill Party, Vehicle and Freight.")

# LR MANAGER
elif menu == "🔍 LR Manager (Edit/Del)":
    st.header("🔍 Search and Manage Records")
    if not df_t.empty:
        sq = st.text_input("Search (LR, Vehicle, Party, Location)")
        f_df = df_t[df_t.apply(lambda r: sq.lower() in str(r).lower(), axis=1)]
        
        for idx, row in f_df.iterrows():
            with st.expander(f"📄 {row['LR']} | {row['Party']} | {row['Vehicle']} | {row['Date']}"):
                with st.form(f"edit_{row['LR']}"):
                    st.write("### Edit Entry Details")
                    e1, e2, e3 = st.columns(3)
                    # All 24 Columns Mapping for Edit
                    u_date = e1.text_input("Date", row['Date'])
                    u_party = e1.text_input("Billing Party", row['Party'])
                    u_cnm = e1.text_input("Consignor", row['Consignor'])
                    u_cgst = e1.text_input("Consignor GST", row['Consignor_GST'])
                    u_cadd = e1.text_area("Consignor Add", row['Consignor_Add'])
                    
                    u_eenm = e2.text_input("Consignee", row['Consignee'])
                    u_eegst = e2.text_input("Consignee GST", row['Consignee_GST'])
                    u_eeadd = e2.text_area("Consignee Add", row['Consignee_Add'])
                    u_vno = e2.text_input("Vehicle", row['Vehicle'])
                    u_floc = e2.text_input("From", row['From'])
                    u_tloc = e2.text_input("To", row['To'])
                    
                    u_mat = e3.text_input("Material", row['Material'])
                    u_wt = e3.number_input("Weight", value=float(row['Weight']))
                    u_fr = e3.number_input("Freight", value=float(row['Freight']))
                    u_hchg = e3.number_input("Hired Charges", value=float(row['HiredCharges']))
                    u_br = e3.text_input("Broker", row['Broker'])
                    u_dsl = e3.number_input("Diesel", value=float(row['Diesel']))
                    u_toll = e3.number_input("Toll", value=float(row['Toll']))

                    if st.form_submit_button("💾 UPDATE DATA"):
                        u_prof = (u_fr - u_hchg) if row['Type'] == "Hired" else (u_fr - (u_dsl + float(row['DriverExp']) + u_toll + float(row['Other'])))
                        up_list = list(row.values)
                        # Column Index Updates
                        up_list[0], up_list[3], up_list[4], up_list[5], up_list[6] = u_date, u_party, u_cnm, u_cgst, u_cadd
                        up_list[7], up_list[8], up_list[9], up_list[12], up_list[15], up_list[16] = u_eenm, u_eegst, u_eeadd, u_vno, u_floc, u_tloc
                        up_list[10], up_list[11], up_list[17], up_list[18], up_list[14], up_list[19], up_list[21], up_list[23] = u_mat, u_wt, u_fr, u_hchg, u_br, u_dsl, u_toll, u_prof
                        
                        if update_ws("trips", row['LR'], up_list): st.success("Updated!"); st.rerun()

                c_del, c_pdf = st.columns([1, 4])
                if c_del.button(f"🗑️ DELETE {row['LR']}", key=f"del_{idx}"):
                    if delete_ws("trips", row['LR']): st.warning("Deleted!"); st.rerun()
                c_pdf.download_button("📥 PDF LR", create_lr_pdf(row), f"{row['LR']}.pdf")

# MONTHLY BILLING
elif menu == "📅 Monthly Bill":
    st.header("📅 Party-wise Monthly Summary")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        sp = st.selectbox("Select Party", df_t["Party"].unique())
        sm = st.selectbox("Select Month", df_t[df_t['Party'] == sp]['Date'].dt.strftime('%B %Y').unique())
        
        m_df = df_t[(df_t['Party'] == sp) & (df_t['Date'].dt.strftime('%B %Y') == sm)]
        st.dataframe(m_df[["Date", "LR", "Vehicle", "From", "To", "Material", "Freight"]], use_container_width=True)
        st.info(f"Total Freight for {sm}: ₹{m_df['Freight'].sum():,.0f}")

# LEDGERS
elif menu == "🏢 Party Ledger":
    st.header("🏢 Party Accounts (Outstandings)")
    if not df_t.empty:
        b = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total_Billing"})
        r = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Received"})
        l = pd.merge(b, r, on="Name", how="left").fillna(0)
        l["Balance"] = l["Total_Billing"] - l["Total_Received"]
        st.table(l.style.format({"Total_Billing": "₹{:.0f}", "Total_Received": "₹{:.0f}", "Balance": "₹{:.0f}"}))

elif menu == "🤝 Broker Ledger":
    st.header("🤝 Broker Market Accounts")
    # Leak-proof: Strip spaces and lowercase for accurate filtering
    h_df = df_t[df_t["Type"].astype(str).str.lower() == "hired"]
    if not h_df.empty:
        w = h_df.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total_Work"})
        p = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Paid"})
        bl = pd.merge(w, p, on="Name", how="left").fillna(0)
        bl["Outstanding"] = bl["Total_Work"] - bl["Total_Paid"]
        st.table(bl.style.format({"Total_Work": "₹{:.0f}", "Total_Paid": "₹{:.0f}", "Outstanding": "₹{:.0f}"}))
    else: st.info("No Hired Vehicle entries found.")

# VEHICLE PROFIT
elif menu == "🚛 Vehicle Profit":
    st.header("🚛 Vehicle Performance Analysis")
    if not df_t.empty:
        vr = df_t.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index().rename(columns={"LR": "Trips", "Freight": "Revenue"})
        st.dataframe(vr.style.format({"Revenue": "₹{:.0f}", "Profit": "₹{:.0f}"}), use_container_width=True)
        st.bar_chart(vr.set_index("Vehicle")["Profit"])

# RECEIPTS & EXPENSES
elif menu in ["💰 Party Receipt", "💸 Broker Payment"]:
    cat = "Party" if "Party" in menu else "Broker"
    st.header(f"💰 {cat} Transaction Entry")
    with st.form("pay"):
        nms = df_t[cat].unique() if not df_t.empty else []
        snm = st.selectbox("Select Name", nms)
        am = st.number_input("Amount", 0.0)
        mo = st.selectbox("Mode", ["Bank Transfer", "Cash", "Cheque", "UPI"])
        if st.form_submit_button("Record Payment"):
            if snm and am > 0:
                if save_ws("payments", [str(date.today()), snm, cat, am, mo]): st.success("Recorded!"); st.rerun()

elif menu == "🏢 Office Expense":
    st.header("🏢 Daily Admin Expenses")
    with st.form("exp"):
        ec = st.selectbox("Category", ["Rent", "Salary", "Stationary", "Electricity", "Other"])
        ea = st.number_input("Amount", 0.0); er = st.text_input("Remarks")
        if st.form_submit_button("Save"):
            if ea > 0:
                if save_ws("admin", [str(date.today()), ec, ea, er]): st.success("Saved!"); st.rerun()
