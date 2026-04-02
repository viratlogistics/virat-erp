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

def load(name):
    try:
        ws = sh.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
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
    pdf.ln(5)

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

# --- UPDATED SIDEBAR MENU (Professional & Clean) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4090/4090434.png", width=80) # Ek transport icon
    st.title("VIRAT LOGISTICS")
    menu = option_menu(
        menu_title="Main Menu", 
        options=[
            "0. Dashboard", "1. Masters Setup", "2. LR Entry", "3. LR Register", 
            "4. Financials", "5. Business Insights", "6. Expense Manager", 
            "7. Driver Khata", "8. Monthly Bill", "9. Cash & Bank"
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
    st.markdown("<h2 style='text-align: center; color: #00d4ff;'>📊 VIRAT LOGISTICS STRATEGIC DASHBOARD</h2>", unsafe_allow_html=True)

    # --- 1. FY SELECTION ---
    available_fy = ["2024-25", "2025-26", "2026-27"]
    selected_fy = st.selectbox("📅 Select Financial Year", available_fy, index=2)

    # --- 2. DATA LOADING & FILTERING ---
    df_p = load("payments")
    df_oe = load("office_expenses")
    
    def get_fy(date_str):
        try:
            dt = pd.to_datetime(date_str)
            return f"{dt.year}-{str(dt.year+1)[2:]}" if dt.month >= 4 else f"{dt.year-1}-{str(dt.year)[2:]}"
        except: return "Unknown"

    df_tf = df_t.copy()
    if not df_tf.empty:
        df_tf['FY'] = df_tf['Date'].apply(get_fy)
        df_tf = df_tf[df_tf['FY'] == selected_fy]

    df_pf = df_p.copy()
    if not df_pf.empty:
        df_pf['FY'] = df_pf['Date'].apply(get_fy)
        df_pf = df_pf[df_pf['FY'] == selected_fy]

    # --- 3. CORE CALCULATIONS (New Strategic Logic) ---

    total_rev = 0; own_profit = 0; hired_profit = 0; office_exp = 0
    total_opening_cash = 0; total_op_receivable = 0; total_op_payable = 0
    cash_in = 0; cash_out_total = 0; trip_actual_exp = 0

    # A. TRIP PERFORMANCE (Trips Sheet + Payments Sheet Linking)
    if not df_tf.empty:
        # Numeric Clean-up
        for c in ['Freight', 'HiredCharges']:
            if c in df_tf.columns: df_tf[c] = pd.to_numeric(df_tf[c], errors='coerce').fillna(0)
        
        total_rev = df_tf['Freight'].sum()
        
        # 1. MARKET GADI PROFIT (Freight - Hired Charges)
        df_mkt = df_tf[df_tf['Type'].str.contains('Market|Hired', case=False, na=False)]
        hired_profit = df_mkt['Freight'].sum() - df_mkt['HiredCharges'].sum()
        
        # 2. OWN FLEET REVENUE
        df_own = df_tf[df_tf['Type'].str.contains('Own', case=False, na=False)]
        own_rev = df_own['Freight'].sum()

        # 3. ACTUAL OWN FLEET EXPENSES (From Payments Sheet with 'LR:' tag)
        if not df_pf.empty:
            df_pf['Amount'] = pd.to_numeric(df_pf['Amount'], errors='coerce').fillna(0)
            # Sirf wo kharche jo kisi LR se link kiye gaye hain
            trip_actual_exp = df_pf[df_pf['Remarks'].str.contains('LR:', na=False)]['Amount'].sum()
            own_profit = own_rev - trip_actual_exp
            
            # 4. OFFICE/ADMIN EXPENSES (Expense category but No LR tag)
            exp_categories = gl("Expense")
            office_exp_mask = (df_pf['Account_Name'].isin(exp_categories)) & (~df_pf['Remarks'].str.contains('LR:', na=False))
            office_exp = df_pf[office_exp_mask]['Amount'].sum()
        else:
            own_profit = own_rev

    # B. CASH & OUTSTANDING LOGIC
    if not df_p.empty:
        # Opening Balances
        op_entries = df_p[df_p['Type'] == 'OP_BAL']
        if not op_entries.empty:
            cash_bank_op = op_entries[op_entries['Account_Name'].str.contains('BANK|CASH', case=False, na=False)]
            total_opening_cash = cash_bank_op['Amount'].sum()
            
            other_op = op_entries[~op_entries['Account_Name'].str.contains('BANK|CASH', case=False, na=False)]
            for _, r in other_op.iterrows():
                val = pd.to_numeric(r['Amount'], errors='coerce')
                if val < 0: total_op_payable += abs(val)
                else: total_op_receivable += val

        # Current FY Cash Flow
        if not df_pf.empty:
            cash_in = df_pf[(df_pf['Type'].str.contains('Receipt|In', case=False, na=False)) & (df_pf['Type'] != 'OP_BAL')]['Amount'].sum()
            cash_out_total = df_pf[(df_pf['Type'].str.contains('Payment|Out', case=False, na=False)) & (df_pf['Type'] != 'OP_BAL')]['Amount'].sum()

    # C. FINAL TOTALS
    total_net_profit = (own_profit + hired_profit) - office_exp
    cash_hand_balance = (total_opening_cash + cash_in) - cash_out_total
    current_year_pending = total_rev - cash_in
    total_to_receive = total_op_receivable + max(0, current_year_pending)
    
    # --- 4. DISPLAY UI ---
    st.write("### 💰 Financial Status (Cash & Dues)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cash In Hand", f"₹{cash_hand_balance:,.0f}", delta=f"Op: ₹{total_opening_cash:,.0f}")
    m2.metric("Total Receivable", f"₹{total_to_receive:,.0f}", delta="Paisa Lena Hai")
    m3.metric("Total Payable", f"₹{total_op_payable:,.0f}", delta="Paisa Dena Hai", delta_color="inverse")
    m4.metric("Yearly Revenue", f"₹{total_rev:,.0f}", delta="Billed")
    
    st.divider()
    st.write("### 🚛 Business Performance")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Net Profit", f"₹{total_net_profit:,.0f}", delta="Total")
    p2.metric("Own Fleet Net", f"₹{own_profit:,.0f}", delta="After Exp")
    p3.metric("Market Commission", f"₹{hired_profit:,.0f}", delta="Hired")
    p4.metric("Admin/Office Exp", f"₹{office_exp:,.0f}", delta_color="inverse")

    st.divider()

    # --- 5. CHARTS & TABLES ---
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("💰 Cash Flow Breakdown")
        cf_data = pd.DataFrame({'Category': ['Bank/Cash Bal', 'Receipts', 'Total Outflow'], 'Amount': [total_opening_cash, cash_in, cash_out_total]})
        fig_pie = px.pie(cf_data, values='Amount', names='Category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_b:
        st.subheader("🚛 Own Vehicle Income (Revenue)")
        if not df_tf.empty:
            df_v = df_tf[df_tf['Type'].str.contains('Own', case=False, na=False)]
            if not df_v.empty:
                v_perf = df_v.groupby('Vehicle')['Freight'].sum().reset_index()
                fig_bar = px.bar(v_perf, x='Vehicle', y='Freight', text_auto='.2s', color_discrete_sequence=['#00d4ff'])
                st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()
    st.subheader("⏳ Party-wise Pending Balance")
    if not df_tf.empty or total_op_receivable > 0:
        p_due = df_tf.groupby('Party')['Freight'].sum().reset_index() if not df_tf.empty else pd.DataFrame(columns=['Party', 'Freight'])
        if not op_entries.empty:
            party_op_list = op_entries[~op_entries['Account_Name'].str.contains('BANK|CASH', case=False, na=False)][['Account_Name', 'Amount']]
            party_op_list.columns = ['Party', 'Opening_Bal']
            p_due = pd.merge(p_due, party_op_list, on='Party', how='outer').fillna(0)
        else: p_due['Opening_Bal'] = 0
        
        p_due['Total_Billed'] = p_due['Freight'] + p_due['Opening_Bal']
        p_rec = df_p[df_p['Type'].str.contains('Receipt', case=False, na=False)].groupby('Account_Name')['Amount'].sum().reset_index()
        p_rec.columns = ['Party', 'Received']
        
        final_due = pd.merge(p_due, p_rec, on='Party', how='left').fillna(0)
        final_due['Pending'] = final_due['Total_Billed'] - final_due['Received']
        display_due = final_due[abs(final_due['Pending']) > 1].sort_values('Pending', ascending=False)
        
        st.dataframe(display_due[['Party', 'Opening_Bal', 'Freight', 'Total_Billed', 'Received', 'Pending']].style.format({
            "Opening_Bal": "₹{:,.0f}", "Freight": "₹{:,.0f}", "Total_Billed": "₹{:,.0f}", "Received": "₹{:,.0f}", "Pending": "₹{:,.0f}"
        }).set_properties(**{'color': '#00d4ff', 'font-weight': 'bold'}), use_container_width=True)
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
        br_info = df_m[df_m['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
        br_code = br_info.get('GST', '01') if sel_br != "Select" else "01"
        
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_mode = st.radio("LR No Mode", ["Auto", "Manual"], horizontal=True, key=f"lrmode_{k}")
        lr_no_auto = f"VIL/26-27/{br_code}/{len(df_t)+1:03d}"
        lr_no = st.text_input("LR Number*", value=lr_no_auto if lr_mode == "Auto" else "", key=f"lrno_{k}")
        risk = st.radio("Risk*", ["At Owner Risk", "Insured"], horizontal=True, key=f"risk_{k}")

    with cp2:
        is_np = st.checkbox("New Party?", key=f"isnp_{k}")
        bill_pty = st.text_input("Enter New Party Name*", key=f"np_{k}") if is_np else st.selectbox("Billing Party*", ["Select"] + gl("Party"), key=f"bp_{k}")

        is_nc = st.checkbox("New Consignor?", key=f"isnc_{k}")
        cnor_name = st.text_input("Enter New Consignor Name*", key=f"nc_{k}") if is_nc else st.selectbox("Consignor Name*", ["Select"] + gl("Party"), key=f"cnor_{k}")
            
        cnor_gst = st.text_input("Consignor GST", key=f"cgst_{k}")
        ins_by = st.selectbox("Insurance Paid By*", ["N/A", "Consignor", "Consignee", "Transporter"], key=f"ins_{k}")

    with cp3:
        is_nee = st.checkbox("New Consignee?", key=f"isnee_{k}")
        cnee_name = st.text_input("Consignee Name*", key=f"cnee_{k}") if is_nee else st.selectbox("Consignee Name*", ["Select"] + gl("Party"), key=f"cneesel_{k}")
            
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
                sel_driver = st.selectbox("Driver Name*", ["Select"] + gl("Driver"))
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
            
            # --- UPDATED LOGIC HERE ---
            if v_cat == "Market Hired": 
                hc = st.number_input("Hired Charges (Market Bhada)", min_value=0.0)
                dsl = toll = drv = 0.0
            else: 
                # Own Fleet ke liye inputs hata diye, Dashboard Cash & Bank se uthayega
                st.info("💡 Own Fleet expenses will be tracked via 'Cash & Bank' menu.")
                hc = dsl = toll = drv = 0.0

        if st.form_submit_button("🚀 SAVE LR"):
            if bill_pty and bill_pty != "Select" and fr_amt > 0:
                # Profit Calculation Logic
                # Market Hired: Freight - Hired Charges
                # Own Fleet: Filhal Freight (Baad mein Payments minus honge Dashboard par)
                prof = (fr_amt - hc) if v_cat == "Market Hired" else fr_amt
                
                row = [
                    str(d), lr_no, v_cat, bill_pty, cnor_name, cnor_gst, "", 
                    cnee_name, cnee_gst, "", mat, n_wt, c_wt, v_no, 
                    sel_driver, br_name, fl, tl, fr_amt, hc, dsl, drv, toll, 0, prof
                ]
                
                if save("trips", row):
                    if is_np and bill_pty not in gl("Party"): save("masters", ["Party", bill_pty])
                    if is_nc and cnor_name not in gl("Consignor"): save("masters", ["Consignor", cnor_name])

                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Cnor": cnor_name, "CnorGST": cnor_gst, 
                        "Cnee": cnee_name, "CneeGST": cnee_gst, "BillP": bill_pty, "From": fl, "To": tl, 
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "Freight": fr_amt, 
                        "PaidBy": paid_by, "Risk": risk, "InvNo": inv_no, "ShipTo": ship_to, "show_fr": show_fr, 
                        "InsBy": ins_by, "BranchName": sel_br, "BranchGST": br_info.get('GST', 'N/A'), 
                        "BranchAddr": br_info.get('Address', 'N/A'), "BankName": br_info.get('Name', 'N/A'), 
                        "BankAC": br_info.get('A_C_No', 'N/A'), "BankIFSC": br_info.get('IFSC', 'N/A')
                    }
                    st.success("LR Saved Successfully!")
                    st.rerun()
            else:
                st.error("Please fill Party Name and Freight!")

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
    t1, t2 = st.tabs(["💸 Add Transaction", "📖 Full Statement"])
    
    with t1:
        st.subheader("📝 New Transaction")
        # Form ka naam badal diya taaki cache refresh ho jaye
        with st.form("p_form_v_final_fixed", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            with f1: 
                p_d = st.date_input("Date", date.today(), key="d_fin_fixed")
                acc = st.selectbox("Account*", ["Select"] + all_accs, key="s_acc_fixed")
            with f2: 
                p_t = st.selectbox("Type*", ["Receipt (In)", "Payment (Out)", "Opening Balance"], key="s_type_fixed")
                
                # --- YEH SECTION NAZAR AANA CHAHIYE ---
                p_side = st.radio("Nature", ["Receivable (Lena Hai)", "Payable (Dena Hai)"], horizontal=True, key="nature_radio")
                
                # min_value hata diya taaki minus allow ho
                p_a = st.number_input("Amount*", min_value=None, step=1.0, key="n_amt_fixed")
                
            with f3: 
                p_m = st.selectbox("Mode", ["NEFT", "Cash", "UPI", "Cheque", "None"], key="s_mode_fixed")
                p_r = st.text_input("Ref/Remarks", value="Opening Balance", key="t_ref_fixed")
            
            # --- SAVE BUTTON ---
            if st.form_submit_button("💾 Save Transaction"):
                if acc != "Select" and p_a != 0:
                    # Logic: Agar Payable hai toh Amount ko minus (-) kar do
                    final_amount = float(p_a)
                    if p_t == "Opening Balance" and p_side == "Payable (Dena Hai)":
                        final_amount = -abs(float(p_a))
                    
                    entry_type = "OP_BAL" if p_t == "Opening Balance" else p_t
                    
                    if save("payments", [str(p_d), acc, entry_type, final_amount, p_m, p_r]): 
                        st.success(f"✅ Saved! Amount recorded as: {final_amount}")
                        st.rerun()
                else:
                    st.error("⚠️ Please select Account and enter Amount!")
    with t2:
        sel_a = st.selectbox("Select Account for Statement", ["Select"] + all_accs, key="s4_final")
        ledger_entries = []
        
        if sel_a != "Select":
            # --- A. OPENING BALANCE (Fixed) ---
            if not df_p.empty:
                op_data = df_p[(df_p['Account_Name'] == sel_a) & (df_p['Type'] == 'OP_BAL')]
                for _, r in op_data.iterrows():
                    # Yahan hum brackets/minus handle karne ke liye pehle numeric convert karenge
                    raw_val = str(r.get('Amount', 0)).replace('(', '-').replace(')', '').replace(',', '')
                    amt = pd.to_numeric(raw_val, errors='coerce')
                    
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': '💰 OPENING BALANCE', 
                        'Debit': amt if amt > 0 else 0,
                        'Credit': abs(amt) if amt < 0 else 0 # Minus value yahan Credit mein jayegi
                    })

            # --- B. TRIP DATA ---
            if not df_t.empty:
                # Party Freight (Debit)
                p_trips = df_t[df_t['Party'] == sel_a]
                for _, r in p_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} (Freight Bill)", 
                        'Debit': pd.to_numeric(r.get('Freight', 0), errors='coerce'), 
                        'Credit': 0
                    })
                # Broker Hired (Credit)
                b_trips = df_t[df_t['Broker'] == sel_a]
                for _, r in b_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} (Hired Charges)", 
                        'Debit': 0, 
                        'Credit': pd.to_numeric(r.get('HiredCharges', 0), errors='coerce')
                    })

            # --- C. PAYMENTS ---
            if not df_p.empty:
                p_entries = df_p[(df_p['Account_Name'] == sel_a) & (df_p['Type'] != 'OP_BAL')]
                for _, r in p_entries.iterrows():
                    raw_p = str(r.get('Amount', 0)).replace('(', '-').replace(')', '').replace(',', '')
                    amt = abs(pd.to_numeric(raw_p, errors='coerce'))
                    p_type = str(r.get('Type','')).lower()
                    
                    if "receipt" in p_type or "in" in p_type:
                        ledger_entries.append({
                            'Date': r.get('Date', date.today()), 
                            'Particulars': f"Payment Recd ({r.get('Mode','Cash')})", 
                            'Debit': 0, 'Credit': amt
                        })
                    else:
                        ledger_entries.append({
                            'Date': r.get('Date', date.today()), 
                            'Particulars': f"Payment Paid ({r.get('Mode','Cash')})", 
                            'Debit': amt, 'Credit': 0
                        })

            # --- D. DISPLAY ---
            if ledger_entries:
                full_df = pd.DataFrame(ledger_entries)
                full_df['Date'] = pd.to_datetime(full_df['Date']).dt.date
                full_df = full_df.sort_values(by=['Date'])
                
                # Balance calculation: Debit - Credit
                full_df['Balance'] = (full_df['Debit'] - full_df['Credit']).cumsum()
                
                st.write(f"#### 📖 Ledger Statement: {sel_a}")
                st.dataframe(full_df, use_container_width=True, hide_index=True)
                
                net_bal = full_df['Debit'].sum() - full_df['Credit'].sum()
                if net_bal > 0:
                    st.success(f"Net Receivable: ₹{abs(net_bal):,.0f}")
                else:
                    st.warning(f"Net Payable: ₹{abs(net_bal):,.0f}")
            else:
                st.info("No transactions found.")
