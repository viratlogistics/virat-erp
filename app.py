import streamlit as st
from streamlit_option_menu import option_menu  # <--- Ye naya add karein
import pandas as pd # Agar pehle se hai toh rehne dein
import plotly.express as px
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json, io

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except:
        return None

sh = get_sh()

# --- Naya wala code yahan paste karein ---
def load(name):
    try:
        ws = sh.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        # Debit/Credit ko number mein badalne ke liye logic
        if 'Debit' in df.columns: df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
        if 'Credit' in df.columns: df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
        if 'Amount' in df.columns: df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except:
        return False

def delete_master_row(name_val):
    try:
        ws = sh.worksheet("masters")
        cell = ws.find(name_val)
        ws.delete_rows(cell.row)
        return True
    except:
        return False

def generate_lr_pdf(lr_data, show_fr=True):
    pdf = FPDF()
    pdf.add_page()
    
    # Header: Branch Name & Address
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, lr_data.get('BranchName', 'VIRAT LOGISTICS').upper(), ln=1, align='C')
    pdf.set_font("Arial", '', 8)
    pdf.cell(0, 4, lr_data.get('BranchAddr', 'N/A'), ln=1, align='C')
    pdf.cell(0, 4, f"GSTIN: {lr_data.get('BranchGST', 'N/A')}", ln=1, align='C')
    pdf.ln()

    # Basic Info Row
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(47, 8, f" LR No: {lr_data.get('LR No', '')}", 1, 0, 'L', True)
    pdf.cell(47, 8, f" Date: {lr_data.get('Date', '')}", 1, 0, 'L', True)
    pdf.cell(48, 8, f" Vehicle: {lr_data.get('Vehicle', '')}", 1, 0, 'L', True)
    pdf.cell(48, 8, f" Risk: {lr_data.get('Risk', 'Owner Risk')}", 1, 1, 'L', True)
    pdf.ln(2)

    # Party Details (Consignor, Consignee, Billing)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(63, 6, " CONSIGNOR", 1, 0, 'L', True)
    pdf.cell(63, 6, " CONSIGNEE", 1, 0, 'L', True)
    pdf.cell(64, 6, " BILLING PARTY / INV DETAILS", 1, 1, 'L', True)
    
    pdf.set_font("Arial", '', 8)
    y_s = pdf.get_y()
    pdf.multi_cell(63, 5, f"{lr_data.get('Cnor', '')}\nGST: {lr_data.get('CnorGST', 'N/A')}", 1, 'L')
    y_e1 = pdf.get_y()
    
    pdf.set_y(y_s); pdf.set_x(73)
    pdf.multi_cell(63, 5, f"{lr_data.get('Cnee', '')}\nGST: {lr_data.get('CneeGST', 'N/A')}", 1, 'L')
    y_e2 = pdf.get_y()
    
    pdf.set_y(y_s); pdf.set_x(136)
    inv_txt = f"Bill to: {lr_data.get('BillP', '')}\nInv No: {lr_data.get('InvNo', 'N/A')}\nInsurance: {lr_data.get('InsBy', 'N/A')}"
    pdf.multi_cell(64, 5, inv_txt, 1, 'L')
    y_e3 = pdf.get_y()
    
    pdf.set_y(max(y_e1, y_e2, y_e3)); pdf.ln(4)

    # Material Table
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(70, 8, " Description of Goods", 1, 0, 'C', True)
    pdf.cell(30, 8, " Pkg", 1, 0, 'C', True)
    pdf.cell(30, 8, " Net/Chg Wt", 1, 0, 'C', True)
    pdf.cell(30, 8, " Paid By", 1, 0, 'C', True)
    pdf.cell(30, 8, " Freight", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 9)
    amt = f"Rs. {lr_data.get('Freight', 0)}" if show_fr else "T.B.B."
    pdf.cell(70, 10, f" {lr_data.get('Material', '')}", 1, 0, 'L')
    pdf.cell(30, 10, f" {lr_data.get('Pkg', '')}", 1, 0, 'C')
    pdf.cell(30, 10, f" {lr_data.get('NetWt', 0)}/{lr_data.get('ChgWt', 0)}", 1, 0, 'C')
    pdf.cell(30, 10, f" {lr_data.get('PaidBy', 'N/A')}", 1, 0, 'C')
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(30, 10, amt, 1, 1, 'C')
    
    pdf.ln(2)
    pdf.cell(190, 6, f" DELIVERY ADDRESS: {lr_data.get('ShipTo', 'N/A')}", 1, 1, 'L')

    # Bottom Bank & T&C
    pdf.set_y(-55)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(100, 5, "PAYMENT BANK DETAILS:", 0, 0, 'L')
    pdf.cell(90, 5, f"FOR {lr_data.get('BranchName', 'VIRAT LOGISTICS')}", 0, 1, 'R')
    
    pdf.set_font("Arial", '', 8)
    pdf.cell(100, 4, f"Bank: {lr_data.get('BankName', 'N/A')}", ln=1)
    pdf.cell(100, 4, f"A/C No: {lr_data.get('BankAC', 'N/A')}", ln=1)
    pdf.cell(100, 4, f"IFSC Code: {lr_data.get('BankIFSC', 'N/A')}", ln=1)
    
    pdf.ln(4)
    pdf.set_font("Arial", 'I', 7)
    pdf.multi_cell(190, 3, "Terms: 1. Subject to Kosamba Jurisdiction. 2. No responsibility for damage after delivery. 3. Detention charges applicable if not unloaded in 24 hrs.")
    
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "--- COMPUTER GENERATED DOCUMENT, NO SIGNATURE REQUIRED ---", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

