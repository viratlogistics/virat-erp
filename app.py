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
        # Secrets se JSON string load karna
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Login Failed (Check Secrets JSON): {e}")
        return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

# Safe Sheet Opening
sh = None
if client:
    try:
        sh = client.open(SHEET_NAME)
    except Exception as e:
        st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili. Check sharing with service email.")
        st.stop()

def load_from_gs(worksheet_name):
    try:
        ws = sh.worksheet(worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# --- SAFE DATA LOADING (Prevents KeyError) ---
def load_safe(worksheet_name, default_cols):
    df = load_from_gs(worksheet_name)
    if df.empty:
        return pd.DataFrame(columns=default_cols)
    # Missing columns ko 0 ya empty string se bhar dena
    for col in default_cols:
        if col not in df.columns:
            df[col] = 0 if any(x in col for x in ["Amount", "Freight", "Profit", "HiredCharges", "Weight"]) else ""
    return df[default_cols]

# Columns structure
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_safe("trips", cols_t)
    df_p = load_safe("payments", cols_p)
    df_a = load_safe("admin", cols_a)
else:
    st.stop()

def save_to_gs(worksheet_name, row_data):
    try:
        ws = sh.worksheet(worksheet_name)
        ws.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"Error saving to {worksheet_name}: {e}")
        return False

# --- 2. PDF GENERATORS ---
def generate_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.set_text_color(211, 47, 47)
    pdf.cell(190, 10, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, f"LR No: {row['LR']}", border=1)
    pdf.cell(95, 10, f"Date: {row['Date']}", border=1, ln=True)
    pdf.ln(5)
    y_start = pdf.get_y()
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 7, "CONSIGNOR", border='TLR')
    pdf.cell(95, 7, "CONSIGNEE", border='TLR', ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(95, 5, f"{row['Consignor']}\n{row['Consignor_Add']}\nGST: {row['Consignor_GST']}", border='LRB')
    pdf.set_y(y_start + 7); pdf.set_x(105)
    pdf.multi_cell(95, 5, f"{row['Consignee']}\n{row['Consignee_Add']}\nGST: {row['Consignee_GST']}", border='LRB')
    pdf.ln(10)
    pdf.cell(100, 10, f"Material: {row['Material']}", border=1)
    pdf.cell(40, 10, f"Weight: {row['Weight']} MT", border=1)
    pdf.cell(50, 10, f"Freight: Rs. {row['Freight']:,}", border=1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 3. LOGIN (admin / 1234) ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP Login")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
        else: st.error("Wrong Login")
    st.stop()

# --- 4. SIDEBAR MENU ---
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add LR", "Monthly Bill", "Vehicle Profit", "Party Receipt", "Broker Payment", "Admin Expense", "LR Report", "Party Ledger", "Broker Ledger"])

# --- 5. DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary (Live Sheets)")
    
    t_prof = pd.to_numeric(df_t["Profit"], errors='coerce').sum()
    t_rev = pd.to_numeric(df_t["Freight"], errors='coerce').sum()
    a_exp = pd.to_numeric(df_a["Amount"], errors='coerce').sum()
    
    p_rec = pd.to_numeric(df_p[df_p["Category"]=="Party"]["Amount"], errors='coerce').sum() if not df_p.empty else 0
    b_work = pd.to_numeric(df_t["HiredCharges"], errors='coerce').sum()
    b_paid = pd.to_numeric(df_p[df_p["Category"]=="Broker"]["Amount"], errors='coerce').sum() if not df_p.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Trip Profit", f"₹{t_prof:,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Due", f"₹{(b_work - b_paid):,.0f}")
    st.divider()
    st.metric("Office Admin Expenses", f"₹{a_exp:,.0f}")

# --- 6. ADD LR ---
elif menu == "Add LR":
    st.header(f"📝 New LR Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d, lr = st.date_input("Date", date.today()), "LR-" + str(len(df_t) + 1001)
            party = st.text_input("Billing Party*")
            consignor = st.text_input("Consignor")
            con_gst = st.text_input("Consignor GST")
            con_add = st.text_area("Consignor Address")
        with c2:
            consignee = st.text_input("Consignee")
            cee_gst = st.text_input("Consignee GST")
            cee_add = st.text_area("Consignee Address")
            f_loc, t_loc = st.text_input("From Location"), st.text_input("To Location")
            vehicle = st.text_input("Vehicle No*")
        with c3:
            mat = st.text_input("Material")
            wt = st.number_input("Weight", 0.0)
            broker = st.text_input("Broker", disabled=(v_type=="Own"))
            freight = st.number_input("Freight*", 0.0)
            if v_type == "Hired":
                h_chg, dsl, de, tl, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else:
                h_chg, dsl, de, tl, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save to Sheets"):
            if party and vehicle:
                prof = (freight - (dsl+de+tl+ot)) if v_type == "Own" else (freight - h_chg)
                new_row = [str(d), lr, v_type, party, consignor, con_gst, con_add, consignee, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
                if save_to_gs("trips", new_row):
                    st.success("Saved Successfully!"); st.rerun()
            else:
                st.error("Please fill Billing Party and Vehicle No.")

# --- 7. VEHICLE PROFIT ---
elif menu == "Vehicle Profit":
    st.header("🚛 Own Vehicle Performance")
    own_trips = df_t[df_t["Type"] == "Own"]
    if not own_trips.empty:
        for c in ["Freight", "Diesel", "Profit"]: own_trips[c] = pd.to_numeric(own_trips[c], errors='coerce').fillna(0)
        veh_sum = own_trips.groupby("Vehicle").agg({"LR": "count", "Freight": "sum", "Profit": "sum"}).reset_index()
        st.dataframe(veh_sum.rename(columns={"LR":"Trips", "Freight":"Revenue"}), use_container_width=True)
    else:
        st.info("No Own Vehicle trips found.")

# --- 8. PAYMENTS & ADMIN ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Transaction")
    with st.form("p_form", clear_on_submit=True):
        nm = st.text_input("Name")
        am = st.number_input("Amount", 0.0)
        md = st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save Payment"):
            if nm and am > 0:
                save_to_gs("payments", [str(date.today()), nm, cat, am, md])
                st.success("Payment Saved!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Admin Expenses")
    with st.form("a_form", clear_on_submit=True):
        ct = st.selectbox("Type", ["Salary", "Rent", "Office", "Other"])
        am = st.number_input("Amount", 0.0)
        rem = st.text_input("Remarks")
        if st.form_submit_button("Save Expense"):
            if am > 0:
                save_to_gs("admin", [str(date.today()), ct, am, rem])
                st.success("Expense Saved!"); st.rerun()

# --- 9. LR REPORT ---
elif menu == "LR Report":
    st.header("📋 Trip Records")
    if not df_t.empty:
        for i, row in df_t.iterrows():
            with st.expander(f"{row['LR']} | {row['Party']} | {row['Vehicle']}"):
                st.write(row)
                pdf_data = generate_lr_pdf(row)
                st.download_button("📥 PDF LR", pdf_data, f"{row['LR']}.pdf", "application/pdf", key=f"pdf_{i}")
    else:
        st.info("No data available.")

# --- 10. LEDGERS ---
elif menu == "Party Ledger":
    st.header("🏢 Party Outstanding")
    if not df_t.empty:
        bill = df_t.groupby("Party")["Freight"].sum().reset_index()
        st.dataframe(bill)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Outstanding")
    hired = df_t[df_t["Type"] == "Hired"]
    if not hired.empty:
        work = hired.groupby("Broker")["HiredCharges"].sum().reset_index()
        st.dataframe(work)