elif menu == "5. Business Insights":
    st.header(f"⚖️ Financial Insights & Fleet Ledgers")

    # --- 1. LOCAL YEAR FILTER (Taki error na aaye) ---
    def get_fy_local(date_str):
        try:
            dt = pd.to_datetime(date_str)
            return f"{dt.year}-{str(dt.year+1)[2:]}" if dt.month >= 4 else f"{dt.year-1}-{str(dt.year)[2:]}"
        except: return "Unknown"

    available_fy = ["2024-25", "2025-26", "2026-27"]
    y_col1, _ = st.columns([1, 3])
    with y_col1:
        ins_fy = st.selectbox("📅 Select Year for Insights", available_fy, index=1, key="ins_fy_sel")

    # Filter Data locally for this menu
    df_tf = df_t.copy()
    df_pf = load("payments").copy()
    df_oef = load("office_expenses").copy()

    for dff in [df_tf, df_pf, df_oef]:
        if not dff.empty:
            dff.columns = [str(c).strip() for c in dff.columns]
            d_col = next((c for c in dff.columns if 'date' in c.lower()), 'Date')
            dff['FY'] = dff[d_col].apply(get_fy_local)
    
    # Final Filtered Data
    df_tf = df_tf[df_tf['FY'] == ins_fy] if not df_tf.empty else pd.DataFrame()
    df_pf = df_pf[df_pf['FY'] == ins_fy] if not df_pf.empty else pd.DataFrame()
    df_oef = df_oef[df_oef['FY'] == ins_fy] if not df_oef.empty else pd.DataFrame()

    # --- 2. TABS FOR DETAILED LEDGERS ---
    t1, t2, t3 = st.tabs(["💰 Cash & Fund Flow", "🚛 Own Truck Ledger", "🤝 Market Hiring Ledger"])

    with t1:
        st.subheader(f"📊 Real-Time Cash Flow Statement ({ins_fy})")
        
        # --- A. PAYMENTS SHEET SE DATA (Direct Receipts & Payments) ---
        cash_in_direct = 0
        cash_out_direct = 0
        if not df_pf.empty:
            amt_c = next((c for c in df_pf.columns if 'amount' in c.lower()), 'Amount')
            type_c = next((c for c in df_pf.columns if 'type' in c.lower()), 'Type')
            df_pf[amt_c] = pd.to_numeric(df_pf[amt_c], errors='coerce').fillna(0)
            
            cash_in_direct = df_pf[df_pf[type_c].str.contains('Receipt|In', case=False, na=False)][amt_c].sum()
            cash_out_direct = df_pf[df_pf[type_c].str.contains('Payment|Out', case=False, na=False)][amt_c].sum()

        # --- B. TRIPS SHEET SE DATA (Own Truck Trip Expenses) ---
        trip_cash_out = 0
        if not df_tf.empty:
            type_c_t = next((c for c in df_tf.columns if 'type' in c.lower()), 'Type')
            # Sirf Own Fleet ke kharche jo on-the-spot pay hote hain
            df_own_exp = df_tf[df_tf[type_c_t].str.contains('Own', case=False, na=False)].copy()
            
            # Kharchon ke columns ka total
            exp_cols = [c for c in df_own_exp.columns if any(x in c.lower() for x in ['diesel', 'toll', 'adv', 'driverexp'])]
            for col in exp_cols:
                df_own_exp[col] = pd.to_numeric(df_own_exp[col], errors='coerce').fillna(0)
            
            trip_cash_out = df_own_exp[exp_cols].sum().sum()

        # --- C. OFFICE EXPENSES ---
        office_out = 0
        if not df_oef.empty:
            amt_c_oe = next((c for c in df_oef.columns if 'amount' in c.lower()), 'Amount')
            office_out = pd.to_numeric(df_oef[amt_c_oe], errors='coerce').fillna(0).sum()

        # --- FINAL TOTALS ---
        total_cash_in = cash_in_direct
        total_cash_out = cash_out_direct + trip_cash_out + office_out
        net_cash_flow = total_cash_in - total_cash_out

        # Display Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Cash Inflow", f"₹{total_cash_in:,.0f}")
        m2.metric("Total Cash Outflow", f"₹{total_cash_out:,.0f}", delta=f"Trips: ₹{trip_cash_out:,.0f}", delta_color="inverse")
        m3.metric("Net Cash Position", f"₹{net_cash_flow:,.0f}")

        st.divider()
        
        # Cash Flow Breakdown Chart
        st.write("#### 📉 Cash Flow Breakdown")
        cf_data = pd.DataFrame({
            'Category': ['Receipts', 'Direct Payments', 'Trip Expenses (Own)', 'Office Exp'],
            'Amount': [cash_in_direct, cash_out_direct, trip_cash_out, office_out]
        })
        fig_cf = px.pie(cf_data, values='Amount', names='Category', hole=0.4, 
                         color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_cf, use_container_width=True)

        # Detailed List of Trip Cash Out (Optional Table)
        if trip_cash_out > 0:
            with st.expander("🔍 View Own Truck Trip Cash Details"):
                st.dataframe(df_own_exp[['Date', 'Vehicle', 'LR No'] + exp_cols], use_container_width=True)
            
            st.write("#### Detailed Transaction History")
            st.dataframe(df_pf[[d_col, 'Account_Name', type_c, amt_c, 'Mode']].sort_values(d_col, ascending=False), use_container_width=True)
        else:
            st.info("No payment data found for this year.")

    with t2:
        st.subheader("Own Fleet: Trip-wise Performance")
        # Variable ko block se pehle khali define karein (NameError se bachne ke liye)
        v_summary = pd.DataFrame() 
        
        type_c_t = next((c for c in df_tf.columns if 'type' in c.lower()), 'Type')
        df_own = df_tf[df_tf[type_c_t].str.contains('Own', case=False, na=False)].copy() if not df_tf.empty else pd.DataFrame()
        
        if not df_own.empty:
            v_col = next((c for c in df_own.columns if 'vehicle' in c.lower()), 'Vehicle')
            cols_to_num = ['Freight', 'Diesel', 'Toll', 'DriverExp', 'Other']
            for c in cols_to_num:
                if c in df_own.columns: df_own[c] = pd.to_numeric(df_own[c], errors='coerce').fillna(0)
            
            df_own['Trip_Cost'] = df_own['Diesel'] + df_own['Toll'] + df_own['DriverExp'] + df_own['Other']
            df_own['Net_Profit'] = df_own['Freight'] - df_own['Trip_Cost']
            
            v_summary = df_own.groupby(v_col).agg({
                'Freight': 'sum', 'Diesel': 'sum', 'Toll': 'sum', 
                'DriverExp': 'sum', 'Trip_Cost': 'sum', 'Net_Profit': 'sum'
            }).reset_index()
            
            st.write("#### 📊 Vehicle-wise Profit Summary")
            v_summary_clean = v_summary.fillna(0)
            
            # Styling apply karein (Safe way)
            st.dataframe(
                v_summary_clean.style.format({
                    'Freight': '₹{:,.0f}', 'Diesel': '₹{:,.0f}', 'Toll': '₹{:,.0f}', 
                    'DriverExp': '₹{:,.0f}', 'Trip_Cost': '₹{:,.0f}', 'Net_Profit': '₹{:,.0f}'
                }).background_gradient(subset=['Net_Profit'], cmap='Greens'), 
                use_container_width=True
            )
        else:
            st.info("Own fleet ka koi data available nahi hai.")

    with t3:
        st.subheader("Market Hiring & Broker Ledger")
        # Variable ko block se pehle khali define karein
        b_summary = pd.DataFrame()

        df_mkt = df_tf[df_tf[type_c_t].str.contains('Market|Hired', case=False, na=False)].copy() if not df_tf.empty else pd.DataFrame()
        
        if not df_mkt.empty:
            b_col = next((c for c in df_mkt.columns if 'broker' in c.lower()), 'Broker')
            # Numeric conversion
            for c in ['HiredCharges', 'Freight']:
                df_mkt[c] = pd.to_numeric(df_mkt[c], errors='coerce').fillna(0)
            
            df_mkt['Commission'] = df_mkt['Freight'] - df_mkt['HiredCharges']
            
            b_summary = df_mkt.groupby(b_col).agg({
                'LR No': 'count', 'Freight': 'sum', 'HiredCharges': 'sum', 'Commission': 'sum'
            }).rename(columns={'LR No': 'Trips'}).reset_index()
            
            st.write("#### 📊 Broker Wise Summary")
            b_summary_clean = b_summary.fillna(0)
            st.dataframe(b_summary_clean.style.format({
                'Freight': '₹{:,.0f}', 'HiredCharges': '₹{:,.0f}', 'Commission': '₹{:,.0f}'
            }), use_container_width=True)
        else:
            st.info("Market hiring ka koi data available nahi hai.")
