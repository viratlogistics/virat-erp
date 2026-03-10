import streamlit as st
import pandas as pd
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
    except: return None

sh = get_sh()

def load(name):
    try:
        ws = sh.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save(name, row):
    try:
        sh.worksheet(name).append_row(row, value_input_option='USER_ENTERED')
        return True
    except: return False

def delete_master_row(name_val):
    try:
        ws = sh.worksheet("masters")
        cell = ws.find(name_val)
        ws.delete_rows(cell.row)
        return True
    except: return False

# --- 2. PDF ENGINE ---
def generate_lr_pdf(lr_data, show_fr=True):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18); pdf.cell(100, 8, "Virat Logistics", ln=1)
    pdf.set_font("Arial", 'I', 8); pdf.cell(190, 5, "Your Goods Are In Good hand..", ln=True)
    pdf.line(10, 30, 200, 30); pdf.ln(8)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {lr_data.get('LR No', '')}", 1); pdf.cell(45, 8, f"Date: {lr_data.get('Date', '')}", 1)
    pdf.cell(50, 8, f"Vehicle: {lr_data.get('Vehicle', '')}", 1); pdf.cell(50, 8, f"Risk: {lr_data.get('Risk', 'Owner Risk')}", 1, ln=True)
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 8); y_s = pdf.get_y()
    pdf.multi_cell(63, 5, f"{lr_data.get('Cnor', '')}\nGST: {lr_data.get('CnorGST', '')}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 5, f"{lr_data.get('Cnee', '')}\nGST: {lr_data.get('CneeGST', '')}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 5, f"{lr_data.get('BillP', '')}\nInv: {lr_data.get('InvNo', '')}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3))
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {lr_data.get('ShipTo', 'N/A')}", 1, ln=True)
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8); pdf.cell(70, 10, lr_data.get('Material', ''), 1); pdf.cell(30, 10, lr_data.get('Pkg', ''), 1); pdf.cell(30, 10, f"{lr_data.get('NetWt', 0)}/{lr_data.get('ChgWt', 0)}", 1); pdf.cell(30, 10, f"{lr_data.get('From', '')}-{lr_data.get('To', '')}", 1)
    amt = f"Rs. {lr_data.get('Freight', 0)}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, f"BANK: {lr_data.get('Bank', 'N/A')} | Freight Paid By: {lr_data.get('PaidBy', 'N/A')}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN LOGIC ---
