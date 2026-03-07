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
        st.error(f"❌ Login Failed (Check Secrets JSON): {e}")
        return None

client = get_gspread_client()
SHEET_NAME = "Virat_Logistics_Data"

sh = None
if client:
    try:
        sh = client.open(SHEET_NAME)
    except Exception as e:
        st.error(f"❌ Sheet '{SHEET_NAME}' nahi mili. Check sharing with service email.")
        st.stop()

# --- HELPER FUNCTIONS ---
def load_from_gs(worksheet_name):
    try:
        ws = sh.worksheet(worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def save_to_gs(worksheet_name, row_data):
    try:
        ws = sh.worksheet(worksheet_name)
        ws.append_row(row_data, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error saving to {worksheet_name}: {e}")
        return False

def update_gs_row(worksheet_name, lr_no, updated_row):
    try:
        ws = sh.worksheet(worksheet_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.update(f'A{cell.row}:X{cell.row}', [updated_row])
            return True
        return False
    except Exception as e:
        st.error(f"Update failed: {e}")
        return False

def delete_gs_row(worksheet_name, lr_no):
    try:
        ws = sh.worksheet(worksheet_name)
        cell = ws.find(str(lr_no))
        if cell:
            ws.delete_rows(cell.row)
            return True
        return False
    except Exception as e:
        st.error(f"Delete failed: {e}")
        return False

# --- DATA STRUCTURE & LOADING ---
cols_t = ["Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add","Consignee","Consignee_GST","Consignee_Add","Material","Weight","Vehicle","Driver","Broker","From","To","Freight","HiredCharges","Diesel","DriverExp","Toll","Other","Profit"]
cols_p = ["Date", "Name", "Category", "Amount", "Mode"]
cols_a = ["Date", "Category", "Amount", "Remarks"]

if sh:
    df_t = load_from_gs("trips")
    df_p = load_from_gs("payments")
    df_a = load_from_gs("admin")
    
    # Missing columns safety
    for c in cols_t:
        if c not in df_t.columns: df_t[c] = 0 if any(x in c for x in ["Freight", "Profit", "Weight", "Charges", "Diesel", "Toll", "Exp"]) else ""
    for c in cols_p:
        if c not in df_p.columns: df_p[c] = 0 if c == "Amount" else ""
    for c in cols_a:
        if c not in df_a.columns: df_a[c] = 0 if c == "Amount" else ""

    # Convert numeric columns safely
    num_cols_t = ["Freight", "HiredCharges", "Profit", "Weight", "Diesel", "Toll", "DriverExp", "Other"]
    for c in num_cols_t:
        df_t[c] = pd.to_numeric(df_t[c], errors='coerce').fillna(0)
    
    if not df_p.empty: df_p["Amount"] = pd.to_numeric(df_p["Amount"], errors='coerce').fillna(0)
    if not df_a.empty: df_a["Amount"] = pd.to_numeric(df_a["Amount"], errors='coerce').fillna(0)
else:
    st.stop()

# --- PDF GENERATOR ---
def generate_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 24); pdf.set_text_color(200, 0, 0)
    pdf.cell(190, 15, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 5, "TRANSPORT & FLEET MANAGEMENT", ln=True, align='C'); pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, f"LR No: {row['LR']}", 1); pdf.cell(95, 10, f"Date: {row['Date']}", 1, ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 8, "CONSIGNOR (SENDER)", 1); pdf.cell(95, 8, "CONSIGNEE (RECEIVER)", 1, ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(95, 6, f"{row['Consignor']}\nGST: {row['Consignor_GST']}\n{row['Consignor_Add']}", 1)
    pdf.set_y(pdf.get_y() - 18); pdf.set_x(105) # Adjust position for multi-cell
    pdf.multi_cell(95, 6, f"{row['Consignee']}\nGST: {row['Consignee_GST']}\n{row['Consignee_Add']}", 1)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "Vehicle No", 1); pdf.cell(100, 10, "Material Description", 1); pdf.cell(50, 10, "Weight (MT)", 1, ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(40, 10, str(row['Vehicle']), 1); pdf.cell(100, 10, str(row['Material']), 1); pdf.cell(50, 10, str(row['Weight']), 1, ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(140, 12, "TOTAL FREIGHT CHARGES", 1, align='R'); pdf.cell(50, 12, f"Rs. {row['Freight']:,}", 1, ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIN SYSTEM ---
if "login" not in st.session_state: st.session_state.login = False
if not st.session_state.login:
    st.title("🚚 Virat Logistics ERP Login")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Access System"):
        if u == "admin" and p == "1234":
            st.session_state.login = True; st.rerun()
        else: st.error("Invalid Username or Password")
    st.stop()

# --- SIDEBAR MENU ---
menu = st.sidebar.selectbox("Main Navigation", ["Dashboard", "Add LR", "LR Reports", "Monthly Bill", "Party Ledger", "Broker Ledger", "Party Receipt", "Broker Payment", "Admin Expense"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    t_rev = df_t["Freight"].sum()
    p_rec = df_p[df_p["Category"]=="Party"]["Amount"].sum() if not df_p.empty else 0
    b_work = df_t["HiredCharges"].sum()
    b_paid = df_p[df_p["Category"]=="Broker"]["Amount"].sum() if not df_p.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Trip Profit", f"₹{df_t['Profit'].sum():,.0f}")
    c2.metric("Party Outstanding", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Payable", f"₹{(b_work - b_paid):,.0f}")
    
    st.divider()
    st.subheader("Monthly Performance")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        monthly_stats = df_t.groupby(df_t['Date'].dt.strftime('%Y-%m'))['Freight'].sum()
        st.line_chart(monthly_stats)

# --- ADD LR ---
elif menu == "Add LR":
    st.header("📝 New Consignment Entry")
    v_type = st.radio("Vehicle Type", ["Own", "Hired"], horizontal=True)
    with st.form("lr_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            d = st.date_input("LR Date", date.today())
            lr_no = f"LR-{len(df_t)+1001}"
            party = st.text_input("Billing Party Name*")
            con_nm = st.text_input("Consignor Name")
            con_gst = st.text_input("Consignor GST")
            con_add = st.text_area("Consignor Address")
        with col2:
            cee_nm = st.text_input("Consignee Name")
            cee_gst = st.text_input("Consignee GST")
            cee_add = st.text_area("Consignee Address")
            f_loc = st.text_input("From Location")
            t_loc = st.text_input("To Location")
            vehicle = st.text_input("Vehicle Number*")
        with col3:
            mat = st.text_input("Material")
            wt = st.number_input("Weight (MT)", 0.0)
            broker = st.text_input("Broker Name", disabled=(v_type=="Own"))
            freight = st.number_input("Total Freight*", 0.0)
            if v_type == "Hired":
                h_chg = st.number_input("Hired Charges")
                dsl, de, tl, ot = 0, 0, 0, 0
            else:
                h_chg = 0
                dsl = st.number_input("Diesel Exp")
                de = st.number_input("Driver Exp")
                tl = st.number_input("Toll/Tax")
                ot = st.number_input("Other Exp")
        
        if st.form_submit_button("Submit & Save"):
            if party and vehicle:
                profit = (freight - h_chg) if v_type == "Hired" else (freight - (dsl+de+tl+ot))
                new_row = [str(d), lr_no, v_type, party, con_nm, con_gst, con_add, cee_nm, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, profit]
                if save_to_gs("trips", new_row):
                    st.success(f"Success! {lr_no} recorded."); st.rerun()
            else:
                st.error("Please fill required fields marked with *")

# --- LR REPORTS (COMPLETE EDIT/DELETE) ---
elif menu == "LR Reports":
    st.header("📋 LR Management (Edit/Delete)")
    if not df_t.empty:
        search = st.text_input("Search LR, Vehicle, or Party")
        filtered = df_t[df_t.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        
        for i, row in filtered.iterrows():
            with st.expander(f"View/Edit: {row['LR']} | {row['Party']} | {row['Vehicle']}"):
                with st.form(f"full_edit_{row['LR']}"):
                    st.write("### Trip Details")
                    c1, c2, c3 = st.columns(3)
                    # Mapping saare 24 columns for edit
                    u_date = c1.text_input("Date", row['Date'])
                    u_party = c1.text_input("Billing Party", row['Party'])
                    u_con = c1.text_input("Consignor", row['Consignor'])
                    u_con_gst = c1.text_input("Consignor GST", row['Consignor_GST'])
                    
                    u_cee = c2.text_input("Consignee", row['Consignee'])
                    u_cee_gst = c2.text_input("Consignee GST", row['Consignee_GST'])
                    u_veh = c2.text_input("Vehicle", row['Vehicle'])
                    u_mat = c2.text_input("Material", row['Material'])
                    
                    u_wt = c3.number_input("Weight", value=float(row['Weight']))
                    u_f = c3.number_input("Freight", value=float(row['Freight']))
                    u_h = c3.number_input("Hired Charges", value=float(row['HiredCharges']))
                    u_br = c3.text_input("Broker", row['Broker'])
                    
                    if st.form_submit_button("Save All Changes"):
                        # Profit recalculation on edit
                        new_prof = (u_f - u_h) if row['Type'] == "Hired" else (u_f - (row['Diesel'] + row['DriverExp'] + row['Toll'] + row['Other']))
                        updated_row = list(row.values)
                        # Index updates based on cols_t
                        updated_row[0], updated_row[3], updated_row[4], updated_row[5], updated_row[7], updated_row[8], updated_row[12], updated_row[10], updated_row[11], updated_row[17], updated_row[18], updated_row[14], updated_row[23] = u_date, u_party, u_con, u_con_gst, u_cee, u_cee_gst, u_veh, u_mat, u_wt, u_f, u_h, u_br, new_prof
                        if update_gs_row("trips", row['LR'], updated_row):
                            st.success("Record updated successfully!"); st.rerun()
                
                col_d1, col_d2 = st.columns([1, 4])
                if col_d1.button(f"🗑️ Delete LR", key=f"del_{i}"):
                    if delete_gs_row("trips", row['LR']):
                        st.warning(f"{row['LR']} deleted."); st.rerun()
                st.download_button("📥 Download PDF LR", generate_lr_pdf(row), f"{row['LR']}.pdf")
    else:
        st.info("No trip data found in sheets.")

# --- MONTHLY BILL ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Invoice Generation")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        parties = df_t["Party"].unique()
        sel_party = st.selectbox("Choose Billing Party", parties)
        months = df_t['Date'].dt.strftime('%B %Y').unique()
        sel_month = st.selectbox("Choose Month", months)
        
        m_df = df_t[(df_t['Party'] == sel_party) & (df_t['Date'].dt.strftime('%B %Y') == sel_month)]
        
        if not m_df.empty:
            st.write(f"### Trips for {sel_party} in {sel_month}")
            st.dataframe(m_df[["Date", "LR", "Vehicle", "Material", "Weight", "From", "To", "Freight"]], use_container_width=True)
            st.metric("Total Monthly Billing", f"₹{m_df['Freight'].sum():,.0f}")
        else:
            st.warning("No trips found for this party in the selected month.")

# --- LEDGERS ---
elif menu == "Party Ledger":
    st.header("🏢 Party Outstanding Ledger")
    if not df_t.empty:
        billing = df_t.groupby("Party")["Freight"].sum().reset_index().rename(columns={"Party":"Name", "Freight":"Total_Billing"})
        receipts = df_p[df_p["Category"]=="Party"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Received"})
        ledger = pd.merge(billing, receipts, on="Name", how="left").fillna(0)
        ledger["Outstanding"] = ledger["Total_Billing"] - ledger["Total_Received"]
        st.table(ledger)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Payable Ledger")
    hired_df = df_t[df_t["Type"] == "Hired"]
    if not hired_df.empty:
        broker_work = hired_df.groupby("Broker")["HiredCharges"].sum().reset_index().rename(columns={"Broker":"Name", "HiredCharges":"Total_Payable"})
        broker_paid = df_p[df_p["Category"]=="Broker"].groupby("Name")["Amount"].sum().reset_index().rename(columns={"Amount":"Total_Paid"})
        ledger = pd.merge(broker_work, broker_paid, on="Name", how="left").fillna(0)
        ledger["Balance_Due"] = ledger["Total_Payable"] - ledger["Total_Paid"]
        st.table(ledger)
    else:
        st.info("No hired vehicle data found.")

# --- PAYMENTS ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 Record {cat} Payment")
    with st.form("payment_form"):
        # Select name from existing records
        if not df_t.empty:
            name_list = df_t[cat].unique() if cat in df_t.columns else []
            name = st.selectbox("Select Name", name_list)
        else:
            name = st.text_input("Enter Name")
            
        p_amt = st.number_input("Amount Paid/Received", 0.0)
        p_mode = st.selectbox("Payment Mode", ["Bank Transfer", "Cash", "Cheque", "Other"])
        if st.form_submit_button("Record Transaction"):
            if name and p_amt > 0:
                if save_to_gs("payments", [str(date.today()), name, cat, p_amt, p_mode]):
                    st.success("Transaction recorded!"); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Office Admin Expenses")
    with st.form("admin_exp"):
        a_cat = st.selectbox("Expense Category", ["Staff Salary", "Office Rent", "Stationary", "Maintenance", "Electricity/WiFi", "Other"])
        a_amt = st.number_input("Amount", 0.0)
        a_rem = st.text_input("Remarks/Notes")
        if st.form_submit_button("Save Expense"):
            if a_amt > 0:
                if save_to_gs("admin", [str(date.today()), a_cat, a_amt, a_rem]):
                    st.success("Expense saved!"); st.rerun()
