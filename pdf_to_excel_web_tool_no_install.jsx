# AARS & ASSOCIATES – Bank Statement Analyzer (Client-ready)
# Tech: Streamlit (deploy on Streamlit Cloud)

import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

st.set_page_config(page_title="AARS & ASSOCIATES – Analyzer", layout="wide")

# =========================
# BRANDING HEADER
# =========================
st.markdown("""
<h2 style='color:#333;'>AARS & ASSOCIATES</h2>
<h4 style='color:#666;'>Chartered Accountants | CA Avi Agarwal</h4>
<p>📞 9327230005 | ✉️ aars.associates1@gmail.com</p>
<hr>
""", unsafe_allow_html=True)

# =========================
# LOGIN (simple)
# =========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("Client Login")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == "client" and pwd == "1234":
            st.session_state.logged_in = True
        else:
            st.error("Invalid credentials")
    st.stop()

# =========================
# FILE UPLOAD
# =========================
files = st.file_uploader("Upload Bank Statements (PDF/Excel)", type=["pdf", "xlsx"], accept_multiple_files=True)

# =========================
# HELPER FUNCTIONS
# =========================

def clean_text(x):
    if pd.isna(x): return ""
    return str(x).replace("\n", " ").strip()


def extract_pdf(file):
    rows = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for r in table:
                    rows.append(r)
    return pd.DataFrame(rows)


def detect_columns(df):
    df = df.applymap(clean_text)
    df.columns = range(len(df.columns))

    records = []
    for _, row in df.iterrows():
        row_str = " ".join(row.astype(str))

        date_match = re.search(r"\d{2}/\d{2}/\d{4}", row_str)
        amount_match = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", row_str)

        if date_match and len(amount_match) >= 1:
            date = datetime.strptime(date_match.group(), "%d/%m/%Y")
            amount = float(amount_match[0].replace(",", ""))

            debit = amount if "CR" not in row_str else 0
            credit = amount if "CR" in row_str else 0

            records.append({
                "Date": date,
                "Description": row_str,
                "Debit": debit,
                "Credit": credit
            })

    return pd.DataFrame(records)


def categorize(desc):
    d = desc.lower()
    if "neft" in d or "imps" in d or "upi" in d:
        return "Transfer"
    if "cash" in d:
        return "Cash"
    if "gst" in d or "charges" in d or "commission" in d:
        return "Bank Charges"
    if "insufficient" in d:
        return "Bounce"
    return "Business"

# =========================
# PROCESS FILES
# =========================

if files:
    final_df = pd.DataFrame()

    for f in files:
        if f.name.endswith(".pdf"):
            raw = extract_pdf(f)
            df = detect_columns(raw)
        else:
            df = pd.read_excel(f)

        final_df = pd.concat([final_df, df], ignore_index=True)

    if final_df.empty:
        st.error("No data extracted")
    else:
        final_df["Category"] = final_df["Description"].apply(categorize)
        final_df.sort_values("Date", inplace=True)

        # =========================
        # CALCULATIONS
        # =========================
        total_debit = final_df["Debit"].sum()
        total_credit = final_df["Credit"].sum()

        count_debit = (final_df["Debit"] > 0).sum()
        count_credit = (final_df["Credit"] > 0).sum()

        final_df["Balance"] = final_df["Credit"].cumsum() - final_df["Debit"].cumsum()

        avg_daily = final_df["Balance"].mean()
        monthly_avg = final_df.groupby(final_df["Date"].dt.to_period("M"))["Balance"].mean()

        bounces = final_df[final_df["Category"] == "Bounce"]

        # =========================
        # DASHBOARD
        # =========================
        st.subheader("Summary")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Credit", f"₹ {total_credit:,.2f}")
        col2.metric("Total Debit", f"₹ {total_debit:,.2f}")
        col3.metric("Avg Daily Balance", f"₹ {avg_daily:,.2f}")

        st.write("### Monthly Avg Balance")
        st.dataframe(monthly_avg)

        st.write("### Transactions")
        st.dataframe(final_df)

        st.write("### Bounce / Alerts")
        st.dataframe(bounces)

        # =========================
        # DOWNLOAD
        # =========================
        output = "report.xlsx"
        with pd.ExcelWriter(output) as writer:
            final_df.to_excel(writer, sheet_name="Transactions", index=False)
            monthly_avg.to_excel(writer, sheet_name="Monthly Avg")
            bounces.to_excel(writer, sheet_name="Alerts")

        with open(output, "rb") as f:
            st.download_button("Download Excel Report", f, file_name="AARS_Report.xlsx")

# =========================
# END
# =========================
