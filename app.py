import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="Virat Logistics ERP", layout="wide")

# -----------------------------
# GOOGLE SHEET CONNECTION
# -----------------------------

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
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [c.strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()


def save_row(sheet, row):
    try:
        sh.worksheet(sheet).append_row(row, value_input_option="USER_ENTERED")
        return True
    except:
        return False


# -----------------------------
# PDF GENERATOR
# -----------------------------

def generate_lr_pdf(data, show_freight):

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(100, 8, data.get("BrName", "VIRAT LOGISTICS"), 0)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 8, f"GST: {data.get('BrGST','')}", 0, 1, "R")

    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(190, 4, f"Address: {data.get('BrAddr','')}")

    pdf.ln(5)

    pdf.set_font("Arial", "B", 10)

    pdf.cell(60, 8, f"LR No: {data.get('LR No','')}", 1)
    pdf.cell(60, 8, f"Date: {data.get('Date','')}", 1)
    pdf.cell(70, 8, f"Vehicle: {data.get('Vehicle','')}", 1, 1)

    pdf.ln(4)

    pdf.set_font("Arial", "B", 9)

    pdf.cell(95, 6, "Consignor", 1)
    pdf.cell(95, 6, "Consignee", 1, 1)

    pdf.set_font("Arial", "", 8)

    pdf.cell(95, 8, data.get("Cnor",""), 1)
    pdf.cell(95, 8, data.get("Cnee",""), 1, 1)

    pdf.ln(4)

    pdf.cell(60, 7, "Material", 1)
    pdf.cell(20, 7, "Nag", 1)
    pdf.cell(40, 7, "Weight", 1)
    pdf.cell(40, 7, "Route", 1)

    freight = f"Rs {data.get('Freight',0)}" if show_freight else "TBB"

    pdf.cell(30, 7, freight, 1, 1)

    pdf.cell(60, 8, data.get("Material",""), 1)
    pdf.cell(20, 8, str(data.get("Articles","")), 1)
    pdf.cell(40, 8, str(data.get("NetWt","")), 1)
    pdf.cell(40, 8, f"{data.get('From','')} - {data.get('To','')}", 1)
    pdf.cell(30, 8, "", 1, 1)

    return pdf.output(dest="S").encode("latin-1")


# -----------------------------
# LOAD DATA
# -----------------------------

df_m = load_data("masters")
df_t = load_data("trips")

if "pdf_ready" not in st.session_state:
    st.session_state.pdf_ready = None


# -----------------------------
# SIDEBAR
# -----------------------------

menu = st.sidebar.selectbox(
    "MENU",
    ["Masters Setup", "LR Entry"]
)

# -----------------------------
# MASTERS
# -----------------------------

if menu == "Masters Setup":

    st.header("Masters Setup")

    m_type = st.radio(
        "Category",
        ["Party", "Branch", "Vehicle", "Bank", "Broker"],
        horizontal=True,
    )

    with st.form("master_form"):

        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Name")
            gst = st.text_input("GST / Code")

        with col2:
            contact = st.text_input("Contact")
            address = st.text_area("Address")

        if st.form_submit_button("Save"):

            if name:
                save_row(
                    "masters",
                    [m_type, name, gst, address, contact]
                )
                st.success("Saved")
                st.rerun()

    if not df_m.empty:
        st.dataframe(df_m[df_m["Type"] == m_type])


# -----------------------------
# LR ENTRY
# -----------------------------

if menu == "LR Entry":

    st.header("LR Entry")

    branches = df_m[df_m["Type"] == "Branch"]
    parties = df_m[df_m["Type"] == "Party"]
    vehicles = df_m[df_m["Type"] == "Vehicle"]
    brokers = df_m[df_m["Type"] == "Broker"]
    banks = df_m[df_m["Type"] == "Bank"]

    col1, col2, col3 = st.columns(3)

    # -----------------------------
    # BRANCH SELECT
    # -----------------------------

    with col1:

        sel_branch = st.selectbox(
            "Select Branch",
            ["Select"] + branches["Name"].tolist()
        )

        if sel_branch != "Select":
            br_data = branches[branches["Name"] == sel_branch].iloc[0]
            branch_code = br_data["GST"]
        else:
            branch_code = ""

    # -----------------------------
    # MODE
    # -----------------------------

    with col2:

        lr_mode = st.radio(
            "LR Mode",
            ["Auto", "Manual"],
            horizontal=True
        )

    # -----------------------------
    # LR NUMBER
    # -----------------------------

    with col3:

        fy = "25-26"

        if not df_t.empty and branch_code != "":

            branch_lrs = df_t[
                df_t["LR No"].astype(str).str.contains(
                    f"/{branch_code}/",
                    na=False
                )
            ]

            next_no = len(branch_lrs) + 1

        else:
            next_no = 1

        auto_lr = f"VIL/{fy}/{branch_code}/{next_no:03d}"

        if lr_mode == "Auto":

            lr_no = auto_lr
            st.text_input("LR Number", value=lr_no, disabled=True)

        else:

            lr_no = st.text_input("LR Number")

    st.divider()

    # -----------------------------
    # PARTY DETAILS
    # -----------------------------

    col1, col2, col3 = st.columns(3)

    with col1:

        billing = st.selectbox(
            "Billing Party",
            ["Select"] + parties["Name"].tolist()
        )

        consignor = st.selectbox(
            "Consignor",
            ["Select"] + parties["Name"].tolist()
        )

    with col2:

        consignee = st.selectbox(
            "Consignee",
            ["Select"] + parties["Name"].tolist()
        )

        vehicle = st.selectbox(
            "Vehicle",
            ["Select"] + vehicles["Name"].tolist()
        )

    with col3:

        bank = st.selectbox(
            "Bank",
            ["Select"] + banks["Name"].tolist()
        )

        broker = st.selectbox(
            "Broker",
            ["Select"] + brokers["Name"].tolist()
        )

    st.divider()

    # -----------------------------
    # LOAD DETAILS
    # -----------------------------

    with st.form("lr_form"):

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

        show_freight = st.checkbox("Print Freight", True)

        if st.form_submit_button("Save & Generate PDF"):

            if lr_no in df_t.get("LR No", []).values:
                st.error("LR already exists")
                st.stop()

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
            ]

            if save_row("trips", row):

                st.success(f"LR {lr_no} Saved")

                st.session_state.pdf_ready = {
                    "LR No": lr_no,
                    "Date": str(lr_date),
                    "Vehicle": vehicle,
                    "Cnor": consignor,
                    "Cnee": consignee,
                    "Material": material,
                    "Articles": articles,
                    "NetWt": weight,
                    "From": from_loc,
                    "To": to_loc,
                    "Freight": freight,
                    "BrName": sel_branch,
                }

    # -----------------------------
    # PDF DOWNLOAD
    # -----------------------------

    if st.session_state.pdf_ready:

        pdf = generate_lr_pdf(
            st.session_state.pdf_ready,
            show_freight,
        )

        st.download_button(
            "Download LR PDF",
            pdf,
            f"{lr_no}.pdf",
        )
