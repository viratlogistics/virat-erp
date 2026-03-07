import streamlit as st
import pandas as pd
import os
from datetime import date
from fpdf import FPDF

# --- 1. CONFIG & DATA SETUP ---
st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

if not os.path.exists("data"):
    os.makedirs("data")

FILES = {
    "trips": ("data/trips.csv", [
        "Date","LR","Type","Party","Consignor","Consignor_GST","Consignor_Add",
        "Consignee","Consignee_GST","Consignee_Add","Material","Weight",
        "Vehicle","Driver","Broker","From","To","Freight","HiredCharges",
        "Diesel","DriverExp","Toll","Other","Profit"
    ]),
    "payments": ("data/payments.csv", ["Date", "Name", "Category", "Amount", "Mode"]),
    "admin": ("data/admin_expenses.csv", ["Date", "Category", "Amount", "Remarks"])
}

def load_all_data():
    data_dict = {}
    for key, (path, cols) in FILES.items():
        if not os.path.exists(path):
            pd.DataFrame(columns=cols).to_csv(path, index=False)
        df = pd.read_csv(path)
        for c in cols:
            if c not in df.columns: 
                df[c] = 0 if any(x in c for x in ["Amount", "Freight", "Profit", "Charges", "Weight"]) else ""
        data_dict[key] = df[cols]
    return data_dict

data_load = load_all_data()
df_t = data_load["trips"]
df_p = data_load["payments"]
df_a = data_load["admin"]

# --- 2. PDF GENERATION FUNCTIONS ---

def generate_lr_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.set_text_color(211, 47, 47)
    pdf.cell(190, 10, "VIRAT LOGISTICS", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 5, "Transport & Fleet Management", ln=True, align='C')
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
    pdf.set_font("Arial", '', 11)
    pdf.cell(280, 7, f"Party: {party} | Period: {selected_m}", ln=True, align='C')
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

def delete_row(df, index, file_key):
    df = df.drop(index)
    df.to_csv(FILES[file_key][0], index=False)
    st.success("Entry Deleted!")
    st.rerun()

# --- 5. DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Financial Summary")
    trip_prof = pd.to_numeric(df_t["Profit"], errors='coerce').sum()
    adm_exp = pd.to_numeric(df_a["Amount"], errors='coerce').sum()
    t_rev = pd.to_numeric(df_t["Freight"], errors='coerce').sum()
    p_rec = pd.to_numeric(df_p[df_p["Category"]=="Party"]["Amount"]).sum()
    b_work = pd.to_numeric(df_t["HiredCharges"]).sum()
    b_paid = pd.to_numeric(df_p[df_p["Category"]=="Broker"]["Amount"]).sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Trip Profit", f"₹{trip_prof:,.0f}")
    c2.metric("Party Due", f"₹{(t_rev - p_rec):,.0f}")
    c3.metric("Broker Due", f"₹{(b_work - b_paid):,.0f}", delta_color="inverse")
    st.divider()
    st.metric("Total Office Expenses", f"₹{adm_exp:,.0f}")

# --- 6. ADD LR ---
elif menu == "Add LR":
    st.header(f"📝 New LR - No: {len(df_t) + 1001}")
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
        if st.form_submit_button("Save LR"):
            if party and vehicle:
                prof = (freight - (dsl+de+tl+ot)) if v_type == "Own" else (freight - h_chg)
                new_row = [str(d), lr, v_type, party, consignor, con_gst, con_add, consignee, cee_gst, cee_add, mat, wt, vehicle, "Driver", broker, f_loc, t_loc, freight, h_chg, dsl, de, tl, ot, prof]
                pd.concat([df_t, pd.DataFrame([new_row], columns=FILES["trips"][1])], ignore_index=True).to_csv(FILES["trips"][0], index=False)
                st.success("LR Saved!"); st.rerun()
            else: st.error("Mandatory fields missing.")

# --- 7. MONTHLY BILL ---
elif menu == "Monthly Bill":
    st.header("📅 Monthly Summary Bill")
    if not df_t.empty:
        df_t['Date'] = pd.to_datetime(df_t['Date'])
        c1, c2 = st.columns(2)
        with c1: p_name = st.selectbox("Select Party", df_t["Party"].unique())
        with c2: 
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

