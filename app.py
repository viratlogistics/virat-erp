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

# CSS for BIG FONTS and ATTRACTIVE LOOK
st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        .stMain {margin-top: -70px;}
        
        /* Menu ka font bada aur bold karne ke liye */
        .nav-link {
            font-size: 16px !important; 
            font-weight: 700 !important; 
            text-transform: uppercase !important;
            border-radius: 0px !important;
            padding: 10px !important;
        }
        
        /* Heading attractive banane ke liye */
        h2, h3 {
            color: #00d4ff !important;
            font-weight: 800;
            letter-spacing: 1px;
        }
    </style>
    """, unsafe_allow_html=True)

# --- UPDATED TOP MENU (Attractive Colors) ---
menu = option_menu(
    menu_title=None, 
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
    orientation="horizontal", 
    styles={
        "container": {
            "padding": "0!important", 
            "background-color": "#0e1117", # Dark Premium Background
            "border-bottom": "2px solid #00d4ff" # Niche ek neon line
        },
        "icon": {"color": "#ffaa00", "font-size": "18px"}, # Icons thode bade aur orange
        "nav-link": {
            "color": "white",
            "text-align": "center", 
            "margin":"0px",
            "--hover-color": "#262730"
        },
        "nav-link-selected": {
            "background-color": "#00d4ff", # Cyan color selection
            "color": "black" # Text black taaki uthkar dikhe
        },
    }
)
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
    st.title("📊 Virat Logistics - Cash & Profit Dashboard")

    # --- 1. FY SELECTION ---
    col_fy, col_empty = st.columns([1, 3])
    with col_fy:
        available_fy = ["2024-25", "2025-26", "2026-27"]
        selected_fy = st.selectbox("📅 Financial Year", available_fy, index=1)

    def get_fy(date_str):
        try:
            dt = pd.to_datetime(date_str)
            return f"{dt.year}-{str(dt.year+1)[2:]}" if dt.month >= 4 else f"{dt.year-1}-{str(dt.year)[2:]}"
        except: return "Unknown"

    # --- 2. DATA LOADING & PREP ---
    df_p = load("payments")
    df_oe = load("office_expenses")
    
    # Cleaning & FY Filtering for ALL Dataframes
    def filter_data(df_raw):
        if df_raw.empty: return pd.DataFrame()
        df_c = df_raw.copy()
        df_c.columns = [str(c).strip() for c in df_c.columns]
        d_col = next((c for c in df_c.columns if 'date' in c.lower()), 'Date')
        df_c['FY'] = df_c[d_col].apply(get_fy)
        return df_c[df_c['FY'] == selected_fy]

    df_t_f = filter_data(df_t)
    df_p_f = filter_data(df_p)
    df_oe_f = filter_data(df_oe)

    # --- 3. CASH FLOW CALCULATION (Using df_p_f) ---
    cash_in = 0
    payments_out = 0
    if not df_p_f.empty:
        amt_col_p = next((c for c in df_p_f.columns if 'amount' in c.lower()), 'Amount')
        type_col_p = next((c for c in df_p_f.columns if 'type' in c.lower()), 'Type')
        df_p_f[amt_col_p] = pd.to_numeric(df_p_f[amt_col_p], errors='coerce').fillna(0)
        cash_in = df_p_f[df_p_f[type_col_p].str.contains('Receipt|In', case=False, na=False)][amt_col_p].sum()
        payments_out = df_p_f[df_p_f[type_col_p].str.contains('Payment|Out', case=False, na=False)][amt_col_p].sum()

    # Own Fleet Cash Out (Using df_t_f)
    own_cash_out = 0
    if not df_t_f.empty:
        type_col_t = next((c for c in df_t_f.columns if 'type' in c.lower()), 'Type')
        df_own = df_t_f[df_t_f[type_col_t].str.contains('Own', case=False, na=False)].copy()
        c_cols = [c for c in df_t_f.columns if any(x in c.lower() for x in ['diesel', 'toll', 'adv', 'driverexp'])]
        for c in c_cols: df_own[c] = pd.to_numeric(df_own[c], errors='coerce').fillna(0)
        own_cash_out = df_own[c_cols].sum().sum()

    # Office Expense (Using df_oe_f)
    office_cash_out = 0
    if not df_oe_f.empty:
        amt_col_oe = next((c for c in df_oe_f.columns if 'amount' in c.lower()), 'Amount')
        office_cash_out = pd.to_numeric(df_oe_f[amt_col_oe], errors='coerce').fillna(0).sum()

    total_actual_cash_out = payments_out + own_cash_out + office_cash_out
    cash_hand_balance = cash_in - total_actual_cash_out

    # --- 4. PROFIT CALCULATION (Using df_t_f) ---
    rev_col = next((c for c in df_t_f.columns if any(x in c.lower() for x in ['freight', 'revenue'])), 'Freight')
    if not df_t_f.empty:
        df_t_f[rev_col] = pd.to_numeric(df_t_f[rev_col], errors='coerce').fillna(0)
        total_rev = df_t_f[rev_col].sum()
        trip_exp_cols = [c for c in df_t_f.columns if any(x in c.lower() for x in ['hired', 'diesel', 'toll', 'adv', 'driverexp', 'other'])]
        for c in trip_exp_cols: df_t_f[c] = pd.to_numeric(df_t_f[c], errors='coerce').fillna(0)
        total_trip_cost = df_t_f[trip_exp_cols].sum().sum()
        net_profit = total_rev - (total_trip_cost + office_cash_out)
    else:
        total_rev = net_profit = 0

    # Display Metrics
    st.subheader(f"📌 Financial Summary: {selected_fy}")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Cash In (Receipts)", f"₹{cash_in:,.0f}")
    r2.metric("Cash Out (Actual)", f"₹{total_actual_cash_out:,.0f}", delta_color="inverse")
    r3.metric("Bank/Hand Balance", f"₹{cash_hand_balance:,.0f}")
    r4.metric("Net Business Profit", f"₹{net_profit:,.0f}")

    st.divider()

    # --- 5. CHARTS ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 Actual Cash Flow")
        cash_df = pd.DataFrame({'Category': ['Cash In', 'Cash Out'], 'Amount': [cash_in, total_actual_cash_out]})
        fig_cash = px.bar(cash_df, x='Category', y='Amount', color='Category', 
                          color_discrete_map={'Cash In': '#2ecc71', 'Cash Out': '#e74c3c'}, text_auto='.3s')
        st.plotly_chart(fig_cash, use_container_width=True)

    with c2:
        st.subheader("🚛 Vehicle Performance (Revenue vs Profit)")
        v_col = next((c for c in df_t_f.columns if 'vehicle' in c.lower()), 'Vehicle')
        if not df_t_f.empty:
            type_col_t = next((c for c in df_t_f.columns if 'type' in c.lower()), 'Type')
            df_v = df_t_f[df_t_f[type_col_t].str.contains('Own', case=False, na=False)].copy()
            if not df_v.empty:
                exp_cols = [c for c in df_v.columns if any(x in c.lower() for x in ['diesel', 'toll', 'adv', 'driverexp'])]
                v_perf = df_v.groupby(v_col).agg({rev_col: 'sum', **{c: 'sum' for c in exp_cols}}).reset_index()
                v_perf['Total_Exp'] = v_perf[exp_cols].sum(axis=1)
                v_perf['Profit'] = v_perf[rev_col] - v_perf['Total_Exp']
                
                v_plot = v_perf.melt(id_vars=v_col, value_vars=[rev_col, 'Profit'], var_name='Metric', value_name='Amount')
                fig_v = px.bar(v_plot, x=v_col, y='Amount', color='Metric', barmode='group',
                               color_discrete_map={rev_col: '#3498db', 'Profit': '#2ecc71'}, text_auto='.2s')
                st.plotly_chart(fig_v, use_container_width=True)
            else:
                st.info("No 'Own Fleet' data for this year.")
        else:
            st.info("No trip data found.")

    # --- 6. RECEIVABLES ---
    st.divider()
    st.subheader("⏳ Top Unpaid Parties (Receivables)")
    party_col = next((c for c in df_t_f.columns if 'party' in c.lower()), 'Party')
    if not df_t_f.empty:
        p_rev = df_t_f.groupby(party_col)[rev_col].sum()
        p_acc_col = next((c for c in df_p_f.columns if any(x in c.lower() for x in ['account', 'name', 'party'])), 'Account_Name')
        p_rec = df_p_f[df_p_f[type_col_p].str.contains('Receipt', case=False, na=False)].groupby(p_acc_col)[amt_col_p].sum() if not df_p_f.empty else pd.Series()
        
        pending = pd.DataFrame({'Billed': p_rev, 'Received': p_rec}).fillna(0)
        pending['Due'] = pending['Billed'] - pending['Received']
        top_pending = pending[pending['Due'] > 100].sort_values('Due', ascending=False).head(10).reset_index()
        top_pending.columns = ['Party', 'Billed', 'Received', 'Due']
        
        if not top_pending.empty:
            fig_due = px.bar(top_pending, x='Due', y='Party', orientation='h', color='Due', color_continuous_scale='Reds')
            st.plotly_chart(fig_due, use_container_width=True)
            st.dataframe(pending[pending['Due'] > 1].style.format("₹{:,.0f}"), use_container_width=True)
if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    
    # 1. Category Selection
    m_type = st.selectbox("Category", ["Branch (Company)", "Party", "Broker", "Vehicle", "Driver"])
    
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
        lr_no_auto = f"VIL/25-26/{br_code}/{len(df_t)+1:03d}"
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
                dsl, toll, drv = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Adv")
                hc = 0.0
            else: 
                hc = st.number_input("Hired Charges")
                dsl = toll = drv = 0.0

        # --- YE FORM KA END HAI ---
        if st.form_submit_button("🚀 SAVE LR"):
            if bill_pty and bill_pty != "Select" and fr_amt > 0:
                # 1. Branch Master se sara data fetch karna
                br_info = df_m[df_m['Name'] == sel_br].iloc[0] if sel_br != "Select" else {}
                
                prof = (fr_amt - (hc if v_cat == "Market Hired" else (dsl+toll+drv)))
                row = [
                    str(d),           # Date
                    lr_no,            # LR No
                    v_cat,            # Type (Own/Market)
                    bill_pty,         # Party
                    cnor_name,        # Consignor
                    cnor_gst,         # Consignor_GST
                    cnor_add,         # Consignor_Add (Blank for now)
                    cnee_name,        # Consignee
                    cnee_gst,         # Consignee_GST
                    ship_to,          # Consignee_Add (Delivery Address)
                    mat,              # Material
                    n_wt,             # Weight (Net)
                    c_wt,             # Chg_Weight (Naya column)
                    v_no,             # Vehicle
                    sel_driver,       # Driver
                    br_name,          # Broker
                    fl,               # From
                    tl,               # To
                    fr_amt,           # Freight
                    (hc if v_cat == "Market Hired" else 0.0), # HiredCharges
                    dsl,              # Diesel
                    drv,              # DriverExp
                    toll,             # Toll
                    0,                # Other
                    prof              # Profit
                ]
                
                if save("trips", row):
                    # 2. AGAR NEW PARTY/CONSIGNOR HAI TO MASTER MEIN SAVE KARO
                    if is_np and bill_pty not in gl("Party"):
                        save("masters", ["Party", bill_pty])
                    if is_nc and cnor_name not in gl("Consignor"):
                        save("masters", ["Consignor", cnor_name])

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
                    st.success("LR Saved and Masters Updated!")
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
        
    all_accs = sorted(gl("Party") + gl("Broker"))
    t1, t2 = st.tabs(["💸 Add Transaction", "📖 Full Statement"])
    
    with t1:
        with st.form("p_form", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            with f1: 
                p_d = st.date_input("Date", date.today())
                acc = st.selectbox("Account*", ["Select"] + all_accs)
            with f2: 
                p_t = st.selectbox("Type*", ["Receipt (In)", "Payment (Out)"])
                p_a = st.number_input("Amount*", min_value=0.0)
            with f3: 
                p_m = st.selectbox("Mode", ["NEFT", "Cash", "UPI", "Cheque"])
                p_r = st.text_input("Ref/Remarks")
            
            if st.form_submit_button("Save Entry"):
                if acc != "Select" and p_a > 0:
                    if save("payments", [str(p_d), acc, p_t, p_a, p_m, p_r]): 
                        st.success("Entry Saved Successfully!"); st.rerun()

    with t2:
        sel_a = st.selectbox("Select Account for Statement", ["Select"] + all_accs)
        if sel_a != "Select":
            ledger_entries = []
            
            # --- 1. TRIP DATA SE ENTRIES (DEBIT & CREDIT DONO CHECK KAREIN) ---
            if not df_t.empty:
                # Agar woh hamari PARTY hai (Humein freight DENA hai - Debit)
                p_trips = df_t[df_t['Party'] == sel_a]
                for _, r in p_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} (Freight Bill)", 
                        'Debit': pd.to_numeric(r.get('Freight', 0), errors='coerce'), 
                        'Credit': 0
                    })
                
                # Agar woh hamara BROKER hai (Humein usko hired charges DENA hai - Credit)
                b_trips = df_t[df_t['Broker'] == sel_a]
                for _, r in b_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} (Hired Charges)", 
                        'Debit': 0, 
                        'Credit': pd.to_numeric(r.get('HiredCharges', 0), errors='coerce')
                    })

            # --- 2. PAYMENT DATA SE ENTRIES (RECEIPT & PAYMENT) ---
            if not df_p.empty:
                # Column name check (Account_Name ya Account)
                acc_col = next((c for c in df_p.columns if any(x in c.lower() for x in ['account', 'name'])), 'Account_Name')
                p_entries = df_p[df_p[acc_col] == sel_a]
                
                for _, r in p_entries.iterrows():
                    amt = pd.to_numeric(r.get('Amount', 0), errors='coerce')
                    p_type = str(r.get('Type','')).lower()
                    mode = r.get('Mode', 'N/A')
                    ref = r.get('Ref_No', r.get('Ref No', 'N/A'))
                    
                    if "receipt" in p_type or "in" in p_type:
                        # Paisa Aaya (Hamari taraf se credit/kam hua receivable)
                        ledger_entries.append({
                            'Date': r.get('Date', date.today()), 
                            'Particulars': f"Cash/Bank Recd ({mode}) Ref:{ref}", 
                            'Debit': 0, 
                            'Credit': amt
                        })
                    else:
                        # Humne Paisa Diya (Payment Out)
                        ledger_entries.append({
                            'Date': r.get('Date', date.today()), 
                            'Particulars': f"Cash/Bank Paid ({mode}) Ref:{ref}", 
                            'Debit': amt, 
                            'Credit': 0
                        })

            # --- 3. FINAL DISPLAY ---
            if ledger_entries:
                full_df = pd.DataFrame(ledger_entries)
                full_df['Date'] = pd.to_datetime(full_df['Date']).dt.date
                full_df = full_df.sort_values(by=['Date'])
                
                # Running Balance Calculation
                full_df['Balance'] = (full_df['Debit'] - full_df['Credit']).cumsum()
                
                st.divider()
                m1, m2, m3 = st.columns(3)
                dr_total = full_df['Debit'].sum()
                cr_total = full_df['Credit'].sum()
                net_bal = dr_total - cr_total
                
                m1.metric("Total DR (Freight/Paid)", f"₹{dr_total:,.0f}")
                m2.metric("Total CR (Hired/Recd)", f"₹{cr_total:,.0f}")
                
                # Logic: Agar balance (+) hai toh Receivable, (-) hai toh Payable
                if net_bal > 0:
                    m3.metric("Net Receivable (Lena hai)", f"₹{abs(net_bal):,.0f}", delta="Paisa Lena hai")
                elif net_bal < 0:
                    m3.metric("Net Payable (Dena hai)", f"₹{abs(net_bal):,.0f}", delta="- Paisa Dena hai", delta_color="inverse")
                else:
                    m3.metric("Net Balance", "₹0", delta="Settled")
                
                st.write(f"#### 📖 Combined Ledger Statement: {sel_a}")
                st.dataframe(full_df, use_container_width=True, hide_index=True)
            else:
                st.info("Is account ke liye koi transaction nahi mila.")

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
























