def generate_invoice_pdf(inv_data):
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER: Branch Details (Dynamic) ---
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, inv_data.get('BranchName', 'VIRAT LOGISTICS').upper(), ln=1, align='C')
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, f"Address: {inv_data.get('BranchAddr', 'N/A')}", ln=1, align='C')
    pdf.cell(0, 5, f"GSTIN: {inv_data.get('BranchGST', 'N/A')}", ln=1, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "TAX INVOICE / BILL", 1, 1, 'C')
    pdf.ln(5)
    
    # --- PARTY & INVOICE INFO ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(100, 6, f"Bill To: {inv_data['Party']}", 0, 0)
    pdf.cell(90, 6, f"Invoice No: {inv_data['InvNo']}", 0, 1, 'R')
    pdf.cell(100, 6, "", 0, 0)
    pdf.cell(90, 6, f"Date: {inv_data['InvDate']}", 0, 1, 'R')
    pdf.ln(5)

    # --- TABLE HEADER ---
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(30, 8, " LR No", 1, 0, 'C', True)
    pdf.cell(35, 8, " Date", 1, 0, 'C', True)
    pdf.cell(85, 8, " Vehicle / Particulars", 1, 0, 'C', True)
    pdf.cell(40, 8, " Amount", 1, 1, 'C', True)
    
    # --- TABLE ROWS (LRs) ---
    pdf.set_font("Arial", '', 9)
    for lr in inv_data['LRs']:
        pdf.cell(30, 8, f" {lr['LR No']}", 1)
        pdf.cell(35, 8, f" {lr['Date']}", 1)
        pdf.cell(85, 8, f" Truck: {lr['Vehicle No']}", 1)
        pdf.cell(40, 8, f" {lr['Freight']}", 1, 1, 'R')
    
    # --- TOTAL ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(150, 10, "GRAND TOTAL ", 1, 0, 'R')
    pdf.cell(40, 10, f"Rs. {inv_data['Total']}", 1, 1, 'R')
    pdf.ln(10)

    # --- BANK DETAILS SECTION (Multi-line Logic) ---
    b_name = inv_data.get('BankName', 'N/A')
    b_acc = inv_data.get('BankAC', 'N/A')
    b_ifsc = inv_data.get('BankIFSC', 'N/A')
    
    y_bank = pdf.get_y()
    pdf.set_font("Arial", 'B', 9)
    pdf.set_xy(10, y_bank)
    bank_text = f"Bank Name: {b_name}\nA/C No: {b_acc}\nIFSC Code: {b_ifsc}"
    pdf.multi_cell(100, 5, bank_text, 1, 'L') 
    y_end = pdf.get_y()

    # Right Box: Signatory
    pdf.set_xy(110, y_bank)
    pdf.cell(90, (y_end - y_bank), "For Virat Logistics (Auth. Signatory)", 1, 1, 'C')

    # Final Return (Encoding Fix)
    try:
        return pdf.output(dest='S').encode('latin-1')
    except:
        return pdf.output(dest='S').encode('utf-8', errors='ignore')
    
# --- 3. MAIN LOGIC ---
df_m = load("masters")
df_t = load("trips")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

# --- PAGE CONFIG ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide", initial_sidebar_state="collapsed")

# CSS for Professional Look
st.markdown("""
    <style>
        /* Sidebar width settings */
        [data-testid="stSidebar"] {
            background-color: #0e1117;
            min-width: 250px;
            max-width: 250px;
        }
        
        /* Main content area */
        .stMain {
            padding-top: 20px;
        }

        /* Metric design update */
        [data-testid="stMetricValue"] {
            font-size: 28px !important;
            color: #00d4ff !important;
        }

        /* Titles attractive design */
        h1, h2, h3 {
            color: #ffffff !important;
            font-weight: 700;
        }
    </style>
    """, unsafe_allow_html=True)
# --- GLOBAL DATA LOADING (Ise sidebar se pehle rakhein) ---
df_p = load("payments")
df_t = load("trips")
df_oe = load("office_expenses")
df_m = load("masters")

# Column Cleaning (Sabhi sheets ke liye ek saath)
for dff in [df_p, df_t, df_oe, df_m]:
    if not dff.empty: 
        dff.columns = [str(c).strip() for c in dff.columns]

# --- AB SIDEBAR SHURU HOGA ---
with st.sidebar:
    st.title("VIRAT LOGISTICS")
    # ... baki ka menu code

# --- UPDATED SIDEBAR MENU (Professional & Clean) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4090/4090434.png", width=80) # Ek transport icon
    st.title("VIRAT LOGISTICS")
    menu = option_menu(
        menu_title="Main Menu", 
        options=[
            "0. Dashboard", "1. Masters Setup", "2. LR Entry", "3. LR Register", 
            "4. Financials", "5. Business Insights", "6. Expense Manager", 
            "7. Driver Khata", "8. Monthly Bill"
        ], 
        icons=[
            "speedometer2", "person-gear", "file-earmark-plus", "table", 
            "currency-rupee", "graph-up-arrow", "wallet2", "person-badge", "receipt"
        ], 
        default_index=0,
        styles={
            "container": {"padding": "5!important", "background-color": "#0e1117"},
            "icon": {"color": "#00d4ff", "font-size": "20px"}, 
            "nav-link": {"font-size": "14px", "text-align": "left", "margin":"5px", "color": "white"},
            "nav-link-selected": {"background-color": "#00d4ff", "color": "black", "font-weight": "bold"},
        }
    )
    st.info(f"F.Y. 2026-27 | Active")
def gl(t): 
    return sorted(df_m[df_m['Type'] == t]['Name'].unique().tolist()) if not df_m.empty else []
def gl(t): 
    if df_m.empty: return []
    
    # Party, Consignor aur Broker ko combine karke dikhane ke liye
    if t in ["Party", "Consignor", "Broker"]:
        combined = df_m[df_m['Type'].isin(["Party", "Broker", "Consignor"])]['Name'].unique().tolist()
        return sorted([str(x) for x in combined if x and str(x).strip() != ""])
    
    # Baaki sab (Vehicle, Driver, Bank) ke liye normal logic
    return sorted(df_m[df_m['Type'] == t]['Name'].unique().tolist())