# --- 8. VEHICLE WISE PROFIT (NEW) ---
elif menu == "Vehicle Profit":
    st.header("🚛 Own Vehicle Profitability Analysis")
    own_trips = df_t[df_t["Type"] == "Own"]
    if not own_trips.empty:
        # Converting to numeric to avoid errors
        own_trips["Freight"] = pd.to_numeric(own_trips["Freight"])
        own_trips["Diesel"] = pd.to_numeric(own_trips["Diesel"])
        own_trips["DriverExp"] = pd.to_numeric(own_trips["DriverExp"])
        own_trips["Toll"] = pd.to_numeric(own_trips["Toll"])
        own_trips["Other"] = pd.to_numeric(own_trips["Other"])
        own_trips["Profit"] = pd.to_numeric(own_trips["Profit"])

        veh_summary = own_trips.groupby("Vehicle").agg({
            "LR": "count",
            "Freight": "sum",
            "Diesel": "sum",
            "Toll": "sum",
            "Profit": "sum"
        }).reset_index()

        veh_summary.rename(columns={"LR": "Total Trips", "Freight": "Total Income", "Profit": "Net Profit"}, inplace=True)
        st.dataframe(veh_summary, use_container_width=True)
        
        # Performance Insight
        best_veh = veh_summary.loc[veh_summary['Net Profit'].idxmax()]
        st.success(f"Best Performing Vehicle: **{best_veh['Vehicle']}** with ₹{best_veh['Net Profit']:,} Profit.")
    else:
        st.info("No 'Own Vehicle' trips found yet.")

# --- 9. PAYMENTS & EXPENSES ---
elif menu in ["Party Receipt", "Broker Payment"]:
    cat = "Party" if menu == "Party Receipt" else "Broker"
    st.header(f"💰 {cat} Transaction")
    with st.form("p_form", clear_on_submit=True):
        names = df_t[cat].unique() if not df_t.empty else []
        p_name = st.selectbox(f"Select {cat}", names)
        p_amt = st.number_input("Amount", 0.0); p_mode = st.selectbox("Mode", ["Cash", "Bank", "Cheque"])
        if st.form_submit_button("Save"):
            new_p = [str(date.today()), p_name, cat, p_amt, p_mode]
            pd.concat([df_p, pd.DataFrame([new_p], columns=FILES["payments"][1])], ignore_index=True).to_csv(FILES["payments"][0], index=False); st.rerun()

elif menu == "Admin Expense":
    st.header("🏢 Admin Expenses")
    with st.form("a_form", clear_on_submit=True):
        a_cat = st.selectbox("Type", ["Staff Salary", "Rent", "Electricity", "Other"])
        a_amt = st.number_input("Amount", 0.0); a_rem = st.text_input("Remarks")
        if st.form_submit_button("Save"):
            new_a = [str(date.today()), a_cat, a_amt, a_rem]
            pd.concat([df_a, pd.DataFrame([new_a], columns=FILES["admin"][1])], ignore_index=True).to_csv(FILES["admin"][0], index=False); st.rerun()
    for i, row in df_a.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.write(f"{row['Date']} - {row['Category']} - ₹{row['Amount']}")
        if c2.button("🗑️", key=f"del_a_{i}"): delete_row(df_a, i, "admin")

# --- 10. REPORTS & LEDGERS ---
elif menu == "LR Report":
    st.header("📋 All Records")
    for i, row in df_t.iterrows():
        with st.expander(f"{row['LR']} | {row['Party']} | {row['Vehicle']}"):
            c1, c2 = st.columns([4, 1])
            c1.write(row)
            if c2.button("🗑️ Delete", key=f"del_lr_{i}"): delete_row(df_t, i, "trips")
            pdf_data = generate_lr_pdf(row)
            c2.download_button("📥 PDF", pdf_data, f"{row['LR']}.pdf", "application/pdf", key=f"pdf_lr_{i}")

elif menu == "Party Ledger":
    st.header("🏢 Party Ledger")
    if not df_t.empty:
        bill = df_t.groupby("Party")["Freight"].sum().reset_index()
        rec = df_p[df_p["Category"]=="Party"]["Amount"].sum() # Simplified for display
        st.dataframe(bill)

elif menu == "Broker Ledger":
    st.header("🤝 Broker Ledger")
    hired = df_t[df_t["Type"] == "Hired"]
    if not hired.empty:
        work = hired.groupby("Broker")["HiredCharges"].sum().reset_index()
        st.dataframe(work)