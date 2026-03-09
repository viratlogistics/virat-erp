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

# --- 2. PROFESSIONAL PDF ENGINE (UPDATED FOR DYNAMIC BRANCH/BANK) ---
def generate_lr_pdf(lr_data, show_fr=True):
    pdf = FPDF()
    pdf.add_page()
    
    # Helper to clean data and handle both Sheet Names & App Names
    def g(key, alt_key=""):
        val = lr_data.get(key, lr_data.get(alt_key, ""))
        return str(val) if val is not None else ""

    pdf.set_font("Arial", 'B', 18); pdf.cell(100, 8, "Virat Logistics", ln=1)
    # Branch details from master if available, else blank
    pdf.set_font("Arial", '', 8); pdf.cell(190, 4, f"Address: {g('BrAddr', 'Address')}", ln=True)
    pdf.cell(190, 4, f"GST No: {g('BrGST', 'GST')}", ln=True); pdf.ln(5)
    pdf.line(10, 35, 200, 35); pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 9)
    # LR No, Date, Vehicle (Ye aapka aa raha hai, isse waise hi rakha hai)
    pdf.cell(45, 8, f"LR No: {g('LR No')}", 1); pdf.cell(45, 8, f"Date: {g('Date')}", 1)
    pdf.cell(50, 8, f"Vehicle: {g('Vehicle')}", 1); pdf.cell(50, 8, f"Risk: {g('Risk', 'At Owner Risk')}", 1, ln=True)
    
    pdf.ln(2); pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 6, "CONSIGNOR", 1, 0, 'C', True); pdf.cell(63, 6, "CONSIGNEE", 1, 0, 'C', True); pdf.cell(64, 6, "BILLING PARTY", 1, 1, 'C', True)
    
    # YAHAN FIX KIYA HAI: Sheet ke columns ko PDF se link kiya hai
    pdf.set_font("Arial", '', 8); y_s = pdf.get_y()
    cnor_info = f"{g('Consignor', 'Cnor')}\nGST: {g('Consignor_GST', 'CnorGST')}"
    pdf.multi_cell(63, 5, cnor_info, 1, 'L'); y_e1 = pdf.get_y()
    
    pdf.set_y(y_s); pdf.set_x(73)
    cnee_info = f"{g('Consignee', 'Cnee')}\nGST: {g('Consignee_GST', 'CneeGST')}"
    pdf.multi_cell(63, 5, cnee_info, 1, 'L'); y_e2 = pdf.get_y()
    
    pdf.set_y(y_s); pdf.set_x(136)
    bill_info = f"{g('Party', 'BillP')}\nInv: {g('InvNo', '')}"
    pdf.multi_cell(64, 5, bill_info, 1, 'L'); y_e3 = pdf.get_y()
    
    pdf.set_y(max(y_e1, y_e2, y_e3)); pdf.ln(2)
    
    pdf.set_font("Arial", 'B', 8); pdf.cell(190, 6, f"SHIP TO: {g('Consignee_Add', 'ShipTo')}", 1, ln=True)
    pdf.ln(4); pdf.cell(70, 7, "Material", 1); pdf.cell(30, 7, "Pkg", 1); pdf.cell(30, 7, "Weight", 1); pdf.cell(30, 7, "Route", 1); pdf.cell(30, 7, "Freight", 1, ln=True)
    
    pdf.set_font("Arial", '', 8)
    pdf.cell(70, 10, g('Material'), 1)
    pdf.cell(30, 10, g('Pkg'), 1)
    pdf.cell(30, 10, f"{g('Weight', 'NetWt')}", 1)
    pdf.cell(30, 10, f"{g('From', '')}-{g('To', '')}", 1)
    
    amt = f"Rs. {g('Freight')}" if show_fr else "T.B.B."
    pdf.cell(30, 10, amt, 1, ln=True); pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, f"BANK: {g('BankInfo', 'N/A')} | Freight Paid By: {g('Paid_By', 'PaidBy')}", ln=True)
    pdf.ln(10); pdf.cell(95, 5, "Consignor Sign", 0, 0, 'L'); pdf.cell(95, 5, "For VIRAT LOGISTICS", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')
# --- 3. MAIN LOGIC ---
df_m = load("masters")
df_t = load("trips")

if 'reset_trigger' not in st.session_state: st.session_state.reset_trigger = 0
if 'pdf_ready' not in st.session_state: st.session_state.pdf_ready = None

menu = st.sidebar.selectbox("🚀 MENU", ["1. Masters Setup", "2. LR Entry", "3. LR Register"])

if menu == "1. Masters Setup":
    st.header("🏗️ Master Management")
    m_type = st.selectbox("Category", ["Party", "Broker", "Vehicle", "Driver", "Bank", "Branch"])
    
    # Edit State Check
    if 'm_edit_idx' not in st.session_state: st.session_state.m_edit_idx = None

    # Form for Add/Edit
    with st.form("m_form", clear_on_submit=True):
        # Agar Edit mode hai toh purana data dikhao, nahi toh khali
        ed_m = df_m.iloc[st.session_state.m_edit_idx] if st.session_state.m_edit_idx is not None else {}
        
        n = st.text_input("Name", value=ed_m.get('Name', ''))
        g = st.text_input("GST/Account No", value=ed_m.get('GST', ''))
        a = st.text_area("Address", value=ed_m.get('Address', ''))
        
        btn_label = "Update Master" if st.session_state.m_edit_idx is not None else "Add Master"
        if st.form_submit_button(btn_label):
            if n:
                if st.session_state.m_edit_idx is not None:
                    # Update Logic: Pehle purana delete fir naya add
                    sh.worksheet("masters").delete_rows(int(st.session_state.m_edit_idx) + 2)
                    st.session_state.m_edit_idx = None
                save("masters", [m_type, n, g, a])
                st.success("Master Updated!"); st.rerun()

    if st.session_state.m_edit_idx is not None:
        if st.button("Cancel Edit"): st.session_state.m_edit_idx = None; st.rerun()

    st.divider()
    # Display List with Edit & Delete Buttons
    if not df_m.empty:
        curr = df_m[df_m['Type'] == m_type]
        for i, r in curr.iterrows():
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.write(f"**{r['Name']}** | {r.get('GST','')}")
            # EDIT Button
            if c2.button("✏️", key=f"medit_{i}"):
                st.session_state.m_edit_idx = i
                st.rerun()
            # DELETE Button
            if c3.button("🗑️", key=f"mdel_{i}"):
                sh.worksheet("masters").delete_rows(int(i) + 2)
                st.rerun()

elif menu == "2. LR Entry":
    st.header("📝 Professional LR Entry")
    if st.button("🆕 RESET FORM"):
        st.session_state.reset_trigger += 1; st.session_state.pdf_ready = None; st.rerun()

    k = st.session_state.reset_trigger
    def gl(t): return sorted(df_m[df_m['Type'] == t]['Name'].unique().tolist()) if not df_m.empty else []
    
    # Agar Edit mode on hai toh data load karo
if st.session_state.get('edit_lr_idx') is not None:
    ed = df_t.iloc[st.session_state.edit_lr_idx]
else:
    ed = {}

# Ab text_input mein 'value' parameter ka use kijiye
with cp1:
    # ... Branch Select ...
    lr_no = st.text_input("LR Number*", value=str(ed.get('LR No', '')), key=f"lrno_{k}")
with cp2:
    cnor_name = st.text_input("Consignor Name*", value=str(ed.get('Consignor', '')), key=f"cnor_{k}")
    # ... baki fields ...cp1, cp2, cp3 = st.columns(3)
    with cp1:
        sel_br = st.selectbox("Select Branch*", ["Select"] + gl("Branch"), key=f"br_{k}")
        br_row = df_m[(df_m['Name'] == sel_br) & (df_m['Type'] == 'Branch')].iloc[0] if sel_br != "Select" else {}
        br_code = br_row.get('GST', '01') if sel_br != "Select" else "01"
        v_cat = st.radio("Trip Type*", ["Own Fleet", "Market Hired"], horizontal=True, key=f"vcat_{k}")
        lr_mode = st.radio("LR No Mode", ["Auto", "Manual"], horizontal=True, key=f"lrmode_{k}")
        lr_no = st.text_input("LR Number*", value=f"VIL/25-26/{br_code}/{len(df_t)+1:03d}" if lr_mode == "Auto" else "", key=f"lrno_{k}")
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
        bank_row = df_m[(df_m['Name'] == sel_bank) & (df_m['Type'] == 'Bank')].iloc[0] if sel_bank != "Select" else {}

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
            if v_cat == "Own Fleet": 
                dsl, toll, drv = st.number_input("Diesel"), st.number_input("Toll"), st.number_input("Driver Adv")
                hc = 0.0
            else: 
                hc = st.number_input("Hired Charges")
                dsl = toll = drv = 0.0

        if st.form_submit_button("🚀 SAVE LR"):
            if sel_br != "Select" and fr_amt > 0:
                prof = (fr_amt - (hc if v_cat == "Market Hired" else (dsl+toll+drv)))
                row = [str(d), lr_no, v_cat, bill_pty, cnor_name, paid_by, n_wt, c_wt, pkg, risk, mat, ins_by, v_no, "Driver", br_name, fl, tl, fr_amt, (hc if v_cat == "Market Hired" else 0.0), dsl, drv, toll, 0, prof]
                if save("trips", row):
                    # Passing Branch & Bank data to PDF dictionary
                    st.session_state.pdf_ready = {
                        "LR No": lr_no, "Date": str(d), "Vehicle": v_no, "Cnor": cnor_name, "CnorGST": cnor_gst, 
                        "Cnee": cnee_name, "CneeGST": cnee_gst, "BillP": bill_pty, "From": fl, "To": tl, 
                        "Material": mat, "Pkg": pkg, "NetWt": n_wt, "ChgWt": c_wt, "Freight": fr_amt, 
                        "PaidBy": paid_by, "Risk": risk, "InsBy": ins_by, "InvNo": inv_no, "ShipTo": ship_to, 
                        "show_fr": show_fr, 
                        "BrName": sel_br, "BrAddr": br_row.get('Address', ''), "BrGST": br_row.get('GST', ''),
                        "BankInfo": f"{sel_bank} - A/C: {bank_row.get('GST', '')}"
                    }
                    st.success("Saved!"); st.rerun()

    if st.session_state.pdf_ready:
        st.download_button("📥 DOWNLOAD PDF", generate_lr_pdf(st.session_state.pdf_ready, st.session_state.pdf_ready.get('show_fr', True)), f"LR_{st.session_state.pdf_ready['LR No']}.pdf")

elif menu == "3. LR Register":
    st.title("📋 LR REGISTER")
    search = st.text_input("Search LR No / Party Name")
    
    if not df_t.empty:
        # Filtering logic
        df_f = df_t.copy()
        if search:
            df_f = df_f[df_f.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        
        for i, row in df_f.iterrows():
            # Har LR ke liye ek dropdown box
            with st.expander(f"LR: {row.get('LR No', 'N/A')} | {row.get('Consignee', 'N/A')} | ₹{row.get('Freight', 0)}"):
                c1, c2, c3 = st.columns([1, 1, 2])
                
                # ✏️ EDIT BUTTON
               if c1.button("✏️ Edit & Fix PDF", key=f"edit_lr_{i}"):
    # 1. Row index save karo
    st.session_state.edit_lr_idx = i
    # 2. Reset trigger badal do taaki form update ho jaye
    st.session_state.reset_trigger += 1
    # 3. Direct Menu 2 (LR Entry) par jaane ka instruction
    st.success("Data Loaded! Ab upar MENU mein '2. LR Entry' select kijiye.")
    st.rerun()
                
                # 🗑️ DELETE BUTTON
                if c2.button("🗑️ Delete", key=f"del_lr_{i}"):
                    # Sheet se row delete (+2 because of header and 0-index)
                    sh.worksheet("trips").delete_rows(int(i) + 2)
                    st.warning(f"LR {row.get('LR No')} Deleted!")
                    st.rerun()
                
                # 📥 PDF DOWNLOAD
                pdf_bytes = generate_lr_pdf(row.to_dict(), True)
                c3.download_button("📥 Download PDF", pdf_bytes, f"LR_{row.get('LR No')}.pdf", key=f"pdf_reg_{i}")
        
        st.divider()
        st.dataframe(df_f)
    else:
        st.info("No records found in trips sheet.")