if menu == "0. Dashboard":
    st.markdown("<h1 style='text-align: center; color: #00d4ff;'>🚀 VIRAT LOGISTICS STRATEGIC DASHBOARD</h1>", unsafe_allow_html=True)

    # --- 1. DATA LOADING & CLEANING ---
    df_p = load("payments")
    df_t = load("trips")
    df_oe = load("office_expenses")
    df_m = load("masters")

    # Column cleaning
    for dff in [df_p, df_t, df_oe]:
        if not dff.empty: 
            dff.columns = [str(c).strip() for c in dff.columns]

    # --- 2. ADVANCED ACCOUNTING CALCULATIONS ---
    
    # A. CASH FLOW (Actual Paisa)
    op_cash = 0
    curr_receipts = 0
    bank_fin_out = 0
    
    if not df_p.empty:
        bank_mask = df_p['Account_Name'].str.contains('BANK|CASH', case=False, na=False)
        bank_df = df_p[bank_mask]
        # Opening Cash (Dr - Cr for OP_BAL)
        op_cash = bank_df[bank_df['Type'] == 'OP_BAL']['Debit'].sum() - bank_df[bank_df['Type'] == 'OP_BAL']['Credit'].sum()
        # Current Receipts (Dr side excluding OP_BAL)
        curr_receipts = bank_df[bank_df['Type'] != 'OP_BAL']['Debit'].sum()
        # Financial Payments (Cr side excluding OP_BAL)
        bank_fin_out = bank_df[bank_df['Type'] != 'OP_BAL']['Credit'].sum()

    # Trip Cash Outflow (ONLY OWN FLEET - Diesel, Toll, DriverExp)
    # Hired charges are skipped here because they go through Financials
    trip_cash_out = 0
    if not df_t.empty:
        own_mask = df_t['Type'].str.contains('Own', case=False, na=False)
        trip_cash_out = df_t[own_mask][['Diesel', 'Toll', 'DriverExp']].sum().sum()
    
    # Office Expenses Outflow
    office_outflow = pd.to_numeric(df_oe['Amount'], errors='coerce').sum() if not df_oe.empty else 0

    # FINAL METRICS
    combined_total_outflow = bank_fin_out + trip_cash_out + office_outflow
    net_cash_balance = (op_cash + curr_receipts) - combined_total_outflow

    # --- 3. TOP METRICS UI (Graphics) ---
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Net Cash Hand", f"₹{net_cash_balance:,.0f}", help="Handles Overdraft/Minus balances")
    m2.metric("🏠 Opening Fund", f"₹{op_cash:,.0f}")
    m3.metric("📥 Current Inflow", f"₹{curr_receipts:,.0f}", help="Actual Receipts")
    m4.metric("📤 Total Outflow", f"₹{combined_total_outflow:,.0f}", delta_color="inverse")

    st.divider()

    # --- 4. ACCRUAL FUND FLOW (Receivables & Payables) ---
    # Receivables = Party Op (Dr) + New Freight - Receipts (Cr)
    parties = gl("Party")
    p_op_dr = df_p[(df_p['Account_Name'].isin(parties)) & (df_p['Type'] == 'OP_BAL')]['Debit'].sum() if not df_p.empty else 0
    total_freight_rev = df_t['Freight'].sum() if not df_t.empty else 0
    p_receipts_cr = df_p[(df_p['Account_Name'].isin(parties)) & (df_p['Type'] != 'OP_BAL')]['Credit'].sum() if not df_p.empty else 0
    net_receivables = (p_op_dr + total_freight_rev) - p_receipts_cr

    # Payables = Broker Op (Cr) + Hired Charges - Payments (Dr)
    brokers = gl("Broker")
    b_op_cr = df_p[(df_p['Account_Name'].isin(brokers)) & (df_p['Type'] == 'OP_BAL')]['Credit'].sum() if not df_p.empty else 0
    total_hired_payable = df_t['HiredCharges'].sum() if not df_t.empty else 0
    b_pay_dr = df_p[(df_p['Account_Name'].isin(brokers)) & (df_p['Type'] != 'OP_BAL')]['Debit'].sum() if not df_p.empty else 0
    net_payables = (b_op_cr + total_hired_payable) - b_pay_dr

    # --- 5. P&L FULL CALCULATION TABLE ---
    st.write("### 📝 Business Profitability Statement")
    admin_only_cost = df_oe[~df_oe['Category'].str.contains('Indrajit|Vishal|Personal', na=False)]['Amount'].sum() if not df_oe.empty else 0
    net_accrual_profit = total_freight_rev - (total_hired_payable + trip_cash_out + admin_only_cost)

    pl_math = {
        "Accounting Particulars": ["(+) Gross Freight Revenue (Billed)", "(-) Hired Charges (Liabilities)", "(-) Own Fleet Direct Expenses", "(-) Office & Admin Expenses", "**NET BUSINESS PROFIT**"],
        "Details": ["From Trips Sheet", "Market Vehicles", "Diesel/Toll/Adv", "Excl. Withdrawals", "Revenue - All Costs"],
        "Amount (₹)": [f"₹{total_freight_rev:,.0f}", f"₹{total_hired_payable:,.0f}", f"₹{trip_cash_out:,.0f}", f"₹{admin_only_cost:,.0f}", f"**₹{net_accrual_profit:,.0f}**"]
    }
    st.table(pd.DataFrame(pl_math))

    # --- 6. VEHICLE PERFORMANCE (NEGATIVE BAR SUPPORT) ---
    st.divider()
    st.subheader("🚛 Fleet Performance (Losses in Red)")
    all_v = gl("Vehicle")
    v_perf = []
    for v in all_v:
        # Net = LR Income - (Diesel/Toll/Adv + Office Maintenance)
        inc = df_t[df_t['Vehicle'] == v]['Freight'].sum() if not df_t.empty else 0
        exp_trip = df_t[df_t['Vehicle'] == v][['Diesel', 'Toll', 'DriverExp']].sum().sum() if not df_t.empty else 0
        exp_off = df_oe[df_oe['Description'].str.contains(v, na=False, case=False)]['Amount'].sum() if not df_oe.empty else 0
        
        net_v = inc - (exp_trip + exp_off)
        v_perf.append({"Vehicle": v, "Performance": net_v})

    v_df = pd.DataFrame(v_perf).sort_values(by="Performance", ascending=False)
    if not v_df.empty:
        v_df['Status'] = ['Profit' if x >= 0 else 'Loss' for x in v_df['Performance']]
        fig_v = px.bar(v_df, x='Vehicle', y='Performance', color='Status', 
                      color_discrete_map={'Profit': '#00d4ff', 'Loss': '#ff4b4b'})
        fig_v.update_layout(showlegend=False, yaxis_title="Profit (+) / Loss (-)")
        st.plotly_chart(fig_v, use_container_width=True)

   # --- 7. FINAL ACCURACY: MULTI-BANK STATUS (TRIP + OFFICE + PAYMENTS) ---
st.divider()
st.write("### 🏦 Multi-Bank Live Status (Auto-Sync)")
my_banks = gl("Bank")

if my_banks:
    b_cols = st.columns(len(my_banks))
    for i, b in enumerate(my_banks):
        
        # SOURCE 1: Payments Sheet (Manual Financial Entries)
        p_bal = 0
        if not df_p.empty:
            # Debit (Aaya) - Credit (Gaya)
            p_bal = df_p[df_p['Account_Name'] == b]['Debit'].sum() - df_p[df_p['Account_Name'] == b]['Credit'].sum()
        
        # SOURCE 2: Trips Sheet (Diesel + Toll + Adv)
        # Yeh tabhi chalega jab Trip sheet mein 'Bank' column mein bank ka naam hoga
        t_bank_exp = 0
        if not df_t.empty:
            # Check column name in your trip sheet
            b_col = 'Bank' if 'Bank' in df_t.columns else ('Paid_Via' if 'Paid_Via' in df_t.columns else None)
            
            if b_col:
                # Sirf us bank se hue OWN Fleet ke kharche (Diesel + Toll + DriverExp)
                t_bank_exp = df_t[df_t[b_col] == b][['Diesel', 'Toll', 'DriverExp']].sum().sum()
        
        # SOURCE 3: Office Expenses (Maintenance etc.)
        o_bank_exp = 0
        if not df_oe.empty:
            # Check if you have 'Mode' or 'Bank' column in Office Expenses
            oe_b_col = 'Mode' if 'Mode' in df_oe.columns else ('Bank' if 'Bank' in df_oe.columns else None)
            if oe_b_col:
                o_bank_exp = df_oe[df_oe[oe_b_col] == b]['Amount'].sum()

        # --- FINAL CALCULATION ---
        # Paisa jo Payments mein hai - Trip ka kharcha - Office ka kharcha
        final_bal = (p_bal - t_bank_exp - o_bank_exp)
        
        with b_cols[i]:
            st.markdown(f"""
                <div style='text-align: center; border: 1px solid #444; border-radius: 8px; padding: 12px; background-color: #1a1a1a;'>
                    <p style='margin:0; color: #888; font-size: 0.9em;'>{b}</p>
                    <h2 style='margin:0; color: {"#00d4ff" if final_bal >= 0 else "#ff4b4b"};'>₹{final_bal:,.0f}</h2>
                    <p style='margin:0; font-size: 0.7em; color: #555;'>Payments - Trips - Office</p>
                </div>
            """, unsafe_allow_html=True)