df_m = load("masters")
df_t = load("trips")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry", "3. LR Register", "4. Financials", "5. Business Insights", "6. Expense Manager", "7. Driver Khata"])
def gl(t): return sorted(df_m[df_m['Type'] == t]['Name'].unique().tolist()) if not df_m.empty else []
if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank", "Branch"])
    with st.form("m_form", clear_on_submit=True):
        val = st.text_input(f"New {m_type}")
        code = st.text_input("Code/GST (Optional)")
        if st.form_submit_button("Add Master"):
            if val: save("masters", [m_type, val, code]); st.success("Saved!"); st.rerun()
    st.divider()
    if not df_m.empty:
        curr_m = df_m[df_m['Type'] == m_type]
        for i, r in curr_m.iterrows():
            mc1, mc2 = st.columns([5,1])
            mc1.write(f"**{r['Name']}** | {r.get('GST', '')}")
            if mc2.button("🗑️", key=f"del_{i}"):
                if delete_master_row(r['Name']): st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    if st.button("🆕 RESET FORM"):
        st.session_state.reset_trigger += 1; st.session_state.pdf_ready = None; st.rerun()

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
        # Dhyaan dein: Ye saari lines 'with cp2:' se 4 spaces aage hain
        is_np = st.checkbox("New Party?", key=f"isnp_{k}")
        if is_np:
            bill_pty = st.text_input("Enter New Party Name*", key=f"np_{k}")
        else:
            bill_pty = st.selectbox("Billing Party*", ["Select"] + gl("Party"), key=f"bp_{k}")

        is_nc = st.checkbox("New Consignor?", key=f"isnc_{k}")
        if is_nc:
            cnor_name = st.text_input("Enter New Consignor Name*", key=f"nc_{k}")
        else:
            # Ab yahan bhi gl("Party") ki list dikhegi
            cnor_name = st.selectbox("Consignor Name*", ["Select"] + gl("Party"), key=f"cnor_{k}")
            
        cnor_gst = st.text_input("Consignor GST", key=f"cgst_{k}")
        ins_by = st.selectbox("Insurance Paid By*", ["N/A", "Consignor", "Consignee", "Transporter"], key=f"ins_{k}")

    with cp3:
        cnee_name = st.text_input("Consignee Name*", key=f"cnee_{k}")
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
                dsl, toll, drv = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Adv"); hc = 0.0
            else: 
                hc = st.number_input("Hired Charges"); dsl = toll = drv = 0.0

        if st.form_submit_button("🚀 SAVE LR"):
            if bill_pty and bill_pty != "Select" and fr_amt > 0:
                prof = (fr_amt - (hc if v_cat == "Market Hired" else (dsl+toll+drv)))
                # Row data for Trips sheet
                row = [str(d), lr_no, v_cat, bill_pty, cnor_name, paid_by, n_wt, c_wt, pkg, risk, mat, ins_by, v_no, sel_driver, br_name, fl, tl, fr_amt, (hc if v_cat == "Market Hired" else 0.0), dsl, drv, toll, 0, prof]
                
                if save("trips", row):
                    # --- AUTO MASTER UPDATE LOGIC ---
                    # Update Party Master if New Party checked
                    if is_np and bill_pty not in gl("Party"):
                        save("masters", ["Party", bill_pty])
                    
                    # Update Consignor Master if New Consignor checked
                    if is_nc and cnor_name not in gl("Consignor"):
                        save("masters", ["Consignor", cnor_name])

                    st.session_state.pdf_ready = {"LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Cnor": cnor_name, "CnorGST": cnor_gst, "Cnee": cnee_name, "CneeGST": cnee_gst, "BillP": bill_pty, "From": fl, "To": tl, "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "Freight": fr_amt, "PaidBy": paid_by, "Bank": sel_bank, "Risk": risk, "InsBy": ins_by, "InvNo": inv_no, "ShipTo": ship_to, "show_fr": show_fr}
                    st.success("LR Saved and Masters Updated!")
                    st.rerun()
            else:
                st.error("Please fill Party Name and Freight!")

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, st.session_state.pdf_ready.get('show_fr', True)), f"LR_{st.session_state.pdf_ready['LR No']}.pdf")
elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    if not df_t.empty:
        for i, row in df_t.iterrows():
            with st.expander(f"LR: {row.get('LR No', 'N/A')} | {row.get('Consignee', 'N/A')}"):
                st.download_button("📥 PDF", generate_lr_pdf(row.to_dict(), True), f"LR_{row.get('LR No','VL')}.pdf", key=f"p_{i}")
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
            
            # 1. TRIPS DATA (Freight/Hired)
            if not df_t.empty:
                # Party Side (Bill generation)
                p_trips = df_t[df_t['Party'] == sel_a]
                for _, r in p_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} ({r.get('From','')} to {r.get('To','')})", 
                        'Debit': pd.to_numeric(r.get('Freight', 0), errors='coerce'), 
                        'Credit': 0
                    })
                # Broker Side (Hiring charges)
                b_trips = df_t[df_t['Broker'] == sel_a]
                for _, r in b_trips.iterrows():
                    ledger_entries.append({
                        'Date': r.get('Date', date.today()), 
                        'Particulars': f"LR: {r.get('LR No','--')} (Market Hired Charges)", 
                        'Debit': 0, 
                        'Credit': pd.to_numeric(r.get('HiredCharges', 0), errors='coerce')
                    })

            # 2. PAYMENTS DATA (Cash Flow)
            if not df_p.empty:
                p_entries = df_p[df_p['Account_Name'] == sel_a]
                for _, r in p_entries.iterrows():
                    amt = pd.to_numeric(r.get('Amount', 0), errors='coerce')
                    mode = r.get('Mode', 'N/A')
                    ref = r.get('Ref_No', r.get('Ref No', 'N/A'))
                    
                    if "Receipt" in str(r.get('Type','')):
                        ledger_entries.append({'Date': r.get('Date', date.today()), 'Particulars': f"Payment Recd ({mode}) Ref:{ref}", 'Debit': 0, 'Credit': amt})
                    else:
                        ledger_entries.append({'Date': r.get('Date', date.today()), 'Particulars': f"Payment Paid ({mode}) Ref:{ref}", 'Debit': amt, 'Credit': 0})

            # --- RENDER TABLE & PDF ---
            if ledger_entries:
                full_df = pd.DataFrame(ledger_entries)
                full_df['Date'] = pd.to_datetime(full_df['Date']).dt.date
                full_df = full_df.sort_values(by=['Date'])
                
                # Dynamic Balance Calculation
                full_df['Balance'] = (full_df['Debit'] - full_df['Credit']).cumsum()
                
                # Summary Metrics
            st.divider()
            m1, m2, m3 = st.columns(3)
            dr_total = full_df['Debit'].sum()
            cr_total = full_df['Credit'].sum()
            bal = dr_total - cr_total
            
            # --- Ye rahi wo line jaha error tha, ab bilkul sahi hai ---
            m1.metric("Total Billed (DR)", f"₹{dr_total:,.0f}")
            m2.metric("Total Paid (CR)", f"₹{cr_total:,.0f}")
            
            status_text = "Receivable" if bal > 0 else "Payable"
            m3.metric(f"Net {status_text}", f"₹{abs(bal):,.0f}")
            
            st.write(f"#### Ledger History: {sel_a}")
            st.dataframe(full_df, use_container_width=True, hide_index=True)
