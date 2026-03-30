import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

st.set_page_config(page_title="AARS Analyzer", layout="wide")

st.title("AARS & ASSOCIATES - Bank Statement Analyzer")

uploaded_files = st.file_uploader("Upload Bank Statements", type=["pdf", "xlsx"], accept_multiple_files=True)

def extract_pdf(file):
    rows = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for r in table:
                    rows.append(r)
    return pd.DataFrame(rows)

def process_df(df):
    df = df.astype(str)
    records = []

    for _, row in df.iterrows():
        row_str = " ".join(row)

        date_match = re.search(r"\d{2}/\d{2}/\d{4}", row_str)
        amt = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", row_str)

        if date_match and amt:
            date = datetime.strptime(date_match.group(), "%d/%m/%Y")
            amount = float(amt[0].replace(",", ""))

            debit = amount if "CR" not in row_str else 0
            credit = amount if "CR" in row_str else 0

            records.append({
                "Date": date,
                "Description": row_str,
                "Debit": debit,
                "Credit": credit
            })

    return pd.DataFrame(records)

def categorize(x):
    x = x.lower()
    if "upi" in x or "neft" in x or "imps" in x:
        return "Transfer"
    if "cash" in x:
        return "Cash"
    if "gst" in x or "charges" in x:
        return "Charges"
    if "insufficient" in x:
        return "Bounce"
    return "Business"

if uploaded_files:
    final = pd.DataFrame()

    for file in uploaded_files:
        if file.name.endswith(".pdf"):
            df = extract_pdf(file)
            df = process_df(df)
        else:
            df = pd.read_excel(file)

        final = pd.concat([final, df])

    final["Category"] = final["Description"].apply(categorize)
    final = final.sort_values("Date")

    final["Balance"] = final["Credit"].cumsum() - final["Debit"].cumsum()

    st.subheader("Summary")

    col1, col2 = st.columns(2)
    col1.metric("Total Credit", f"₹ {final['Credit'].sum():,.2f}")
    col2.metric("Total Debit", f"₹ {final['Debit'].sum():,.2f}")

    st.metric("Avg Daily Balance", f"₹ {final['Balance'].mean():,.2f}")

    st.subheader("Transactions")
    st.dataframe(final)

    st.subheader("Bounces")
    st.dataframe(final[final["Category"]=="Bounce"])

    final.to_excel("report.xlsx", index=False)

    with open("report.xlsx", "rb") as f:
        st.download_button("Download Report", f, "report.xlsx")