if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    
    # 1. Category Selection
    m_type = st.selectbox("Category", ["Branch (Company)", "Party", "Broker", "Vehicle", "Driver", "BANK"])
    
    with st.form("m_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        # Default empty values
        name, gst, addr, cont, ac, ifsc, d_name, d_no = "", "", "", "", "", "", "", ""

        if m_type == "Branch (Company)":
            with col1:
                name = st.text_input("Branch Name (e.g. Virat Kim)")
                gst = st.text_input("Branch GST")
                addr = st.text_area("Branch Address")
            with col2:
                ac = st.text_input("Bank A/C No")
                ifsc = st.text_input("Bank IFSC")
                cont = st.text_input("Branch Contact No")

        elif m_type in ["Party", "Broker"]:
            with col1:
                name = st.text_input(f"{m_type} Name")
                gst = st.text_input("GST Number")
            with col2:
                addr = st.text_area("Full Address")
                cont = st.text_input("Contact Number")

        elif m_type == "Driver":
            with col1:
                d_name = st.text_input("Driver Full Name")
            with col2:
                d_no = st.text_input("License Number / Mobile")

        elif m_type == "Vehicle":
            name = st.text_input("Vehicle Number (e.g. GJ05BX1234)")

        if m_type == "BANK":
            with col1:
                name = st.text_input("BANK Name (e.g. BANK OF BARODA)")
                gst = st.text_input("BANK GST")
                addr = st.text_area("BANK Address")
            with col2:
                ac = st.text_input("Bank A/C No")
                ifsc = st.text_input("Bank IFSC")
                cont = st.text_input("BANK Contact No")

        # Save Button
        if st.form_submit_button(f"Save {m_type}"):
            if name or d_name:
                # Order: Type, Name, GST, Address, Contact, A_C_No, IFSC, Driver_Name, Driver_No
                new_row = [m_type, name, gst, addr, cont, ac, ifsc, d_name, d_no]
                if save("masters", new_row):
                    st.success(f"{m_type} Saved!"); st.rerun()
            else:
                st.error("Please enter Name!")

    st.divider()
    # Display existing masters
    if not df_m.empty:
        st.write(f"### Current {m_type} List")
        curr_m = df_m[df_m['Type'] == m_type]
        st.dataframe(curr_m.dropna(axis=1, how='all'), use_container_width=True)
elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    if st.button("🆕 RESET FORM"):
        st.session_state.reset_trigger += 1
        st.session_state.pdf_ready = None
        st.rerun()

    k = st.session_state.reset_trigger
    cp1, cp2, cp3 = st.columns(3)
    
    with cp1:
        sel_br = st.selectbox("Select Branch*", ["Select"] + gl("Branch"), key=f"br_{k}")
        br_code = df_m[df_m['Name'] == sel_br].iloc[0].get('GST', '01') if sel_br != "Select" else "01"
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_mode = st.radio("LR No Mode", ["Auto", "Manual"], horizontal=True, key=f"lrmode_{k}")
        lr_no_auto = f"VIL/26-27/{br_code}/{len(df_t)+1:03d}"
        lr_no = st.text_input("LR Number*", value=lr_no_auto if lr_mode == "Auto" else "", key=f"lrno_{k}")
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"risk_{k}")

    with cp2:
        is_np = st.checkbox("New Party?", key=f"isnp_{k}")
        if is_np:
            bill_pty = st.text_input("Enter New Party Name*", key=f"np_{k}")
        else:
            # gl("Party") ab humne global function mein update kar diya hai 
            # ki wo Broker + Party dono dikhaye
            bill_pty = st.selectbox("Billing Party*", ["Select"] + gl("Party"), key=f"bp_{k}")

        is_nc = st.checkbox("New Consignor?", key=f"isnc_{k}")
        if is_nc:
            cnor_name = st.text_input("Enter New Consignor Name*", key=f"nc_{k}")
        else:
            # Yahan bhi combined list aayegi
            cnor_name = st.selectbox("Consignor Name*", ["Select"] + gl("Party"), key=f"cnor_{k}")
            
        cnor_gst = st.text_input("Consignor GST", key=f"cgst_{k}")
        ins_by = st.selectbox("Insurance Paid By*", ["N/A", "Consignor", "Consignee", "Transporter"], key=f"ins_{k}")

    with cp3:
        # Consignee dropdown mein bhi aksar wahi log hote hain, 
        # isliye yahan bhi dropdown dena better hai
        is_nee = st.checkbox("New Consignee?", key=f"isnee_{k}")
        if is_nee:
            cnee_name = st.text_input("Consignee Name*", key=f"cnee_{k}")
        else:
            cnee_name = st.selectbox("Consignee Name*", ["Select"] + gl("Party"), key=f"cneesel_{k}")
            
        cnee_gst = st.text_input("Consignee GST", key=f"cngst_{k}")
        paid_by = st.selectbox("Freight Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"pby_{k}")
        sel_bank = st.selectbox("Select Bank*", ["Select"] + gl("Bank"), key=f"bank_{k}")
    with st.form(f"lr_form_{k}"):
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", date.today())
            v_list = gl("Vehicle")
            v_no = st.selectbox("Vehicle No*", ["Select"] + v_list) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            
            if v_cat == "Own Fleet":
                d_list = gl("Driver")
                sel_driver = st.selectbox("Driver Name*", ["Select"] + d_list)
                br_name = "OWN"
            else:
                sel_driver = "Market Driver"
                br_name = st.selectbox("Broker*", ["Select"] + gl("Broker"))
                
            ship_to = st.text_area("Ship To Address")

        with c2:
            fl, tl = st.text_input("From City"), st.text_input("To City")
            mat, pkg = st.text_input("Material"), st.selectbox("Packaging", ["Drums", "Bags", "Boxes", "Loose", "Pallets"])
            inv_no = st.text_input("Invoice No & Date")

        with c3:
            n_wt, c_wt = st.number_input("Net Wt", min_value=0.0), st.number_input("Chg Wt", min_value=0.0)
            fr_amt = st.number_input("Total Freight*", min_value=0.0)
            show_fr = st.checkbox("Show Freight in PDF?", value=True)
            if v_cat == "Own Fleet": 
                dsl = st.number_input("Diesel", min_value=0.0)
                toll = st.number_input("Toll", min_value=0.0)
                drv = st.number_input("Driver Adv", min_value=0.0)
        
                # Masters se Bank ki list uthayega
                paid_via = st.selectbox("Kharcha Kis Bank Se Huva?*", ["Select"] + gl("Bank"), key=f"p_via_{k}")
            else: 
                hc = st.number_input("Hired Charges")
                dsl = toll = drv = 0.0

        # --- YE FORM KA END HAI ---
        # --- 🚀 FINAL & COMPLETE SAVE LOGIC (Sahi Order Mein) ---
        if st.form_submit_button("🚀 SAVE LR"):
            if bill_pty and bill_pty != "Select" and fr_amt > 0:
                # 1. Profit Calculation
                prof = (fr_amt - (hc if v_cat == "Market Hired" else (dsl+toll+drv)))
                
                # 2. Trips Sheet Row (With 26th Column: paid_via)
                row = [
                    str(d), lr_no, v_cat, bill_pty, cnor_name, cnor_gst, "", 
                    cnee_name, cnee_gst, "", mat, n_wt, c_wt, v_no, sel_driver, 
                    br_name, fl, tl, fr_amt, 
                    (hc if v_cat == "Market Hired" else 0.0), 
                    dsl, drv, toll, 0, prof, 
                    paid_via # <-- Column 26: Trip sheet mein bank jayega
                ]
                
                if save("trips", row):
                    # --- A. NEW PARTY MASTER UPDATE ---
                    if is_np and bill_pty not in gl("Party"):
                        save("masters", ["Party", bill_pty])
                    
                    # --- B. NEW CONSIGNOR MASTER UPDATE ---
                    if is_nc and cnor_name not in gl("Consignor"):
                        save("masters", ["Consignor", cnor_name])

                    # --- C. BANK BALANCE MINUS (PAYMENTS AUTO-ENTRY) ---
                    if v_cat == "Own Fleet" and paid_via != "Select":
                        total_trip_exp = dsl + toll + drv
                        if total_trip_exp > 0:
                            # 8 Columns order as per your ERP
                            bank_payment_row = [
                                str(d),                     # 1. Date
                                f"Trip Exp ({v_no})",       # 2. Account_Name
                                "Payment (Out)",            # 3. Type
                                total_trip_exp,             # 4. Amount
                                "Bank",                     # 5. Mode
                                f"Diesel/Toll for LR: {lr_no}", # 6. Remarks
                                lr_no,                      # 7. LR_Ref
                                paid_via                    # 8. Bank_Used (Dashboard sync)
                            ]
                            save("payments", bank_payment_row)
                    
                    # --- D. PDF & SUCCESS DATA ---
                    br_info = df_m[df_m['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, 
                        "Cnor": cnor_name, "CnorGST": cnor_gst, 
                        "Cnee": cnee_name, "CneeGST": cnee_gst, 
                        "BillP": bill_pty, "From": fl, "To": tl, 
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, 
                        "Freight": fr_amt, "PaidBy": paid_by, "Risk": risk, 
                        "InvNo": inv_no, "ShipTo": ship_to, "show_fr": show_fr, "InsBy": ins_by,
                        "BranchName": sel_br,
                        "BranchGST": br_info.get('GST', 'N/A'),
                        "BranchAddr": br_info.get('Address', 'N/A'),
                        "BankName": br_info.get('Name', 'N/A'),
                        "BankAC": br_info.get('A_C_No', 'N/A'),
                        "BankIFSC": br_info.get('IFSC', 'N/A')
                    }
                    st.success(f"✅ LR {lr_no} Saved! Party & Bank Balance Updated.")
                    st.rerun()
            else:
                st.error("Please fill Party Name and Freight!")
                    
                    # 3. PDF ke liye Branch/Company ka sara data bundle karna
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, 
                        "Cnor": cnor_name, "CnorGST": cnor_gst, 
                        "Cnee": cnee_name, "CneeGST": cnee_gst, 
                        "BillP": bill_pty, "From": fl, "To": tl, 
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, 
                        "Freight": fr_amt, "PaidBy": paid_by, "Risk": risk, 
                        "InvNo": inv_no, "ShipTo": ship_to, "show_fr": show_fr, "InsBy": ins_by,
                        "BranchName": sel_br,
                        "BranchGST": br_info.get('GST', 'N/A'),
                        "BranchAddr": br_info.get('Address', 'N/A'),
                        "BankName": br_info.get('Name', 'N/A'),
                        "BankAC": br_info.get('A_C_No', 'N/A'),
                        "BankIFSC": br_info.get('IFSC', 'N/A')
                    }
                    st.success("LR Saved and Masters Updated! and Bank Balance Updated!")
                    st.rerun()
            else:
                st.error("Please fill Party Name and Freight!")
    # --- YE LINE FORM KE BAHAR (LEFT MARGIN SE MATCH KAREIN) ---
    if st.session_state.pdf_ready:
        st.divider()
        st.download_button("📥 DOWNLOAD LR PDF", generate_lr_pdf(st.session_state.pdf_ready, st.session_state.pdf_ready.get('show_fr', True)), f"LR_{st.session_state.pdf_ready['LR No']}.pdf")    
elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    if not df_t.empty:
        # Columns clean karein taaki matching mein galti na ho
        df_t.columns = [str(c).strip() for c in df_t.columns]
        
        for i, row in df_t.iterrows():
            # 1. Branch/Bank details fetch karna (kyunki trips sheet mein bank info nahi hoti)
            br_name = row.get('Branch', 'Select') 
            br_row = df_m[df_m['Name'] == br_name]
            br_info = br_row.iloc[0] if not br_row.empty else {}

            # 2. Dictionary taiyar karein jo PDF function ko chahiye
            lr_data_for_pdf = {
                "LR No": row.get('LR No', 'N/A'),
                "Date": row.get('Date', ''),
                "Vehicle": row.get('Vehicle', ''),
                "Risk": row.get('Risk', 'At Owner Risk'),
                "Cnor": row.get('Consignor', 'N/A'),
                "Cnee": row.get('Consignee', 'N/A'),
                "BillP": row.get('Party', 'N/A'),
                "Material": row.get('Material', 'N/A'),
                "Pkg": row.get('Pkg', 'N/A'),
                "NetWt": row.get('NetWt', 0),
                "ChgWt": row.get('ChgWt', 0),
                "Freight": row.get('Freight', 0),
                "PaidBy": row.get('PaidBy', 'N/A'),
                "From": row.get('From', ''),
                "To": row.get('To', ''),
                "ShipTo": row.get('ShipTo', 'N/A'),
                "InsBy": row.get('InsBy', 'N/A'),
                "BranchName": br_name if br_name != 'Select' else "VIRAT LOGISTICS",
                "BranchAddr": br_info.get('Address', 'N/A'),
                "BranchGST": br_info.get('GST', 'N/A'),
                "BankName": br_info.get('Name', 'N/A'),
                "BankAC": br_info.get('A_C_No', 'N/A'),
                "BankIFSC": br_info.get('IFSC', 'N/A')
            }

            with st.expander(f"LR: {lr_data_for_pdf['LR No']} | {lr_data_for_pdf['Cnee']}"):
                try:
                    # 3. Corrected dictionary pass karein
                    pdf_output = generate_lr_pdf(lr_data_for_pdf, True)
                    st.download_button(
                        label="📥 DOWNLOAD PDF",
                        data=pdf_output,
                        file_name=f"LR_{lr_data_for_pdf['LR No']}.pdf",
                        key=f"dl_reg_{i}"
                    )
                except Exception as e:
                    st.error(f"PDF Error: {str(e)}")
        
        st.dataframe(df_t)
        
elif menu == "4. Financials":
    st.header("⚖️ Party & Broker Full Statement")
    df_p = load("payments")
    df_t = load("trips")
    
    if not df_t.empty: df_t.columns = [str(c).strip() for c in df_t.columns]
    if not df_p.empty: df_p.columns = [str(c).strip() for c in df_p.columns]
        
    all_accs = sorted(gl("Party") + gl("Broker") + gl("Driver") + gl("Bank"))
    my_banks = gl("Bank") # Sirf banks ki list dropdown ke liye
    
    t1, t2 = st.tabs(["💸 Add Transaction", "📖 Full Statement"])
    
    with t1:
        # Fixed Indentation here
        with st.form("p_form_new", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            with f1: 
                p_d = st.date_input("Date", date.today(), key="fin_date")
                acc = st.selectbox("Select Account*", ["Select"] + all_accs, key="fin_acc")
            with f2: 
                p_amt = st.number_input("Amount (₹)*", min_value=0.0, key="fin_amt")
                # Creditor OP Bal logic: Debit = Lena hai, Credit = Dena hai
                entry_direction = st.selectbox("Entry Type*", [
                    "Credit (Dena Hai / Receipt Recd / Op Bal)", 
                    "Debit (Lena Hai / Payment Paid / Freight)"
                ], key="fin_dir")
            with f3: 
                p_m = st.selectbox("Payment Mode", ["NEFT", "Cash", "UPI", "Cheque", "Transfer"], key="fin_mode")
                # Naya Logic: Kis bank se paisa gaya/aaya
                bank_used = st.selectbox("Bank/Cash Account Used*", ["N/A"] + my_banks, key="fin_bank_used")
            
            p_r = st.text_input("Ref / Remarks", key="fin_rem")
            
            if st.form_submit_button("🚀 Save Transaction"):
                if acc != "Select" and p_amt > 0:
                    dr = p_amt if "Debit" in entry_direction else 0
                    cr = p_amt if "Credit" in entry_direction else 0
                    
                    # Row: Date, Account_Name, Type, Debit, Credit, Mode, Remarks, Bank_Used
                    new_row = [str(p_d), acc, "Manual Entry", dr, cr, p_m, p_r, bank_used]
                    
                    if save("payments", new_row):
                        # Double Entry Logic: Agar bank used hai, toh bank account mein opposite entry auto-save hogi
                        if bank_used != "N/A":
                            # Bank ke liye opposite entry (Bank Dr if Party Cr, and vice versa)
                            bank_row = [str(p_d), bank_used, "Bank Adjustment", cr, dr, p_m, f"Ref: {acc} - {p_r}", "Self"]
                            save("payments", bank_row)
                        
                        st.success(f"Entry Saved for {acc}!"); st.rerun()
                else:
                    st.error("Account aur Amount select karein!")

    with t2:
        sel_a = st.selectbox("Select Account for Statement", ["Select"] + all_accs, key="s4_final")
        ledger_entries = []
        
        if sel_a != "Select":
            # 1. Opening Balance logic from payments sheet
            if not df_p.empty:
                op_data = df_p[(df_p['Account_Name'] == sel_a) & (df_p['Type'] == 'OP_BAL')]
                for _, r in op_data.iterrows():
                    # Dr and Cr columns check
                    dr_val = pd.to_numeric(r.get('Debit', 0), errors='coerce')
                    cr_val = pd.to_numeric(r.get('Credit', 0), errors='coerce')
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': '💰 OPENING BALANCE', 
                        'Debit': dr_val, 'Credit': cr_val, 'Bank': 'N/A'
                    })

            # 2. Trip Data (Freight and Hired Charges)
            if not df_t.empty:
                # Party Freight (Debit)
                p_trips = df_t[df_t['Party'] == sel_a]
                for _, r in p_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} (Freight Bill)", 
                        'Debit': pd.to_numeric(r.get('Freight', 0), errors='coerce'), 'Credit': 0, 'Bank': 'N/A'
                    })
                # Broker Hired (Credit)
                b_trips = df_t[df_t['Broker'] == sel_a]
                for _, r in b_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} (Hired Charges)", 
                        'Debit': 0, 'Credit': pd.to_numeric(r.get('HiredCharges', 0), errors='coerce'), 'Bank': 'N/A'
                    })

            # --- 3. Payments Data (Receipts and Payments) ---
            if not df_p.empty:
                p_entries = df_p[(df_p['Account_Name'] == sel_a) & (df_p['Type'] != 'OP_BAL')]
                for _, r in p_entries.iterrows():
                    # Dr aur Cr value ko numbers mein convert karein
                    dr_val = pd.to_numeric(r.get('Debit', 0), errors='coerce')
                    cr_val = pd.to_numeric(r.get('Credit', 0), errors='coerce')
        
                    # Logic: Agar Debit column mein entry hai toh wo humne "Pay" kiya hai, 
                    # Agar Credit mein hai toh humein "Receive" hua hai.
                    entry_type = "Payment (Out) 💸" if dr_val > 0 else "Receipt (In) 💰"
                    if dr_val > 0 and cr_val > 0: entry_type = "Adjustment 🔄" # Dono ho toh adjustment

                    ledger_entries.append({
                    'Date': r.get('Date', date.today()), 
                    'Particulars': f"{entry_type} | {r.get('Mode','Cash')} - {r.get('Remarks','')}", 
                    'Debit': dr_val, 
                    'Credit': cr_val,
                    'Bank': r.get('Bank_Used', 'N/A')
                 })

            if ledger_entries:
                full_df = pd.DataFrame(ledger_entries)
                full_df['Date'] = pd.to_datetime(full_df['Date']).dt.date
                full_df = full_df.sort_values(by=['Date'])
                # Running Balance: Debit - Credit
                full_df['Balance'] = (full_df['Debit'] - full_df['Credit']).cumsum()
                
                st.write(f"#### 📖 Ledger Statement: {sel_a}")
                st.dataframe(full_df, use_container_width=True, hide_index=True)
                
                net_bal = full_df['Debit'].sum() - full_df['Credit'].sum()
                if net_bal > 0:
                    st.success(f"Net Receivable (Lena Hai): ₹{abs(net_bal):,.2f}")
                elif net_bal < 0:
                    st.warning(f"Net Payable (Dena Hai): ₹{abs(net_bal):,.2f}")
                else:
                    st.success("Account Settled (0 Balance)")
            else:
                st.info("No records found.")
