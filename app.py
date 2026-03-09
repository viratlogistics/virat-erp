import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
import io
import os

st.set_page_config(layout="wide")

DATA_FILE = "lr_data.csv"
MASTER_FILE = "master_data.csv"


# ---------------------------
# LOAD DATA
# ---------------------------

def load_lr():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=[
            "LR No","Date","Consignor","Consignee","Vehicle",
            "Vehicle Type","Freight","Weight","Articles"
        ])
    return df


def save_lr(df):
    df.to_csv(DATA_FILE,index=False)


def load_master():
    if os.path.exists(MASTER_FILE):
        df = pd.read_csv(MASTER_FILE)
    else:
        df = pd.DataFrame(columns=[
            "Company Name",
            "Address",
            "GST",
            "Branch Code",
            "Phone"
        ])
    return df


def save_master(df):
    df.to_csv(MASTER_FILE,index=False)


df = load_lr()
master = load_master()


# ---------------------------
# SIDEBAR
# ---------------------------

menu = st.sidebar.selectbox(
    "Menu",
    [
        "Create LR",
        "LR Register",
        "Master Settings"
    ]
)


# ---------------------------
# MASTER SETTINGS
# ---------------------------

if menu == "Master Settings":

    st.title("MASTER SETTINGS")

    if len(master)==0:

        company = st.text_input("Company Name")
        address = st.text_area("Address")
        gst = st.text_input("GST Number")
        branch = st.text_input("Branch Code")
        phone = st.text_input("Phone")

        if st.button("Save Master"):
            new = pd.DataFrame([{
                "Company Name":company,
                "Address":address,
                "GST":gst,
                "Branch Code":branch,
                "Phone":phone
            }])

            save_master(new)
            st.success("Master Saved")

    else:

        row = master.iloc[0]

        company = st.text_input("Company Name",row["Company Name"])
        address = st.text_area("Address",row["Address"])
        gst = st.text_input("GST Number",row["GST"])
        branch = st.text_input("Branch Code",row["Branch Code"])
        phone = st.text_input("Phone",row["Phone"])

        if st.button("Update Master"):
            new = pd.DataFrame([{
                "Company Name":company,
                "Address":address,
                "GST":gst,
                "Branch Code":branch,
                "Phone":phone
            }])

            save_master(new)
            st.success("Updated")


# ---------------------------
# CREATE LR
# ---------------------------

if menu == "Create LR":

    st.title("CREATE LR")

    last_lr = 1000
    if len(df)>0 and "LR No" in df.columns:
        try:
            last_lr = int(df["LR No"].max())
        except:
            pass

    lr_no = last_lr + 1

    with st.form("lr_form"):

        col1,col2,col3 = st.columns(3)

        with col1:
            date = st.date_input("Date",datetime.today())
            consignor = st.text_input("Consignor")

        with col2:
            consignee = st.text_input("Consignee")
            vehicle = st.text_input("Vehicle No")

        with col3:
            vehicle_type = st.selectbox(
                "Vehicle Type",
                ["OWN","HIRED"]
            )
            freight = st.number_input("Freight")

        articles = st.text_input("Articles")
        weight = st.number_input("Weight")

        st.markdown("---")

        # OWN EXPENSES
        if vehicle_type == "OWN":

            st.subheader("OWN VEHICLE EXPENSE")

            diesel = st.number_input("Diesel")
            toll = st.number_input("Toll")
            driver = st.number_input("Driver Expense")

        else:

            st.subheader("HIRED VEHICLE DETAILS")

            hire_rate = st.number_input("Hire Rate")
            advance = st.number_input("Advance")

        submitted = st.form_submit_button("SAVE LR")


    # ---------------------------
    # SAVE LR
    # ---------------------------

    if submitted:

        new = pd.DataFrame([{
            "LR No":lr_no,
            "Date":date,
            "Consignor":consignor,
            "Consignee":consignee,
            "Vehicle":vehicle,
            "Vehicle Type":vehicle_type,
            "Freight":freight,
            "Weight":weight,
            "Articles":articles
        }])

        df = pd.concat([df,new],ignore_index=True)

        save_lr(df)

        st.success(f"LR Saved : {lr_no}")

        # ---------------------------
        # PDF GENERATION
        # ---------------------------

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )

        styles = getSampleStyleSheet()

        elements = []

        if len(master)>0:

            m = master.iloc[0]

            elements.append(
                Paragraph(
                    f"<b>{m['Company Name']}</b>",
                    styles["Title"]
                )
            )

            elements.append(
                Paragraph(
                    f"{m['Address']}",
                    styles["Normal"]
                )
            )

            elements.append(
                Paragraph(
                    f"GST : {m['GST']} | Branch : {m['Branch Code']}",
                    styles["Normal"]
                )
            )

        elements.append(Spacer(1,10))

        elements.append(
            Paragraph(
                f"<b>LR No : {lr_no}</b>",
                styles["Heading3"]
            )
        )

        elements.append(
            Paragraph(
                f"Date : {date}",
                styles["Normal"]
            )
        )

        elements.append(Spacer(1,10))

        data = [
            ["Consignor",consignor],
            ["Consignee",consignee],
            ["Vehicle",vehicle],
            ["Vehicle Type",vehicle_type],
            ["Articles",articles],
            ["Weight",weight],
            ["Freight",freight]
        ]

        table = Table(data,colWidths=[120,350])

        table.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),1,colors.grey),
            ("BACKGROUND",(0,0),(0,-1),colors.lightgrey)
        ]))

        elements.append(table)

        elements.append(Spacer(1,20))

        item_table = Table([
            ["No","Description","Weight","Freight"],
            ["1",articles,weight,freight]
        ])

        item_table.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),1,colors.black),
            ("BACKGROUND",(0,0),(-1,0),colors.lightgrey)
        ]))

        elements.append(item_table)

        doc.build(elements)

        pdf = buffer.getvalue()

    # DOWNLOAD BUTTON OUTSIDE FORM

        st.download_button(
            "DOWNLOAD LR PDF",
            pdf,
            file_name=f"LR_{lr_no}.pdf",
            mime="application/pdf"
        )


# ---------------------------
# LR REGISTER
# ---------------------------

if menu == "LR Register":

    st.title("LR REGISTER")

    if len(df)==0:
        st.info("No LR Found")
    else:

        if "LR No" not in df.columns:
            st.error("Column LR No missing")
        else:

            search = st.text_input("Search LR")

            df_t = df.copy()

            if search:

                df_t = df_t[
                    df_t["LR No"].astype(str).str.contains(search)
                ]

            st.dataframe(df_t)