elif menu == "6. Expense Manager":
    st.header("🏢 Office & Personal Expense Manager")
    df_oe = load("office_expenses")
    if not df_oe.empty: df_oe.columns = [str(c).strip() for c in df_oe.columns]

    # Char alag tabs: Entry, Office View, Indrajit Khata, Vishal Khata
    tab_add, tab_view, tab_indrajit, tab_vishal = st.tabs([
        "➕ Add Expense", "📊 Office Expenses", "👤 Indrajit Khata", "👤 Vishal Khata"
    ])
    
    with tab_add:
        with st.form("office_exp_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                e_date = st.date_input("Date", date.today())
                e_cat = st.selectbox("Category", [
                    "Office Rent", "Electricity", "Staff Salary", 
                    "Stationery", "Tea/Coffee", "maintenance", 
                    "Indrajit Personal", "Vishal Personal", "Others"
                ])
            with col2:
                e_amt = st.number_input("Amount (₹)", min_value=0.0)
                e_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque"])
            
            e_desc = st.text_input("Description / Remarks")
            
            if st.form_submit_button("Save Expense"):
                if e_amt > 0:
                    if save("office_expenses", [str(e_date), e_cat, e_desc, e_amt, e_mode]):
                        st.success(f"{e_cat} Entry Saved!"); st.rerun()

    with tab_view:
        st.subheader("General Office Expenses")
        if not df_oe.empty:
            # Sirf Office wale (Personal ko filter karke hata rahe hain)
            office_df = df_oe[~df_oe['Category'].str.contains('Indrajit|Vishal', na=False)]
            st.dataframe(office_df, use_container_width=True)
            st.info(f"Total Office Expense: ₹{pd.to_numeric(office_df['Amount'], errors='coerce').sum():,.2f}")

    with tab_indrajit:
        st.subheader("👤 Indrajit Personal Ledger")
        if not df_oe.empty:
            ind_df = df_oe[df_oe['Category'] == "Indrajit Personal"]
            if not ind_df.empty:
                # Amount column dhoondna
                amt_col = next((c for c in ind_df.columns if 'amount' in c.lower()), 'Amount')
                total_i = pd.to_numeric(ind_df[amt_col], errors='coerce').sum()
                st.metric("Total Withdrawals (Indrajit)", f"₹{total_i:,.0f}")
                
                st.divider()
                # Sirf wahi columns dikhana jo sheet mein available hain
                st.write("#### Detailed Transaction History")
                st.dataframe(ind_df, use_container_width=True, hide_index=True)
            else:
                st.info("Indrajit ka koi personal record nahi mila.")

    with tab_vishal:
        st.subheader("👤 Vishal Personal Ledger")
        if not df_oe.empty:
            vis_df = df_oe[df_oe['Category'] == "Vishal Personal"]
            if not vis_df.empty:
                # Amount column dhoondna
                amt_col = next((c for c in vis_df.columns if 'amount' in c.lower()), 'Amount')
                total_v = pd.to_numeric(vis_df[amt_col], errors='coerce').sum()
                st.metric("Total Withdrawals (Vishal)", f"₹{total_v:,.0f}")
                
                st.divider()
                # Pura dataframe dikhana safe hai
                st.write("#### Detailed Transaction History")
                st.dataframe(vis_df, use_container_width=True, hide_index=True)
            else:
                st.info("Vishal ka koi personal record nahi mila.")
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
elif menu == "9. Cash & Bank":
    st.header("🏦 Cash & Bank Management", divider="rainbow")
    
    # 1. DATA LOADING & CLEANING
    df_p = load("payments")
    if not df_p.empty:
        df_p['Amount'] = df_p['Amount'].astype(str).str.replace(r'\(', '-', regex=True).str.replace(r'\)', '', regex=True).str.replace(',', '').str.replace('₹', '')
        df_p['Amount'] = pd.to_numeric(df_p['Amount'], errors='coerce').fillna(0)

    # 2. LIVE BALANCES (Metrics)
    st.subheader("📊 Live Account Balances", divider="blue")
    banks_list = gl("Bank")
    cols = st.columns(len(banks_list) + 1)
    cash_bal = df_p[df_p['Account_Name'].str.contains('CASH', case=False, na=False)]['Amount'].sum()
    cols[0].metric("💵 Cash in Hand", f"₹{cash_bal:,.2f}")
    for i, b in enumerate(banks_list):
        b_bal = df_p[df_p['Account_Name'] == b]['Amount'].sum()
        cols[i+1].metric(f"🏦 {b}", f"₹{b_bal:,.2f}")

    st.divider()

    # 3. TRANSACTION TABS (Yahan dhyan dein)
    t1, t2 = st.tabs(["💸 Record Payment / Expense", "📑 Digital Passbook"])
    
    with t1:
        st.subheader("💸 Record Expense / Payment", divider="orange")
        df_t_live = load("trips")
        lr_options = ["General / No LR"] + (df_t_live['LR No'].unique().tolist()[::-1] if not df_t_live.empty else [])
        all_to_options = sorted(gl("Expense") + ["Indrajit Personal", "Vishal Personal"] + gl("Driver") + gl("Broker") + gl("Party"))

        with st.form("cash_bank_expense_final_v3", clear_on_submit=True):
            f1, f2 = st.columns(2)
            with f1:
                p_date = st.date_input("Date", date.today())
                to_acc = st.selectbox("Pay To (Expense/Account)*", ["Select"] + all_to_options)
                linked_lr = st.selectbox("Link to LR No*", lr_options)
                p_amt = st.number_input("Amount (₹)*", min_value=0.0, step=1.0)
            with f2:
                from_acc = st.selectbox("Pay From (Bank/Cash Account)*", ["Select"] + sorted(gl("Bank") + ["CASH"]))
                p_mode = st.selectbox("Mode", ["Cash", "UPI", "NEFT", "Cheque", "Transfer"])
                p_rem = st.text_input("Remarks", placeholder="Diesel, Toll, etc.")

            if st.form_submit_button("🚀 Confirm & Save Transaction"):
                if to_acc != "Select" and from_acc != "Select" and p_amt > 0:
                    lr_tag = f"LR:{linked_lr}" if linked_lr != "General / No LR" else "General"
                    final_remarks = f"{lr_tag} | {to_acc} | {p_rem}"
                    e1 = save("payments", [str(p_date), from_acc, "Payment (Out)", -p_amt, p_mode, final_remarks])
                    e2 = save("payments", [str(p_date), to_acc, "Payment (Out)", p_amt, p_mode, final_remarks])
                    if e1 and e2:
                        st.success(f"✅ ₹{p_amt} Saved!")
                        st.rerun()
                else:
                    st.error("⚠️ Please fill mandatory fields!")

    # --- YE T2 TAB T1 KE BAHAR HONA CHAHIYE (SAME MARGIN) ---
    with t2:
        st.subheader("📑 Digital Passbook", divider="violet")
        # List of all accounts for passbook
        pb_options = sorted(gl("Bank") + ["CASH"] + gl("Expense") + ["Indrajit Personal", "Vishal Personal"] + gl("Driver"))
        sel_acc = st.selectbox("Select Account to View Passbook", ["Select"] + pb_options, key="passbook_view_final")
        
        if sel_acc != "Select":
            # Filter data from payments sheet
            stmt_df = df_p[df_p['Account_Name'] == sel_acc].sort_values('Date', ascending=False)
            if not stmt_df.empty:
                # Sirf vahi columns dikhao jo sheet mein hain: Date, Type, Amount, Mode, Remarks
                st.dataframe(
                    stmt_df[['Date', 'Type', 'Amount', 'Mode', 'Remarks']].style.format({"Amount": "₹{:,.2f}"}),
                    use_container_width=True,
                    hide_index=True
                )
                total_current = stmt_df['Amount'].sum()
                st.info(f"💰 Current Balance in **{sel_acc}**: **₹{total_current:,.2f}**")
            else:
                st.warning(f"No transactions found for {sel_acc}.")
























































