import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import io
import json

st.set_page_config(page_title="Virat ERP v8.3", layout="wide")

# ---------------- GOOGLE SHEETS ----------------

@st.cache_resource
def get_sh():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json_key"])
        creds = Credentials.from_service_account_info(
            info,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(creds).open("Virat_Logistics_Data")
    except:
        return None

sh = get_sh()


def load_data(sheet):
    try:
        df = pd.DataFrame(sh.worksheet(sheet).get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()


# ---------------- PDF ENGINE ----------------

def generate_pro_pdf(lr):

    lr = {k.strip(): v for k, v in lr.items()}

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    elements = []

    s = lambda x: str(x) if x is not None else ""

    # Header
    elements.append(
        Paragraph(
            f"<font size=18><b>{s(lr.get('BrName','VIRAT LOGISTICS'))}</b></font>",
            styles['Title']
        )
    )

    elements.append(
        Paragraph(
            f"GST : {s(lr.get('BrGST',''))} | Branch : {s(lr.get('BrCode',''))}",
            styles['Normal']
        )
    )

    elements.append(
        Paragraph(
            f"Address : {s(lr.get('BrAddr',''))}",
            styles['Normal']
        )
    )

    elements.append(Spacer(1,15))

    # LR INFO
    info_data = [[
        f"LR No : {s(lr.get('LR No'))}",
        f"Date : {s(lr.get('Date'))}",
        f"Vehicle : {s(lr.get('Vehicle'))}"
    ]]

    t1 = Table(info_data, colWidths=[180,150,180])

    t1.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),1,colors.black),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold")
    ]))

    elements.append(t1)
    elements.append(Spacer(1,10))

    # PARTY TABLE

    party_data = [
        ["CONSIGNOR","CONSIGNEE","BILLING PARTY"],
        [
            s(lr.get("Consignor")),
            s(lr.get("Consignee")),
            s(lr.get("Party"))
        ]
    ]

    t2 = Table(party_data,colWidths=[170,170,170])

    t2.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),1,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.lightgrey)
    ]))

    elements.append(t2)

    elements.append(Spacer(1,15))

    # GOODS

    goods = [
        ["No","Description","Articles","Weight","Freight"],
        [
            "1",
            s(lr.get("Material")),
            s(lr.get("Articles")),
            s(lr.get("Weight")),
            f"Rs {s(lr.get('Freight'))}"
        ]
    ]

    t3 = Table(goods,colWidths=[40,200,70,80,100])

    t3.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),1,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.whitesmoke)
    ]))

    elements.append(t3)

    elements.append(Spacer(1,20))

    elements.append(
        Paragraph(
            f"Route : {s(lr.get('From'))} → {s(lr.get('To'))}",
            styles['Normal']
        )
    )

    doc.build(elements)

    return buffer.getvalue()


# ---------------- LOAD DATA ----------------

df_m = load_data("masters")
df_t = load_data("trips")

if 'reset_k' not in st.session_state:
    st.session_state.reset_k = 0

menu = st.sidebar.selectbox(
    "Menu",
    ["Create LR","LR Register","Master Settings"]
)

# ---------------- MASTER ----------------

def gl(t):
    if df_m.empty:
        return []
    return df_m[df_m["Type"]==t]["Name"].tolist()


# ---------------- CREATE LR ----------------

if menu == "Create LR":

    st.title("CREATE LR")

    if st.button("RESET FORM"):
        st.session_state.reset_k += 1
        st.rerun()

    k = st.session_state.reset_k

    c1,c2,c3 = st.columns(3)

    s_br = c1.selectbox("Branch",["Select"] + gl("Branch"))

    br_row = df_m[df_m["Name"]==s_br]

    if not br_row.empty:
        b_c = br_row["Code"].values[0]
    else:
        b_c = "XX"

    v_cat = c2.radio(
        "Trip Category",
        ["Own Fleet","Market Hired"]
    )

    # LR AUTO NUMBER

    try:
        next_lr = len(df_t) + 1
    except:
        next_lr = 1

    auto_lr = f"VIL/25-26/{b_c}/{next_lr:03d}"

    l_no = c3.text_input(
        "LR Number",
        value=auto_lr
    )

    st.divider()

    cp1,cp2,cp3 = st.columns(3)

    p = cp1.selectbox("Party",["Select"] + gl("Party"))
    cn = cp1.selectbox("Consignor",["Select"] + gl("Party"))
    ce = cp2.selectbox("Consignee",["Select"] + gl("Party"))

    fr_loc = cp3.text_input("From")
    to_loc = cp3.text_input("To")

    with st.form("lr_form"):

        f1,f2,f3 = st.columns(3)

        dt = f1.date_input("Date",date.today())

        if v_cat == "Own Fleet":
            vn = f1.selectbox("Vehicle",["Select"] + gl("Vehicle"))
        else:
            vn = f1.text_input("Vehicle No")

        mt = f1.text_input("Material")

        art = f2.number_input("Articles",min_value=1)

        wt = f2.number_input("Weight")

        f_a = f3.number_input("Freight")

        if st.form_submit_button("SAVE & GENERATE PDF"):

            row = [
                str(dt),
                l_no,
                v_cat,
                p,
                cn,
                "",
                "",
                ce,
                "",
                "",
                mt,
                wt,
                vn,
                "Driver",
                "",
                fr_loc,
                to_loc,
                f_a
            ]

            sh.worksheet("trips").append_row(row)

            st.success(f"LR {l_no} Saved")

            pdf_dict = {
                "LR No":l_no,
                "Date":dt,
                "Vehicle":vn,
                "Consignor":cn,
                "Consignee":ce,
                "Party":p,
                "Material":mt,
                "Articles":art,
                "Weight":wt,
                "Freight":f_a,
                "From":fr_loc,
                "To":to_loc,
                "BrName":"VIRAT LOGISTICS",
                "BrAddr":"Kosamba/Kim Gujarat"
            }

            pdf = generate_pro_pdf(pdf_dict)

            st.download_button(
                "Download LR PDF",
                pdf,
                file_name=f"{l_no}.pdf"
            )


# ---------------- LR REGISTER ----------------

if menu == "LR Register":

    st.title("LR REGISTER")

    search = st.text_input("Search")

    if not df_t.empty:

        df_f = df_t.copy()

        if search:
            df_f = df_f[
                df_f.apply(
                    lambda r: search.lower() in str(r).lower(),
                    axis=1
                )
            ]

        st.dataframe(df_f)
