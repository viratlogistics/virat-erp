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

# Safe Sheet Opening
sh = None
if client:
    try:
        sh = client.open(SHEET_NAME)
    except:
        st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili. Check sharing settings.")
        st.stop()

def load_from_gs(worksheet_name):
    try:
        ws = sh.worksheet(worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def load_safe(worksheet_name, default_cols):
    df = load_from_gs(worksheet_name)
    if df.empty:
        return pd.DataFrame(columns=default_cols)
    for col in default_cols:
        if col not in df.columns:
            df[col] = 0 if any(x in col for x in ["Amount", "Freight", "Profit", "HiredCharges", "Weight"]) else ""
    return df[default_cols]

# Columns structure (DO NOT CHANGE ORDER)
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
        # Ensure row_data is a list of strings/numbers for proper column alignment
        ws.append_row(row_data, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error saving: {e}")
        return False

# --- 2. PDF GENERATORS ---
def generate_detailed_monthly_pdf(party, selected_df, selected_m):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(280, 10, "VIRAT LOGISTICS - SUMMARY BILL", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(280, 7, f"Party: {party} | Month: {selected_m}", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 8)
    headers = [("Date", 20), ("LR No", 20), ("Vehicle", 30), ("Consignee", 45), ("Material", 35), ("Weight", 15), ("Route", 65), ("Freight", 25)]
    for h, w in headers: pdf.cell(w, 8, h, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", '', 7)
    for _, r in selected_df.iterrows():
        pdf.cell(20, 7, str(r['Date']), 1)
        pdf.cell(20, 7, str(r['LR']), 1)
        pdf.cell(30, 7, str(r['Vehicle']), 1)
        pdf.cell(45, 7, str(r['Consignee'])[:25], 1)
        pdf.cell(35, 7, str(r['Material'])[:20], 1)
        pdf.cell(15, 7, str(r['Weight']), 1, 0, 'C')
        pdf.cell(65, 7, f"{r['From']}-{r['To']}"[:40], 1)
        pdf.cell(25, 7, f"{float(r['Freight']):,.0f}", 1, 1, 'R')
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(230, 10, "GRAND TOTAL", 1, 0, 'R')
    pdf.cell(25, 10, f"Rs. {selected_df['Freight'].astype(float).sum():,.0f}", 1, 1, 'R')
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

# --- 4. SIDEBAR ---
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add LR", "Monthly Bill", "Party Receipt", "Broker Payment", "Admin Expense", "Party Ledger", "Broker Ledger"])

# --- 5. DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    t_prof = pd.to_numeric(df_t["Profit"], errors='coerce').sum()
    t_rev = pd.to_numeric(df_t["Freight"], errors='coerce').sum()
    a_exp = pd.to_numeric(df_a["Amount"], errors='coerce').sum()
    p_rec = pd.to_numeric(df_p[df_p["Category"]=="Party"]["Amount"], errors='coerce').sum() if not df_p.empty else 0
    b_work = pd.to_numeric(df_t["HiredCharges"], errors='coerce').sum()
    b_paid = pd.to_numeric(df_p[df_p["Category"]=="Broker"]["Amount"], errors='coerce').sum() if not df_p.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Profit", f"₹{t_prof:,.0f}")
    c2.metric("Party Outstanding", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Payable", f"₹{(b_work - b_paid):,.0f}")
    st.divider()
    st.metric("Office Expenses", f"₹{a_exp:,.0f}")

# --- 6. ADD LR ---
elif menu == "Add LR":
    st.header(f"📝 New LR Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            lr = "LR-" + str(len(df_t) + 1001)
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
            mat, wt = st.text_input("Material"), st.number_input("Weight", 0.0)
            broker = st.text_input("Broker", disabled=(v_type=="Own"))
            freight = st.number_input("Freight*", 0.0)
            if v_type == "Hired":
                h_chg, dsl, de, tl, ot = st.number_input("Hired Charges"), 0, 0, 0, 0
            else:
                h_chg, dsl, de, tl, ot = 0, st.number_input("Diesel"), st.number_input("Driver Exp"), st.number_input("Toll"), st.number_input("Other")
        
        if st.form_submit_button("Save to Sheets"):
            if party and vehicle:
                prof = (freight - (dsl+de+tl+ot)) if v_type == "Own" else (freight - h_chg)
                # Align data strictly with cols_t
                new_row = [str(d), lr, v_type, party, consignor, con_gst, con_add, consignee, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
                if save_to_gs("trips", new_row):
                    st.success("Entry Saved Successfully!"); st.rerun()

# --- 7. MONTHLY BILL ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Summary Bill")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        p_list = df_t["Party"].unique()
        p_name = st.selectbox("Select Party", p_list)
        m_list = df_t['Date'].dt.strftime('%B %Y').unique()
        sel_m = st.selectbox("Select Month", m_list)
        m_df = df_t[(df_t['Party']==p_name) & (df_t['Date'].dt.strftime('%B %Y')==sel_m)].copy()
        if not m_df.empty:
            m_df.insert(0, "Select", True)
            edited = st.data_editor(m_df, hide_index=True)
            sel_trips = edited[edited["Select"] == True]
            if not sel_trips.empty:
                pdf_bytes = generate_detailed_monthly_pdf(p_name, sel_trips, sel_m)
                st.download_button("📥 Download Bill PDF", pdf_bytes, f"Bill_{p_name}_{sel_m}.pdf", "application/pdf")

# --- 8. LEDGERS (ACCURATE) ---
elif menu == "Party Ledger":
    st.header("🏢 Party Wise Outstanding")
    if not df_t.empty:
        # Total Billing
        p_bill = df_t.groupby("Party")["Freight"].sum().reset_index()
        p_bill.columns = ["Name", "Total_Billing"]
        # Total Received
        p_paid = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index() if not df_p.empty else pd.DataFrame(columns=["Name", "Amount"])
        p_paid.columns = ["Name", "Total_Received"]
        # Merge
        ledger = pd.merge(p_bill, p_paid, on="Name", how="left").fillna(0)
        ledger["Balance"] = ledger["Total_Billing"] - ledger["Total_Received"]
        st.dataframe(ledger, use_container_width=True)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Wise Outstanding")
    hired = df_t[df_t["Type"] == "Hired"]
    if not hired.empty:
        b_work = hired.groupby("Broker")["HiredCharges"].sum().reset_index()
        b_work.columns = ["Name", "Total_Work"]
        b_paid = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index() if not df_p.empty else pd.DataFrame(columns=["Name", "Amount"])
        b_paid.columns = ["Name", "Total_Paid"]
        ledger = pd.merge(b_work, b_paid, on="Name", how="left").fillna(0)
        ledger["Balance"] = ledger["Total_Work"] - ledger["Total_Paid"]
        st.dataframe(ledger, use_container_width=True)

# --- 9. PAYMENTS & ADMIN ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Transaction")
    with st.form("p_form", clear_on_submit=True):
        nm, am, md = st.text_input("Name (Exactly as in LR)"), st.number_input("Amount", 0.0), st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save Payment"):
            if nm and am > 0:
                if save_to_gs("payments", [str(date.today()), nm, cat, am, md]):
                    st.success("Payment Recorded!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Office Admin Expense")
    with st.form("a_form", clear_on_submit=True):
        ct, am, rem = st.selectbox("Type", ["Salary", "Rent", "Office", "Other"]), st.number_input("Amount", 0.0), st.text_input("Remarks")
        if st.form_submit_button("Save"):
            if am > 0:
                save_to_gs("admin", [str(date.today()), ct, am, rem])
                st.success("Expense Recorded!"); st.rerun()
