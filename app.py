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

# --- 2. PROFESSIONAL PDF ENGINE (YOUR ORIGINAL CODE) ---
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

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry", "3. LR Register", "4. Financial Ledger"])

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
    def gl(t): return sorted(df_m[df_m['Type'] == t]['Name'].unique().tolist()) if not df_m.empty else []
    
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
        is_np = st.checkbox("New Party?")
        bill_pty = st.text_input("Enter Party Name") if is_np else st.selectbox("Billing Party*", ["Select"] + gl("Party"), key=f"bp_{k}")
        cnor_name = st.text_input("Consignor Name*", key=f"cnor_{k}")
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
            v_no = st.selectbox("Vehicle*", ["Select"] + gl("Vehicle")) if v_cat == "Own Fleet" else st.text_input("Market Vehicle No*")
            br_name = "OWN" if v_cat == "Own Fleet" else st.selectbox("Broker*", ["Select"] + gl("Broker"))
            ship_to = st.text_area("Ship To Address")
        with c2:
            fl, tl = st.text_input("From City"), st.text_input("To City")
            mat, pkg = st.text_input("Material"), st.selectbox("Packaging", ["Drums", "Bags", "Boxes", "Loose", "Pallets"])
            inv_no = st.text_input("Invoice No & Date")
        with c3:
            n_wt, c_wt = st.number_input("Net Wt", min_value=0.0), st.number_input("Chg Wt", min_value=0.0)
            fr_amt = st.number_input("Total Freight*", min_value=0.0)
            show_fr = st.checkbox("Show Freight in PDF?", value=True)
            # --- OWN/HIRE LOGIC RE-INSTATED ---
            if v_cat == "Own Fleet": 
                dsl, toll, drv = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Adv")
                hc = 0.0
            else: 
                hc = st.number_input("Hired Charges")
                dsl = toll = drv = 0.0

        if st.form_submit_button("🚀 SAVE LR"):
            if bill_pty != "Select" and fr_amt > 0:
                prof = (fr_amt - (hc if v_cat == "Market Hired" else (dsl+toll+drv)))
                row = [str(d), lr_no, v_cat, bill_pty, cnor_name, paid_by, n_wt, c_wt, pkg, risk, mat, ins_by, v_no, "Driver", br_name, fl, tl, fr_amt, (hc if v_cat == "Market Hired" else 0.0), dsl, drv, toll, 0, prof]
                if save("trips", row):
                    st.session_state.pdf_ready = {"LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Cnor": cnor_name, "CnorGST": cnor_gst, "Cnee": cnee_name, "CneeGST": cnee_gst, "BillP": bill_pty, "From": fl, "To": tl, "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "Freight": fr_amt, "PaidBy": paid_by, "Bank": sel_bank, "Risk": risk, "InsBy": ins_by, "InvNo": inv_no, "ShipTo": ship_to, "show_fr": show_fr}
                    st.success("Saved!"); st.rerun()

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, st.session_state.pdf_ready.get('show_fr', True)), f"LR_{st.session_state.pdf_ready['LR No']}.pdf")

elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    if not df_t.empty:
        for i, row in df_t.iterrows():
            with st.expander(f"LR: {row.get('LR No', 'N/A')} | {row.get('Consignee', 'N/A')}"):
                st.download_button("📥 PDF", generate_lr_pdf(row.to_dict(), True), f"LR_{row.get('LR No','VL')}.pdf", key=f"p_{i}")
        st.dataframe(df_t)
# --- 4. FINANCIAL LEDGER (SIMPLIFIED: ALL NAMES IN ONE LIST) ---
elif menu == "4. Financial Ledger":
    st.title("💳 Financial Management")
    t1, t2 = st.tabs(["➕ Add Transaction", "📑 Statement Report"])
    
    with t1:
        st.subheader("Record Transaction (Paisa Aaya/Diya)")
        with st.form("ledger_entry_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            
            # Transaction Type: Aaya ya Diya
            l_type = c1.radio("Transaction*", ["Received (Paisa Aaya)", "Paid (Paisa Diya)"], horizontal=True)
            l_date = c2.date_input("Date", date.today())
            
            # --- SAB NAAM EK SAATH ---
            all_names = []
            if not df_m.empty:
                # Party aur Broker dono ke naam ek hi list mein dalo
                m_filter = df_m[df_m['Type'].isin(['Party', 'Broker'])]
                all_names = sorted(m_filter['Name'].unique().tolist())
            
            l_name = st.selectbox("Select Party / Broker Name*", ["Select"] + all_names)
            
            c3, c4 = st.columns(2)
            l_amt = c3.number_input("Amount*", min_value=0.0)
            l_mode = c4.selectbox("Mode", ["Bank Transfer", "Cash", "Cheque", "TDS/Other"])
            l_rem = st.text_input("Remarks (Invoice, LR No, etc.)")
            
            # Submit Button
            if st.form_submit_button("Save Transaction"):
                if l_name != "Select" and l_amt > 0:
                    # Naam ke sath Category bhi nikal lo taaki report mein dikhe
                    row_data = df_m[df_m['Name'] == l_name].iloc[0]
                    l_cat = row_data['Type']
                    
                    save("payments", [str(l_date), l_cat, l_type, l_name, l_amt, l_mode, l_rem])
                    st.success(f"✅ Saved: ₹{l_amt} for {l_name} ({l_cat})")
                    st.rerun()

    with t2:
        st.subheader("Hisaab-Kitaab (Report)")
        # Report mein bhi wahi common list rakhte hain
        r_name = st.selectbox("Select Name for Statement", ["Select"] + all_names, key="rep_name_common")
        
        if r_name != "Select":
            df_p = load("payments")
            # Is naam ki category dhoondho (Party hai ya Broker)
            r_cat = df_m[df_m['Name'] == r_name].iloc[0]['Type']
            
            if r_cat == "Party":
                # PARTY REPORT
                billed_df = df_t[df_t['Party'] == r_name]
                b_total = safe_float(billed_df['Freight'].sum())
                paid_df = df_p[df_p['Name'] == r_name]
                p_total = safe_float(paid_df['Amount'].sum())
                
                st.info(f"Account Type: {r_cat}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Billed", f"₹{b_total:,.2f}")
                c2.metric("Total Received", f"₹{p_total:,.2f}")
                c3.metric("Balance Due", f"₹{b_total - p_total:,.2f}")
            else:
                # BROKER REPORT
                payable_df = df_t[df_t['Broker'] == r_name]
                # Hired Charges usually 18th column
                py_total = safe_float(payable_df.iloc[:, 18].sum()) if not payable_df.empty else 0.0
                p_paid_df = df_p[df_p['Name'] == r_name]
                p_paid_total = safe_float(p_paid_df['Amount'].sum())
                
                st.info(f"Account Type: {r_cat}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Hired Payable", f"₹{py_total:,.2f}")
                c2.metric("Total Paid", f"₹{p_paid_total:,.2f}")
                c3.metric("Balance to Pay", f"₹{py_total - p_paid_total:,.2f}")
            
            st.divider()
            st.write("📊 Trip / Biling History")
            st.dataframe(billed_df if r_cat == "Party" else payable_df, use_container_width=True)
            st.write("💵 Payment History")
            st.dataframe(df_p[df_p['Name'] == r_name], use_container_width=True)
