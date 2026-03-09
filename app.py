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

def safe_float(val):
    try:
        if val == "" or val is None: return 0.0
        return float(val)
    except: return 0.0

# --- 2. PROFESSIONAL PDF ENGINE (FREIGHT HIDE SUPPORT) ---
def generate_lr_pdf(lr, show_fr=True):
    pdf = FPDF()
    pdf.add_page()
    def s(v): return str(v) if v is not None else ""
    pdf.set_font("Arial", 'B', 18); pdf.cell(100, 8, s(lr.get('BrName', 'Virat Logistics')), ln=1)
    pdf.set_font("Arial", '', 8); pdf.cell(190, 4, f"Address: {s(lr.get('BrAddr', ''))}", ln=True)
    pdf.cell(190, 4, f"GST No: {s(lr.get('BrGST', ''))}", ln=True); pdf.ln(5)
    pdf.line(10, 35, 200, 35); pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 8, f"LR No: {s(lr.get('LR No'))}", 1); pdf.cell(45, 8, f"Date: {s(lr.get('Date'))}", 1)
    pdf.cell(50, 8, f"Vehicle: {s(lr.get('Vehicle'))}", 1); pdf.cell(50, 8, f"Risk: {s(lr.get('Risk', 'At Owner Risk'))}", 1, ln=True)
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 8); y_s = pdf.get_y()
    pdf.multi_cell(63, 5, f"{s(lr.get('Consignor'))}\nGST: {s(lr.get('CnorGST'))}", 1, 'L'); y_e1 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(73); pdf.multi_cell(63, 5, f"{s(lr.get('Consignee'))}\nGST: {s(lr.get('CneeGST'))}", 1, 'L'); y_e2 = pdf.get_y()
    pdf.set_y(y_s); pdf.set_x(136); pdf.multi_cell(64, 5, f"{s(lr.get('Party', lr.get('BillP')))}\nInv: {s(lr.get('InvNo'))}", 1, 'L'); y_e3 = pdf.get_y()
    pdf.set_y(max(y_e1, y_e2, y_e3)); pdf.ln(2)
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {s(lr.get('ShipTo', 'N/A'))}", 1, ln=True)
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    pdf.set_font("Arial", '', 8)
    pdf.cell(70, 10, s(lr.get('Material')), 1); pdf.cell(30, 10, s(lr.get('Pkg')), 1); pdf.cell(30, 10, s(lr.get('Weight', lr.get('NetWt'))), 1); pdf.cell(30, 10, f"{s(lr.get('From'))}-{s(lr.get('To'))}", 1)
    
    # Freight Hide/Show Logic
    amt = f"Rs. {s(lr.get('Freight'))}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True); pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 5, f"BANK: {s(lr.get('BankInfo', 'N/A'))} | Paid By: {s(lr.get('Paid_By', lr.get('PaidBy')))}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN APP ---
df_m, df_t = load("masters"), load("trips")

if 'm_edit_idx' not in st.session_state: st.session_state.m_edit_idx = None
if 'edit_lr_no' not in st.session_state: st.session_state.edit_lr_no = None
if 'reset_k' not in st.session_state: st.session_state.reset_k = 0
if 'last_pdf' not in st.session_state: st.session_state.last_pdf = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry", "3. LR Register", "4. Financial Ledger"])

