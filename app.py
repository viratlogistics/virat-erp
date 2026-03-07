import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIG & GOOGLE SHEETS SETUP ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

# Google Sheets Connection Logic
def get_gspread_client():
    # Streamlit Secrets se credentials uthana
   def get_gspread_client():
    # Streamlit Secrets ko dictionary mein badalna
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # Private key ke newline (\n) characters ko fix karna
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

client = get_gspread_client()
# Sheet ka naam wahi hona chahiye jo aapne banaya hai
SHEET_NAME = "Virat_Logistics_Data"
sh = client.open(SHEET_NAME)

def load_from_gs(worksheet_name):
    ws = sh.worksheet(worksheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_to_gs(worksheet_name, row_data):
    ws = sh.worksheet(worksheet_name)
    ws.append_row(row_data)

# Data Loading from Sheets
try:
    df_t = load_from_gs("trips")
    df_p = load_from_gs("payments")
    df_a = load_from_gs("admin")
except Exception as e:
    st.error(f"Error connecting to Google Sheets: {e}")
    st.stop()

# --- 2. PDF GENERATION FUNCTIONS (Unchanged) ---
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

def generate_detailed_monthly_pdf(party, selected_df, selected_m):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(280, 10, "VIRAT LOGISTICS - SUMMARY INVOICE", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 9)
    cols = [("Date", 22), ("LR No", 22), ("Vehicle", 30), ("Consignee", 50), ("Material", 40), ("Weight", 20), ("From-To", 66), ("Freight", 30)]
    for c_name, width in cols: pdf.cell(width, 10, c_name, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", '', 8)
    for _, r in selected_df.iterrows():
        pdf.cell(22, 8, str(r['Date']), 1)
        pdf.cell(22, 8, str(r['LR']), 1)
        pdf.cell(30, 8, str(r['Vehicle']), 1)
        pdf.cell(50, 8, str(r['Consignee'])[:25], 1)
        pdf.cell(40, 8, str(r['Material'])[:20], 1)
        pdf.cell(20, 8, f"{r['Weight']}", 1, 0, 'C')
        pdf.cell(66, 8, f"{r['From']}-{r['To']}"[:40], 1)
        pdf.cell(30, 8, f"{r['Freight']:,}", 1, 1, 'R')
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(250, 10, "GRAND TOTAL", 1, 0, 'R')
    pdf.cell(30, 10, f"Rs. {selected_df['Freight'].sum():,}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. LOGIN ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP Login")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Login"):
        if u == "admin" and p == "1234": st.session_state.login = True; st.rerun()
        else: st.error("Wrong Login")
    st.stop()

# --- 4. SIDEBAR MENU ---
menu = st.sidebar.selectbox("Menu", [
    "Dashboard", "Add LR", "Monthly Bill", "Vehicle Profit", 
    "Party Receipt", "Broker Payment", "Admin Expense", 
    "LR Report", "Party Ledger", "Broker Ledger"
])

# --- 5. DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary (Live from Sheets)")
    trip_prof = pd.to_numeric(df_t["Profit"], errors='coerce').sum()
    adm_exp = pd.to_numeric(df_a["Amount"], errors='coerce').sum()
    t_rev = pd.to_numeric(df_t["Freight"], errors='coerce').sum()
    p_rec = pd.to_numeric(df_p[df_p["Category"]=="Party"]["Amount"]).sum()
    b_work = pd.to_numeric(df_t["HiredCharges"]).sum()
    b_paid = pd.to_numeric(df_p[df_p["Category"]=="Broker"]["Amount"]).sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Trip Profit", f"₹{trip_prof:,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Due", f"₹{(b_work - b_paid):,.0f}")

# --- 6. ADD LR ---
elif menu == "Add LR":
    st.header(f"📝 New LR Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d, lr = st.date_input("Date", date.today()), "LR-" + str(len(df_t) + 1001)
            party, consignor, con_gst, con_add = st.text_input("Billing Party*"), st.text_input("Consignor"), st.text_input("Consignor GST"), st.text_area("Consignor Address")
        with c2:
            consignee, cee_gst, cee_add = st.text_input("Consignee"), st.text_input("Consignee GST"), st.text_area("Consignee Address")
            f_loc, t_loc, vehicle = st.text_input("From Location"), st.text_input("To Location"), st.text_input("Vehicle No*")
        with c3:
            mat, wt, broker = st.text_input("Material"), st.number_input("Weight", 0.0), st.text_input("Broker", disabled=(v_type=="Own"))
            freight = st.number_input("Freight*", 0.0)
            if v_type == "Hired": h_chg, dsl, de, tl, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else: h_chg, dsl, de, tl, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save to Sheets"):
            if party and vehicle:
                prof = (freight - (dsl+de+tl+ot)) if v_type == "Own" else (freight - h_chg)
                new_row = [str(d), lr, v_type, party, consignor, con_gst, con_add, consignee, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
                save_to_gs("trips", new_row)
                st.success("Saved Successfully!"); st.rerun()

# --- 7. MONTHLY BILL ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Summary Bill")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        p_name = st.selectbox("Select Party", df_t["Party"].unique())
        m_list = df_t['Date'].dt.strftime('%B %Y').unique()
        sel_m = st.selectbox("Select Month", m_list)
        m_df = df_t[(df_t['Party']==p_name) & (df_t['Date'].dt.strftime('%B %Y')==sel_m)].copy()
        if not m_df.empty:
            m_df.insert(0, "Select", True)
            edited = st.data_editor(m_df, column_order=("Select", "Date", "LR", "Vehicle", "Consignee", "Material", "Weight", "Freight"), hide_index=True)
            sel_trips = edited[edited["Select"] == True]
            if not sel_trips.empty:
                pdf_bytes = generate_detailed_monthly_pdf(p_name, sel_trips, sel_m)
                st.download_button("📥 Download Monthly PDF", pdf_bytes, f"Bill_{p_name}.pdf", "application/pdf")

# --- (Other sections like Admin Expense, Ledgers follow same logic but use save_to_gs) ---
elif menu == "Admin Expense":
    st.header("🏢 Admin Expenses")
    with st.form("a_form", clear_on_submit=True):
        a_cat = st.selectbox("Category", ["Staff Salary", "Rent", "Electricity", "Other"])
        a_amt = st.number_input("Amount", 0.0)
        a_rem = st.text_input("Remarks")
        if st.form_submit_button("Save"):
            save_to_gs("admin", [str(date.today()), a_cat, a_amt, a_rem])
            st.rerun()

elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Transaction")
    with st.form("p_form", clear_on_submit=True):
        p_name = st.text_input("Name")
        p_amt = st.number_input("Amount", 0.0); p_mode = st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save"):
            save_to_gs("payments", [str(date.today()), p_name, cat, p_amt, p_mode])
            st.rerun()

