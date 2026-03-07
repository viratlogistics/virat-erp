import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 1. CONFIG & GOOGLE SHEETS SETUP ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

def get_gspread_client():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Login Failed: {e}")
        return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

sh = None
if client:
    try: sh = client.open(SHEET_NAME)
    except: st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili."); st.stop()

def load_from_gs(worksheet_name):
    try:
        ws = sh.worksheet(worksheet_name)
        return pd.DataFrame(ws.get_all_records())
    except: return pd.DataFrame()

# Column Structures
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_from_gs("trips")
    df_p = load_from_gs("payments")
    df_a = load_from_gs("admin")
    
    # Missing columns safety & Numeric Conversion
    for c in cols_t: 
        if c not in df_t.columns: df_t[c] = ""
    num_cols = ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp", "Other"]
    for c in num_cols:
        if c in df_t.columns:
            df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    
    if not df_p.empty:
        df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    if not df_a.empty:
        df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
else:
    st.stop()

def save_to_gs(worksheet_name, row_data):
    try:
        ws = sh.worksheet(worksheet_name)
        ws.append_row(row_data, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error: {e}"); return False

# --- 2. PDF GENERATORS ---
def generate_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20); pdf.cell(190, 10, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.cell(190, 5, "Transport & Fleet Management", ln=True, align='C'); pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, f"LR No: {row['LR']}", border=1)
    pdf.cell(95, 10, f"Date: {row['Date']}", border=1, ln=True); pdf.ln(5)
    pdf.cell(95, 7, f"Consignor: {row['Consignor']}", border='TLR', ln=True)
    pdf.cell(95, 7, f"Consignee: {row['Consignee']}", border='LRB', ln=True); pdf.ln(5)
    pdf.cell(100, 10, f"Material: {row['Material']}", border=1)
    pdf.cell(90, 10, f"Freight: Rs. {row['Freight']}", border=1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

def generate_monthly_pdf(party, m_df, month):
    pdf = FPDF(orientation='L', unit='mm', format='A4'); pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(280, 10, f"BILL SUMMARY - {party}", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.cell(280, 7, f"Month: {month}", ln=True, align='C'); pdf.ln(5)
    pdf.set_font("Arial", 'B', 8)
    for h in ["Date", "LR", "Vehicle", "Consignee", "From-To", "Freight"]: pdf.cell(45, 8, h, 1, 0, 'C')
    pdf.ln(); pdf.set_font("Arial", '', 8)
    for _, r in m_df.iterrows():
        pdf.cell(45, 7, str(r['Date']), 1)
        pdf.cell(45, 7, str(r['LR']), 1)
        pdf.cell(45, 7, str(r['Vehicle']), 1)
        pdf.cell(45, 7, str(r['Consignee'])[:20], 1)
        pdf.cell(45, 7, f"{r['From']}-{r['To']}"[:20], 1)
        pdf.cell(45, 7, str(r['Freight']), 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. LOGIN & MENU ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP")
    u, p = st.text_input("User"), st.text_input("Pass", type="password")
    if st.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
    st.stop()

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add LR", "LR Reports", "Monthly Bill", "Vehicle Profit", "Party Ledger", "Broker Ledger", "Party Receipt", "Broker Payment", "Admin Expense"])

# --- 4. DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    t_rev = df_t["Freight"].sum()
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum() if not df_p.empty else 0
    b_work = df_t["HiredCharges"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum() if not df_p.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Profit", f"₹{df_t['Profit'].sum():,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Payable", f"₹{(b_work - b_paid):,.0f}")

# --- 5. ADD LR ---
elif menu == "Add LR":
    st.header("📝 New LR Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d, party = st.date_input("Date"), st.text_input("Billing Party*")
            consignor, con_gst, con_add = st.text_input("Consignor"), st.text_input("GST"), st.text_area("Address")
        with c2:
            consignee, cee_gst, cee_add = st.text_input("Consignee"), st.text_input("Consignee GST"), st.text_area("Consignee Add")
            f_loc, t_loc, vehicle = st.text_input("From"), st.text_input("To"), st.text_input("Vehicle No*")
        with c3:
            mat, wt = st.text_input("Material"), st.number_input("Weight", 0.0)
            broker = st.text_input("Broker", disabled=(v_type=="Own"))
            freight = st.number_input("Freight*", 0.0)
            if v_type == "Hired": h_chg, dsl, de, tl, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else: h_chg, dsl, de, tl, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save"):
            prof = (freight - (dsl+de+tl+ot)) if v_type == "Own" else (freight - h_chg)
            new_row = [str(d), f"LR-{len(df_t)+1001}", v_type, party, consignor, con_gst, con_add, consignee, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
            if save_to_gs("trips", new_row): st.success("Saved!"); st.rerun()

# --- 6. LR REPORTS ---
elif menu == "LR Reports":
    st.header("📋 All LR Records")
    if not df_t.empty:
        for i, row in df_t.iterrows():
            with st.expander(f"{row['LR']} | {row['Party']} | {row['Vehicle']}"):
                st.write(row)
                st.download_button("📥 PDF", generate_lr_pdf(row), f"{row['LR']}.pdf", "application/pdf", key=f"pdf_{i}")

# --- 7. MONTHLY BILL ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Party Bill")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        p_name = st.selectbox("Select Party", df_t["Party"].unique())
        m_list = df_t['Date'].dt.strftime('%B %Y').unique()
        sel_m = st.selectbox("Select Month", m_list)
        m_df = df_t[(df_t['Party']==p_name) & (df_t['Date'].dt.strftime('%B %Y')==sel_m)]
        if not m_df.empty:
            st.dataframe(m_df)
            st.download_button("📥 Download Monthly PDF", generate_monthly_pdf(p_name, m_df, sel_m), f"Bill_{p_name}.pdf", "application/pdf")

# --- 8. VEHICLE PROFIT ---
elif menu == "Vehicle Profit":
    st.header("🚛 Vehicle Wise Profit")
    own = df_t[df_t["Type"]=="Own"]
    if not own.empty:
        v_sum = own.groupby("Vehicle").agg({"LR":"count", "Freight":"sum", "Profit":"sum"}).reset_index()
        st.dataframe(v_sum.rename(columns={"LR":"Trips"}), use_container_width=True)

# --- 9. LEDGERS ---
elif menu == "Party Ledger":
    st.header("🏢 Party Ledger")
    if not df_t.empty:
        p_bill = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total_Billing"})
        p_paid = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Received"})
        res = pd.merge(p_bill, p_paid, on="Name", how="left").fillna(0)
        res["Balance"] = res["Total_Billing"] - res["Total_Received"]
        st.dataframe(res, use_container_width=True)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Wise Outstanding")
    
    # Sirf 'Hired' trips ko filter karein
    hired = df_t[df_t["Type"] == "Hired"]
    
    if not hired.empty:
        # Numeric conversion safety
        hired["HiredCharges"] = pd.to_numeric(hired["HiredCharges"], errors='coerce').fillna(0)
        
        # Broker ke naam se group karein
        b_work = hired.groupby("Broker")["HiredCharges"].sum().reset_index()
        b_work.columns = ["Name", "Total_Work"]
        
        # Payments check karein
        if not df_p.empty:
            df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
            b_paid = df_p[df_p["Category"] == "Broker"].groupby("Name")["Amount"].sum().reset_index()
            b_paid.columns = ["Name", "Total_Paid"]
        else:
            b_paid = pd.DataFrame(columns=["Name", "Total_Paid"])
            
        # Merge Work and Paid data
        res = pd.merge(b_work, b_paid, on="Name", how="left").fillna(0)
        res["Balance"] = res["Total_Work"] - res["Total_Paid"]
        
        # Final Table Display
        st.subheader("Summary Table")
        st.dataframe(res, use_container_width=True)
        
        # Detail view for each broker
        st.divider()
        st.subheader("Broker Wise Trip Details")
        for b_name in res["Name"].unique():
            with st.expander(f"Details for: {b_name}"):
                st.write(hired[hired["Broker"] == b_name][["Date", "LR", "Vehicle", "From", "To", "HiredCharges"]])
    else:
        st.info("Koi 'Hired' type ki entry nahi mili. Add LR mein 'Hired' select karke entry karein.")
# --- 10. PAYMENTS & ADMIN ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Entry")
    with st.form("p_form", clear_on_submit=True):
        nm = st.selectbox("Name", df_t[cat].unique() if not df_t.empty else [])
        am, md = st.number_input("Amount", 0.0), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save"):
            if save_to_gs("payments", [str(date.today()), nm, cat, am, md]): st.success("Saved!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Admin Expense")
    with st.form("a_form", clear_on_submit=True):
        ct, am, rem = st.selectbox("Type", ["Salary", "Rent", "Office", "Other"]), st.number_input("Amount"), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            save_to_gs("admin", [str(date.today()), ct, am, rem]); st.rerun()