elif menu == "5. Business Insights":
    st.markdown("<h2 style='text-align: center; color: #00d4ff;'>📈 BUSINESS INSIGHTS & ANALYTICS</h2>", unsafe_allow_html=True)

    # --- 1. DATA LOADING (Yahan fix hai - Data load hona zaroori hai) ---
    df_p = load("payments")
    df_t = load("trips")
    df_oe = load("office_expenses")
    df_m = load("masters")

    # Column Standardizing (Spaces hatane ke liye)
    for dff in [df_p, df_t, df_oe]:
        if not dff.empty: 
            dff.columns = [str(c).strip() for c in dff.columns]

    if df_t.empty:
        st.warning("Trips sheet khali hai. Analytics ke liye data zaroori hai.")
    else:
        # --- 2. VEHICLE PROFITABILITY REPORT (Accuracy Fixed) ---
        st.subheader("🚛 Detailed Fleet Performance")
        all_v = gl("Vehicle")
        v_analytics = []

        for v in all_v:
            # Income (LR se)
            v_inc = df_t[df_t['Vehicle'] == v]['Freight'].sum()
            # Trip Exp (Diesel/Toll jo Own Fleet mein hai)
            v_trip_exp = df_t[df_t['Vehicle'] == v][['Diesel', 'Toll', 'DriverExp']].sum().sum()
            # Office Maintenance (Description mein gadi number match karke)
            v_maint = 0
            if not df_oe.empty:
                v_maint = df_oe[df_oe['Description'].str.contains(v, na=False, case=False)]['Amount'].sum()
            
            net_v = v_inc - (v_trip_exp + v_maint)
            v_analytics.append({
                "Vehicle": v,
                "Income": v_inc,
                "Direct Costs": v_trip_exp + v_maint,
                "Net Profit/Loss": net_v
            })

        v_df = pd.DataFrame(v_analytics).sort_values(by="Net Profit/Loss", ascending=False)
        st.dataframe(v_df.style.format({"Income": "₹{:,.0f}", "Direct Costs": "₹{:,.0f}", "Net Profit/Loss": "₹{:,.0f}"}), use_container_width=True)

        # --- 3. PARTY REVENUE & RECEIVABLES ---
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏢 Party Revenue Share")
            party_rev = df_t.groupby('Party')['Freight'].sum().reset_index()
            fig_p = px.pie(party_rev, values='Freight', names='Party', hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig_p, use_container_width=True)

        with col2:
            st.subheader("⏳ Party Outstanding (Receivables)")
            if not df_p.empty:
                parties_list = gl("Party")
                outstanding = []
                for p in parties_list:
                    # Logic: Op Dr + Freight - Receipts Cr
                    p_op = df_p[(df_p['Account_Name'] == p) & (df_p['Type'] == 'OP_BAL')]['Debit'].sum()
                    p_freight = df_t[df_t['Party'] == p]['Freight'].sum()
                    p_receipts = df_p[(df_p['Account_Name'] == p) & (df_p['Type'] != 'OP_BAL')]['Credit'].sum()
                    bal = (p_op + p_freight) - p_receipts
                    if bal > 1: # ₹1 se zyada balance hai toh dikhao
                        outstanding.append({"Party": p, "Balance": bal})
                
                if outstanding:
                    out_df = pd.DataFrame(outstanding).sort_values(by="Balance", ascending=False)
                    fig_out = px.bar(out_df, x='Party', y='Balance', color_discrete_sequence=['#ff9f43'])
                    st.plotly_chart(fig_out, use_container_width=True)
                else:
                    st.write("Koi pending payment nahi hai.")

        # --- 4. MONTHLY GROWTH TREND ---
        st.divider()
        st.subheader("📅 Monthly Business Trend")
        try:
            df_t['Date'] = pd.to_datetime(df_t['Date'], errors='coerce')
            df_t['Month'] = df_t['Date'].dt.strftime('%Y-%m')
            monthly = df_t.groupby('Month')['Freight'].sum().reset_index()
            fig_line = px.line(monthly, x='Month', y='Freight', markers=True, title="Revenue Growth")
            st.plotly_chart(fig_line, use_container_width=True)
        except:
            st.info("Trips sheet mein Date format check karein.")
