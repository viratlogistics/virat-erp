import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

# ---------------- GOOGLE SHEET CONNECTION ---------------- #

@st.cache_resource
def connect_sheet():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(
            info,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
        return client.open("Virat_Logistics_Data")
    except:
        return None

sh = connect_sheet()


def load_data(sheet):
    try:
        ws = sh.worksheet(sheet)
        data = ws.get_all_records()

        if len(data) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    except:
        return pd.DataFrame()


def save_row(sheet, row):
    try:
        sh.worksheet(sheet).append_row(row, value_input_option="USER_ENTERED")
        return True
    except:
        return False


# ---------------- PDF GENERATOR ---------------- #

def generate_lr_pdf(data, show_freight):

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(130, 8, data["BrName"], 0)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(60, 8, f"GST: {data['BrGST']}", 0, 1, "R")

    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(190, 4, data["BrAddr"])

    pdf.line(10, 30, 200, 30)

    pdf.ln(5)

    # HEADER BOX
    pdf.set_font("Arial", "B", 10)

    pdf.cell(60, 8, f"LR NO : {data['LR No']}", 1)
    pdf.cell(60, 8, f"DATE : {data['Date']}", 1)
    pdf.cell(70, 8, f"VEHICLE : {data['Vehicle']}", 1, 1)

    pdf.ln(4)

    # PARTY BOX
    pdf.set_font("Arial", "B", 9)
    pdf.cell(95, 6, "CONSIGNOR", 1)
    pdf.cell(95, 6, "CONSIGNEE", 1, 1)

    pdf.set_font("Arial", "", 8)
    pdf.cell(95, 8, data["Consignor"], 1)
    pdf.cell(95, 8, data["Consignee"], 1, 1)

    pdf.ln(4)

    # MATERIAL TABLE
    pdf.set_font("Arial", "B", 9)

    pdf.cell(50, 7, "Material", 1)
    pdf.cell(20, 7, "Pkg", 1)
    pdf.cell(30, 7, "Articles", 1)
    pdf.cell(30, 7, "Weight", 1)
    pdf.cell(30, 7, "Route", 1)
    pdf.cell(30, 7, "Freight", 1, 1)

    pdf.set_font("Arial", "", 8)

    freight = f"Rs {data['Freight']}" if show_freight else "T.B.B."

    pdf.cell(50, 8, data["Material"], 1)
    pdf.cell(20, 8, "BOX", 1)
    pdf.cell(30, 8, str(data["Articles"]), 1)
    pdf.cell(30, 8, str(data["Weight"]), 1)
    pdf.cell(30, 8, f"{data['From']} - {data['To']}", 1)
    pdf.cell(30, 8, freight, 1, 1)

    pdf.ln(6)

    # RISK BOX
    pdf.set_font("Arial", "B", 9)

    risk_text = f"Risk : {data['Risk']}"

    pdf.cell(190, 8, risk_text, 1, 1)

    pdf.ln(10)

    pdf.cell(95, 6, "Consignor Sign", 0)
    pdf.cell(95, 6, "For Virat Logistics", 0, 1, "R")

    return pdf.output(dest="S").encode("latin-1")


# ---------------- LOAD DATA ---------------- #

df_m = load_data("masters")
df_t = load_data("trips")

# ---------------- MENU ---------------- #

menu = st.sidebar.selectbox("MENU", ["Masters Setup", "LR Entry"])

# ---------------- MASTERS ---------------- #

if menu == "Masters Setup":

    st.header("Masters Setup")

    mtype = st.radio(
        "Category",
        ["Party", "Branch", "Vehicle", "Broker", "Bank"],
        horizontal=True,
    )

    with st.form("master_form"):

        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Name")
            code = st.text_input("GST / Branch Code")

        with col2:
            contact = st.text_input("Contact")
            addr = st.text_area("Address")

        if st.form_submit_button("Save"):

            if name:
                save_row("masters", [mtype, name, code, addr, contact])
                st.success("Saved")
                st.rerun()

    if not df_m.empty:
        st.dataframe(df_m[df_m["Type"] == mtype])


# ---------------- LR ENTRY ---------------- #

if menu == "LR Entry":

    st.header("LR Entry")

    branches = df_m[df_m["Type"] == "Branch"]
    parties = df_m[df_m["Type"] == "Party"]
    vehicles = df_m[df_m["Type"] == "Vehicle"]
    brokers = df_m[df_m["Type"] == "Broker"]

    c1, c2, c3 = st.columns(3)

    # BRANCH
    with c1:

        branch = st.selectbox(
            "Branch",
            ["Select"] + branches["Name"].tolist()
        )

        if branch != "Select":
            br_data = branches[branches["Name"] == branch].iloc[0]
            branch_code = br_data["GST"]
        else:
            branch_code = ""

    # MODE
    with c2:

        lr_mode = st.radio(
            "LR Mode",
            ["Auto", "Manual"],
            horizontal=True,
        )

    # LR NUMBER
    with c3:

        fy = "25-26"
        next_no = 1

        if not df_t.empty and "LR No" in df_t.columns and branch_code != "":
            branch_lrs = df_t[
                df_t["LR No"].astype(str).str.contains(branch_code)
            ]
            next_no = len(branch_lrs) + 1

        auto_lr = f"VIL/{fy}/{branch_code}/{next_no:03d}"

        if lr_mode == "Auto":
            lr_no = auto_lr
            st.text_input("LR Number", value=lr_no, disabled=True)
        else:
            lr_no = st.text_input("LR Number")

    st.divider()

    # PARTY
    col1, col2, col3 = st.columns(3)

    billing = col1.selectbox("Billing Party", ["Select"] + parties["Name"].tolist())
    consignor = col2.selectbox("Consignor", ["Select"] + parties["Name"].tolist())
    consignee = col3.selectbox("Consignee", ["Select"] + parties["Name"].tolist())

    st.divider()

    trip_type = st.radio("Vehicle Type", ["Own Fleet", "Market Hired"], horizontal=True)

    vehicle = ""
    diesel = 0
    toll = 0
    drv = 0
    hired = 0

    if trip_type == "Own Fleet":

        vehicle = st.selectbox("Vehicle", ["Select"] + vehicles["Name"].tolist())

        e1, e2, e3 = st.columns(3)

        diesel = e1.number_input("Diesel Expense", min_value=0.0)
        toll = e2.number_input("Toll Expense", min_value=0.0)
        drv = e3.number_input("Driver Advance", min_value=0.0)

    else:

        vehicle = st.text_input("Market Vehicle No")

        broker = st.selectbox("Broker", ["Select"] + brokers["Name"].tolist())

        hired = st.number_input("Hired Charges", min_value=0.0)

    st.divider()

    with st.form("trip_form"):

        c1, c2, c3 = st.columns(3)

        with c1:
            lr_date = st.date_input("Date", date.today())
            from_loc = st.text_input("From")

        with c2:
            to_loc = st.text_input("To")
            material = st.text_input("Material")

        with c3:
            articles = st.number_input("Articles", min_value=1)
            weight = st.number_input("Weight")

        freight = st.number_input("Freight", min_value=0.0)

        show_fr = st.checkbox("Print Freight", True)

        risk = st.radio("Risk Type", ["Owner Risk", "Insured"])

        if st.form_submit_button("SAVE & GENERATE LR"):

            if not df_t.empty and "LR No" in df_t.columns:
                if lr_no in df_t["LR No"].values:
                    st.error("LR already exists")
                    st.stop()

            if trip_type == "Market Hired":
                profit = freight - hired
            else:
                profit = freight - diesel - toll - drv

            row = [
                str(lr_date),
                lr_no,
                billing,
                consignor,
                consignee,
                vehicle,
                from_loc,
                to_loc,
                material,
                articles,
                weight,
                freight,
                profit,
            ]

            if save_row("trips", row):

                st.success("LR Saved")

                pdf_data = {
                    "LR No": lr_no,
                    "Date": str(lr_date),
                    "Vehicle": vehicle,
                    "BrName": branch,
                    "BrGST": branch_code,
                    "BrAddr": br_data.get("Address", ""),
                    "Consignor": consignor,
                    "Consignee": consignee,
                    "Material": material,
                    "Articles": articles,
                    "Weight": weight,
                    "From": from_loc,
                    "To": to_loc,
                    "Freight": freight,
                    "Risk": risk,
                }

                pdf = generate_lr_pdf(pdf_data, show_fr)

                st.download_button(
                    "DOWNLOAD LR PDF",
                    pdf,
                    f"{lr_no}.pdf"
                )