# MASTER SETUP
if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Bank", "Branch"])
    m_ed = df_m.iloc[st.session_state.m_edit_idx] if st.session_state.m_edit_idx is not None else {}
    with st.form("m_form", clear_on_submit=True):
        n = st.text_input("Name", value=m_ed.get('Name', ''))
        g = st.text_input("GST/Account No", value=m_ed.get('GST', ''))
        a = st.text_area("Address", value=m_ed.get('Address', ''))
        if st.form_submit_button("Save/Update Master"):
            if n:
                if st.session_state.m_edit_idx is not None:
                    sh.worksheet("masters").delete_rows(int(st.session_state.m_edit_idx) + 2)
                    st.session_state.m_edit_idx = None
                save("masters", [m_type, n, g, a]); st.rerun()
    st.divider()
    if not df_m.empty:
        curr = df_m[df_m['Type'] == m_type]
        for i, r in curr.iterrows():
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.write(f"**{r['Name']}** | {r.get('GST','')}")
            if c2.button("✏️", key=f"me_{i}"): st.session_state.m_edit_idx = i; st.rerun()
            if c3.button("🗑️", key=f"md_{i}"): sh.worksheet("masters").delete_rows(int(i) + 2); st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    
    # 1. Edit/Reset Check
    if st.session_state.edit_lr_no:
        st.warning(f"Editing Mode: {st.session_state.edit_lr_no}")
        ed_row = df_t[df_t['LR No'] == st.session_state.edit_lr_no]
        ed = ed_row.iloc[0] if not ed_row.empty else {}
    else: ed = {}

    k = st.session_state.reset_k
    def gl(t): return sorted(df_m[df_m['Type'] == t]['Name'].tolist()) if not df_m.empty else []

    # --- MAIN FORM START ---
    with st.form(f"lr_main_form_{k}"):
        st.subheader("🚛 Vehicle & Route Details")
        cp1, cp2, cp3 = st.columns(3)
        
        with cp1:
            sel_br = st.selectbox("Branch*", ["Select"] + gl("Branch"), key=f"f_br_{k}")
            br_r = df_m[(df_m['Name'] == sel_br) & (df_m['Type'] == 'Branch')].iloc[0] if sel_br != "Select" else {}
            
            # TRIP TYPE SELECTION
            v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"f_vcat_{k}")
            
            sel_broker = "OWN"
            if v_cat == "Market Hired":
                sel_broker = st.selectbox("Select Broker*", ["Select"] + gl("Broker"), key=f"f_broker_{k}")
            
            lr_no = st.text_input("LR No*", value=str(ed.get('LR No', f"VIL/25-26/{br_r.get('GST','01')}/{len(df_t)+1:03d}")), key=f"f_lrno_{k}")

        with cp2:
            bill_p = st.selectbox("Billing Party*", ["Select"] + gl("Party"), key=f"f_bp_{k}")
            # AUTO FETCH FROM MASTER
            p_data = df_m[(df_m['Name'] == bill_p) & (df_m['Type'] == 'Party')].iloc[0] if bill_p != "Select" else {}
            
            cn = st.text_input("Consignor Name", value=str(p_data.get('Name', ed.get('Consignor', ''))), key=f"f_cn_{k}")
            cn_gst = st.text_input("Consignor GST", value=str(p_data.get('GST', '')), key=f"f_cgst_{k}")
            cn_addr = st.text_area("Consignor Address", value=str(p_data.get('Address', '')), key=f"f_caddr_{k}", height=68)

        with cp3:
            ce = st.text_input("Consignee Name", value=str(ed.get('Consignee', '')), key=f"f_ce_{k}")
            ce_gst = st.text_input("Consignee GST", key=f"f_cegst_{k}") # FIXED SYNTAX
            pb = st.selectbox("Paid By*", ["Consignor", "Consignee", "Billing Party"], key=f"f_pb_{k}")
            bk = st.selectbox("Bank*", ["Select"] + gl("Bank"), key=f"f_bk_{k}")

        st.divider()
        st.subheader("📦 Consignment Details")
        f1, f2, f3 = st.columns(3)
        with f1:
            dt = st.date_input("Date", date.today())
            vn = st.text_input("Vehicle No", value=str(ed.get('Vehicle', '')))
            fl = st.text_input("From City", value=str(ed.get('From', '')))
            tl = st.text_input("To City", value=str(ed.get('To', '')))
        
        with f2:
            mt = st.text_input("Material Name", value=str(ed.get('Material', '')))
            pkg = st.selectbox("Packaging Type", ["Bags", "Drums", "Boxes", "Loose", "Pallets", "Other"])
            art = st.number_input("Total Articles (Qty)", min_value=0, step=1)
            nw = st.number_input("Net Weight", value=safe_float(ed.get('Weight', 0.0)))

        with f3:
            cw = st.number_input("Charged Weight", value=safe_float(ed.get('ChargedWeight', 0.0)))
            fr = st.number_input("Total Freight Amount", value=safe_float(ed.get('Freight', 0.0)))
            show_fr = st.checkbox("Show Freight in PDF?", value=True)

        st.divider()
        st.subheader("💰 Trip Expenses")
        ex1, ex2, ex3 = st.columns(3)
        
        if v_cat == "Own Fleet": 
            dsl = ex1.number_input("Diesel Amount", min_value=0.0)
            toll = ex2.number_input("Toll / Border", min_value=0.0)
            drv = ex3.number_input("Driver Advance", min_value=0.0)
            hc = 0.0
        else: 
            hc = ex1.number_input("Hired Charges (Market)", min_value=0.0)
            dsl = toll = drv = 0.0

        if st.form_submit_button("🚀 SAVE LR & GENERATE BILTY"):
            row = [str(dt), lr_no, v_cat, bill_p, cn, cn_gst, cn_addr, ce, ce_gst, pkg, mt, art, vn, sel_broker, fl, tl, fr, cw, nw, (fr-hc-dsl-toll-drv)]
            
            if st.session_state.edit_lr_no:
                try: sh.worksheet("trips").delete_rows(sh.worksheet("trips").find(st.session_state.edit_lr_no).row)
                except: pass
                st.session_state.edit_lr_no = None
            
            save("trips", row)
            st.session_state.last_pdf = {"LR No": lr_no, "Date": str(dt), "Vehicle": vn, "Consignor": cn, "Consignee": ce, "Party": bill_p, "From": fl, "To": tl, "Material": mt, "Weight": nw, "Freight": fr, "Paid_By": pb, "BrName": sel_br, "BrAddr": br_r.get('Address',''), "BrGST": br_r.get('GST',''), "Pkg": pkg, "Art": art, "CWt": cw, "show_fr": show_fr}
            st.session_state.reset_k += 1
            st.rerun()

    if st.session_state.last_pdf:
        st.success(f"✅ Saved Successfully!")
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.last_pdf, st.session_state.last_pdf.get('show_fr', True)), f"LR_{st.session_state.last_pdf['LR No']}.pdf")
        if st.button("Close & Next Entry"): st.session_state.last_pdf = None; st.rerun()
elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR/Party")
    if not df_t.empty:
        df_f = df_t.copy()
        if search: df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        for i, row in df_f.iterrows():
            with st.expander(f"LR: {row['LR No']} | {row['Consignee']}"):
                c1, c2, c3 = st.columns(3)
                if c1.button("✏️ Edit", key=f"e_{i}"): st.session_state.edit_lr_no = row['LR No']; st.rerun()
                if c2.button("🗑️ Delete", key=f"d_{i}"):
                    try: sh.worksheet("trips").delete_rows(sh.worksheet("trips").find(row['LR No']).row); st.rerun()
                    except: st.error("Not found")
                st.download_button("📥 PDF", generate_lr_pdf(row.to_dict(), True), f"LR_{row['LR No']}.pdf", key=f"p_{i}")
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