elif menu == "5. Business Insights":
    st.header("📊 Business Dashboard & Own Fleet Analytics")
    
    # 1. Fresh Data Load
    df_t = load("trips")
    df_oe = load("office_expenses")
    
    if not df_t.empty:
        # Data Cleaning: Headers aur Numbers fix karna
        df_t.columns = [str(c).strip() for c in df_t.columns]
        num_cols = ['Freight', 'HiredCharges', 'Diesel', 'DriverExp', 'Toll', 'Other']
        for col in num_cols:
            if col in df_t.columns:
                df_t[col] = pd.to_numeric(df_t[col], errors='coerce').fillna(0)

        # Office Expense Total Calculation
        off_total = 0
        if not df_oe.empty:
            df_oe.columns = [str(c).strip() for c in df_oe.columns]
            off_total = pd.to_numeric(df_oe['Amount'], errors='coerce').fillna(0).sum()

        # Business KPI Calculations
        t_rev = df_t['Freight'].sum()
        # Trip specific costs (Diesel + Toll + Driver + Broker Dues)
        trip_costs = df_t[['HiredCharges', 'Diesel', 'DriverExp', 'Toll', 'Other']].sum().sum()
        # Final Profit = Total Freight - (Trip Costs + Office Costs)
        f_profit = t_rev - (trip_costs + off_total)
        
        # --- UI LAYOUT ---
        t_sum, t_own = st.tabs(["📈 Overview", "🚛 Own Vehicle Profit"])

        with t_sum:
            st.subheader("Total Performance Summary")
            # Metrics Row
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Revenue", f"₹{t_rev:,.0f}")
            m2.metric("Total Expenses (Trip+Off)", f"₹{(trip_costs + off_total):,.0f}")
            m3.metric("Final Net Profit", f"₹{f_profit:,.0f}", delta=f"Office: ₹{off_total:,.0f}", delta_color="inverse")
            
            st.divider()
            
            cl, cr = st.columns(2)
            with cl:
                st.write("#### 🏆 Top Parties (By Revenue)")
                p_data = df_t.groupby('Party')['Freight'].sum().sort_values(ascending=False).head(5)
                st.bar_chart(p_data)
            with cr:
                st.write("#### 📊 Trip Distribution & Revenue")
                dist = df_t.groupby('Type').agg({'Type': 'count', 'Freight': 'sum'}).rename(columns={'Type': 'Trips', 'Freight': 'Revenue'})
                st.dataframe(dist.style.format({'Revenue': '₹{:,.0f}'}), use_container_width=True)

        with t_own:
            # Filter for Own Fleet only
            df_own = df_t[df_t['Type'] == "Own Fleet"].copy()
            if not df_own.empty:
                st.subheader("🚛 Individual Own Vehicle Performance")
                # Grouping by Vehicle
                v_an = df_own.groupby('Vehicle').agg({
                    'Freight': 'sum', 
                    'Diesel': 'sum', 
                    'DriverExp': 'sum', 
                    'Toll': 'sum', 
                    'Other': 'sum'
                }).reset_index()
                
                v_an['Total_Exp'] = v_an[['Diesel', 'DriverExp', 'Toll', 'Other']].sum(axis=1)
                v_an['Net_Profit'] = v_an['Freight'] - v_an['Total_Exp']
                v_an = v_an.sort_values(by='Net_Profit', ascending=False)
                
                st.success(f"💰 Own Fleet Net Profit: ₹{v_an['Net_Profit'].sum():,.2f}")
                
                # Visual Chart
                st.bar_chart(v_an.set_index('Vehicle')['Net_Profit'])
                
                # Formatted Table
                st.dataframe(
                    v_an, 
                    column_config={
                        "Freight": st.column_config.NumberColumn("Revenue", format="₹%d"),
                        "Total_Exp": st.column_config.NumberColumn("Expenses", format="₹%d"),
                        "Net_Profit": st.column_config.NumberColumn("Net Profit", format="₹%d"),
                    },
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.warning("Own Fleet data not found. Please check LR Entry.")
    else:
        st.error("No trip data found. Please add LR entries first.")
elif menu == "6. Expense Manager":
    st.header("🏢 Office & General Expense Manager")
    
    # 1. Load Office Expense Data
    df_oe = load("office_expenses")
    
    tab_add, tab_view = st.tabs(["➕ Add Expense", "📊 View Expenses"])
    
    with tab_add:
        with st.form("office_exp_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                e_date = st.date_input("Date", date.today())
                # Category choices for office expenses
                e_cat = st.selectbox("Category", ["Office Rent", "Electricity", "Staff Salary", "Stationery", "Tea/Coffee", "Repairs", "Others"])
            with col2:
                e_amt = st.number_input("Amount (₹)", min_value=0.0)
                e_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque"])
            
            e_desc = st.text_input("Description (e.g. Electricity bill for March)")
            
            if st.form_submit_button("Save Office Expense"):
                if e_amt > 0:
                    # Saving to 'office_expenses' sheet
                    if save("office_expenses", [str(e_date), e_cat, e_desc, e_amt, e_mode]):
                        st.success("Office Expense Saved Successfully!")
                        st.rerun()

    with tab_view:
        if not df_oe.empty:
            df_oe.columns = [str(c).strip() for c in df_oe.columns]
            st.subheader("Monthly Expense Summary")
            st.dataframe(df_oe, use_container_width=True)
            st.info(f"Total Office Expenses: ₹{pd.to_numeric(df_oe['Amount'], errors='coerce').sum():,.2f}")
        else:
            st.warning("કોઈ ઓફિસ ખર્ચ મળ્યો નથી.")
elif menu == "7. Driver Khata":
    st.header("🚛 Driver Khata & Trip Settlement")
    
    # Data Load
    df_dk = load("driver_khata")
    df_t = load("trips")
    drivers = gl("Driver")
    
    tab_entry, tab_settle = st.tabs(["➕ Add Entry (Salary/Extra)", "📖 Driver Settlement & Ledger"])
    
    with tab_entry:
        st.subheader("Extra Advance or Salary Entry")
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
                    # Salary/Advance is Debit for Driver
                    if save("driver_khata", [str(d_date), d_name, "N/A", "Debit", d_amt, d_note]):
                        st.success(f"Saved for {d_name}"); st.rerun()

    with tab_settle:
        # Dhyaan dein: Ye line 'with' se exactly 4 spaces aage hai
        sel_d = st.selectbox("Choose Driver for Final Settlement", ["Select"] + drivers)
        
        if sel_d != "Select":
            st.divider()
            
            # --- 1. AUTO-FETCH FROM TRIPS ---
            st.write(f"### 🔍 Trip Summary for {sel_d}")
            if not df_t.empty:
                # Column cleaning
                df_t.columns = [str(c).strip() for c in df_t.columns]
                # Filter trips for selected driver
                d_trips = df_t[df_t['Driver'] == sel_d].copy()
                
                if not d_trips.empty:
                    # Number conversion for math
                    for c in ['Diesel', 'DriverExp', 'Toll']:
                        if c in d_trips.columns:
                            d_trips[c] = pd.to_numeric(d_trips[c], errors='coerce').fillna(0)
                    
                    t_adv = d_trips['DriverExp'].sum() if 'DriverExp' in d_trips.columns else 0
                    t_dsl = d_trips['Diesel'].sum() if 'Diesel' in d_trips.columns else 0
                    
                    c1, c2 = st.columns(2)
                    c1.metric("Trip Advance (Pending)", f"₹{t_adv:,.0f}")
                    c2.metric("Trip Diesel (Total)", f"₹{t_dsl:,.0f}")

                    # --- IMPORT BUTTON ---
                    if st.button(f"📥 Import ₹{t_adv} to Personal Ledger"):
                        # Save entry to driver_khata sheet
                        if save("driver_khata", [str(date.today()), sel_d, "Trips", "Debit", t_adv, "Auto-Import from Trips"]):
                            st.success("Trip Advance Imported Successfully!"); st.rerun()
                else:
                    st.info("Is driver ki koi trip history nahi mili.")

            # --- 2. PERSONAL LEDGER (SALARY/EXTRA) ---
            st.write(f"### 📜 Personal Ledger (Salary/Extra)")
            if not df_dk.empty:
                df_dk.columns = [str(c).strip() for c in df_dk.columns]
                d_hist = df_dk[df_dk['Driver_Name'] == sel_d]
                
                # Metrics for Personal Khata
                total_p = pd.to_numeric(d_hist['Amount'], errors='coerce').sum() if not d_hist.empty else 0
                st.warning(f"Total Personal Dues: ₹{total_p:,.2f}")
                
                st.dataframe(d_hist, use_container_width=True, hide_index=True)


