elif menu == "6. Expense Manager":
    st.header("🏢 Office & Personal Expense Manager")
    
    # 1. DATA LOADING
    df_oe = load("office_expenses")
    df_m_data = load("masters") 

    # --- DROP DOWN LISTS (From Masters) ---
    if not df_m_data.empty:
        # Bank list loading (Type 'Bank' or 'BANK')
        b_list = sorted(df_m_data[df_m_data['Type'].str.contains('Bank', case=False, na=False)]['Name'].unique().tolist())
        # Vehicle list loading (Type 'Vehicle' or 'VEHICLE')
        v_list = sorted(df_m_data[df_m_data['Type'].str.contains('Vehicle', case=False, na=False)]['Name'].unique().tolist())
    else:
        b_list = ["Cash"]
        v_list = []

    tab_add, tab_view, tab_indrajit, tab_vishal = st.tabs([
        "➕ Add Expense", "📊 Office Expenses", "👤 Indrajit Khata", "👤 Vishal Khata"
    ])
    
    with tab_add:
        # Form shuru
        with st.form("office_exp_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                e_date = st.date_input("Date", date.today())
                e_cat = st.selectbox("Category", [
                    "Office Rent", "Electricity", "Staff Salary", 
                    "Stationery", "Tea/Coffee", "Maintenance", 
                    "Driver Salary", "Vehicle Maintenance", 
                    "Indrajit Personal", "Vishal Personal", "Others"
                ])
                
                # LOGIC REMOVED: Ab dropdown hamesha enabled rahega
                sel_v_no = st.selectbox("Select Vehicle No (If any)", 
                                        options=["N/A"] + v_list if v_list else ["N/A"])

            with col2:
                e_amt = st.number_input("Amount (₹)", min_value=0.0, step=1.0)
                # Actual Banks from Master
                e_bank = st.selectbox("Paid From (Bank/Cash)", b_list if b_list else ["Cash"])
            
            e_desc = st.text_input("Description / Remarks")
            
            # Form Submit Button (Zaroori hai)
            submitted = st.form_submit_button("🚀 Save Expense")
            
            if submitted:
                if e_amt > 0:
                    # Row data as per your CSV structure
                    new_row = [str(e_date), e_cat, e_desc, e_amt, e_bank, sel_v_no]
                    
                    if save("office_expenses", new_row):
                        st.success(f"Entry Saved Successfully!")
                        st.rerun()
                else:
                    st.error("Please enter a valid Amount!")

    # --- VIEW & LEDGERS ---
    with tab_view:
        st.subheader("General Office Expenses")
        if not df_oe.empty:
            office_df = df_oe[~df_oe['Category'].str.contains('Indrajit|Vishal', na=False)]
            st.dataframe(office_df, use_container_width=True, hide_index=True)
            st.info(f"Total Office Exp: ₹{pd.to_numeric(office_df['Amount'], errors='coerce').sum():,.2f}")

    with tab_indrajit:
        st.subheader("👤 Indrajit Personal Ledger")
        if not df_oe.empty:
            ind_df = df_oe[df_oe['Category'] == "Indrajit Personal"]
            st.metric("Total Withdrawal", f"₹{pd.to_numeric(ind_df['Amount'], errors='coerce').sum():,.0f}")
            st.dataframe(ind_df, use_container_width=True)

    with tab_vishal:
        st.subheader("👤 Vishal Personal Ledger")
        if not df_oe.empty:
            vis_df = df_oe[df_oe['Category'] == "Vishal Personal"]
            st.metric("Total Withdrawal", f"₹{pd.to_numeric(vis_df['Amount'], errors='coerce').sum():,.0f}")
            st.dataframe(vis_df, use_container_width=True)
elif menu == "7. Driver Khata":
    st.header("🚛 Driver Khata & Trip Settlement")
    df_dk = load("driver_khata")
    df_t = load("trips")
    drivers = gl("Driver")
    tab_entry, tab_settle = st.tabs(["➕ Add Entry (Salary/Extra)", "📖 Driver Settlement & Ledger"])
    
    with tab_entry:
        with st.form("driver_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                d_date = st.date_input("Date", date.today())
                d_name = st.selectbox("Select Driver*", ["Select"] + drivers)
            with c2:
                d_type = st.selectbox("Entry Type*", ["Salary Paid", "Personal Advance (Extra)", "Other Credit"])
                d_amt = st.number_input("Amount (₹)*", min_value=0.0)
            with c3:
                d_note = st.text_input("Remarks")
            if st.form_submit_button("Save Entry"):
                if d_name != "Select" and d_amt > 0:
                    if save("driver_khata", [str(d_date), d_name, "N/A", "Debit", d_amt, d_note]):
                        st.success(f"Saved for {d_name}"); st.rerun()

    with tab_settle:
        sel_d = st.selectbox("Choose Driver for Final Settlement", ["Select"] + drivers)
        if sel_d != "Select":
            st.divider()
            st.write(f"### 🔍 Trip Summary for {sel_d}")
            if not df_t.empty:
                df_t.columns = [str(c).strip() for c in df_t.columns]
                d_trips = df_t[df_t['Driver'] == sel_d].copy()
                if not d_trips.empty:
                    for c in ['Diesel', 'DriverExp', 'Toll']:
                        if c in d_trips.columns:
                            d_trips[c] = pd.to_numeric(d_trips[c], errors='coerce').fillna(0)
                    t_adv = d_trips['DriverExp'].sum()
                    t_dsl = d_trips['Diesel'].sum()
                    c1, c2 = st.columns(2)
                    c1.metric("Trip Advance (Pending)", f"₹{t_adv:,.0f}")
                    c2.metric("Trip Diesel (Total)", f"₹{t_dsl:,.0f}")
                    if st.button(f"📥 Import ₹{t_adv} to Personal Ledger"):
                        if save("driver_khata", [str(date.today()), sel_d, "Trips", "Debit", t_adv, "Auto-Import from Trips"]):
                            st.success("Trip Advance Imported!"); st.rerun()
                else:
                    st.info("No trip history.")

            st.write(f"### 📜 Personal Ledger")
            if not df_dk.empty:
                df_dk.columns = [str(c).strip() for c in df_dk.columns]
                d_hist = df_dk[df_dk['Driver_Name'] == sel_d]
                total_p = pd.to_numeric(d_hist['Amount'], errors='coerce').sum() if not d_hist.empty else 0
                st.warning(f"Total Personal Dues: ₹{total_p:,.2f}")
                st.dataframe(d_hist, use_container_width=True, hide_index=True)
                
elif menu == "8. Monthly Bill":
    st.header("🧾 Monthly Billing & Invoice Generation")
    
    # 1. Branch selection
    sel_br = st.selectbox("Select Billing Branch*", ["Select"] + gl("Branch"), key="bill_br_8")
    
    br_info = {}
    if sel_br != "Select":
        mask = (df_m['Type'].str.contains('Branch', case=False, na=False)) & (df_m['Name'] == sel_br)
        temp_df = df_m[mask]
        if not temp_df.empty:
            br_info = temp_df.iloc[0].to_dict()

    # 2. Party Selection
    sel_party = st.selectbox("Select Party to Bill*", ["Select"] + gl("Party"), key="party_bill_8")
    
    if sel_party != "Select":
        # SAFE FILTERING: Check karein ki column 'Party' hai ya 'Party Name'
        col_to_use = 'Party' if 'Party' in df_t.columns else 'Party Name'
        
        try:
            party_lrs = df_t[df_t[col_to_use] == sel_party]
            
            if not party_lrs.empty:
                st.subheader(f"Pending LRs for {sel_party}")
                selected_lrs = []
                for i, row in party_lrs.iterrows():
                    # Vehicle No column check logic
                    v_col = 'Vehicle No' if 'Vehicle No' in df_t.columns else 'Vehicle'
                    
                    c1, c2, c3 = st.columns([1, 2, 1])
                    with c1:
                        pick = st.checkbox(f"Select", key=f"sel_{i}")
                    with c2:
                        st.write(f"LR: {row['LR No']} | Date: {row['Date']}")
                    with c3:
                        st.write(f"Amt: {row['Freight']}")
                    
                    if pick:
                        # PDF ke liye zaroori data bundle
                        selected_lrs.append({
                            "LR No": row['LR No'],
                            "Date": row['Date'],
                            "Vehicle No": row.get(v_col, 'N/A'),
                            "Freight": row['Freight']
                        })
                
                if selected_lrs:
                    st.divider()
                    total_bill = sum(float(item['Freight']) for item in selected_lrs)
                    st.info(f"Total Bill Amount: ₹{total_bill}")
                    
                    inv_no = st.text_input("Invoice Number", value=f"VL/INV/{len(df_t):03d}")
                    inv_date = st.date_input("Invoice Date", date.today())
                    
                    if st.button("📄 Generate Tax Invoice"):
                        # Branch aur Bank Details fetching
                        st.session_state.inv_ready = {
                            "InvNo": inv_no,
                            "InvDate": str(inv_date),
                            "Party": sel_party,
                            "LRs": selected_lrs,
                            "Total": total_bill,
                            "BranchName": sel_br,
                            "BranchGST": br_info.get('GST', 'N/A'),
                            "BranchAddr": br_info.get('Address', 'N/A'),
                            "BankName": br_info.get('Bank_Name', 'N/A'),
                            "BankAC": br_info.get('A_C_No', 'N/A'),
                            "BankIFSC": br_info.get('IFSC', 'N/A')
                        }
                        st.success("Invoice Ready!")
            else:
                st.warning(f"No records found for {sel_party} in Trips sheet.")
        except KeyError:
            st.error(f"Column '{col_to_use}' not found in Trips sheet. Please check your Google Sheet headers.")

    # 3. Download Section
    if st.session_state.get('inv_ready'):
        pdf_data = generate_invoice_pdf(st.session_state.inv_ready)
        st.download_button("📥 DOWNLOAD INVOICE PDF", pdf_data, f"Invoice_{st.session_state.inv_ready['InvNo']}.pdf")

