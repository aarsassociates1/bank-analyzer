import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

st.set_page_config(page_title="AARS Analyzer", layout="wide")

st.title("AARS & ASSOCIATES - Smart Bank Analyzer")

uploaded_files = st.file_uploader("Upload Bank Statements", type=["pdf", "xlsx"], accept_multiple_files=True)

# ---------------- PDF Extraction ----------------
def extract_pdf(file):
    rows = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.split("\n"):
                    rows.append([line])
    return pd.DataFrame(rows, columns=["raw"])

# ---------------- Data Processing ----------------
def process_df(df):
    records = []

    for _, row in df.iterrows():
        row_str = " ".join(row).strip()

        # Date
        date_match = re.search(r"\d{2}/\d{2}/\d{4}", row_str)

        # Amounts (capture all numbers)
        amounts = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", row_str)

        if date_match and amounts:
            date = datetime.strptime(date_match.group(), "%d/%m/%Y")

            # Take last amount as transaction (better accuracy)
            amount = float(amounts[-1].replace(",", ""))

            # Detect CR/DR
            if "cr" in row_str.lower():
                credit = amount
                debit = 0
            else:
                debit = amount
                credit = 0

            records.append({
                "Date": date,
                "Description": row_str,
                "Debit": debit,
                "Credit": credit
            })

    return pd.DataFrame(records)

# ---------------- Party Detection ----------------
def extract_party(desc):
    desc = desc.upper()

    # UPI
    upi = re.search(r"UPI/[^\s]+", desc)
    if upi:
        return upi.group()

    # NEFT/IMPS
    bank = re.search(r"(NEFT|IMPS|RTGS)[^\s]+", desc)
    if bank:
        return bank.group()

    # Default first words
    return " ".join(desc.split()[:3])

# ---------------- Categorization ----------------
def categorize(desc):
    desc = desc.lower()

    if any(x in desc for x in ["upi", "neft", "imps", "rtgs"]):
        return "Transfer"
    elif any(x in desc for x in ["salary", "income"]):
        return "Income"
    elif any(x in desc for x in ["gst", "tax"]):
        return "Tax"
    elif any(x in desc for x in ["charge", "fee", "penalty"]):
        return "Bank Charges"
    elif "cash" in desc:
        return "Cash"
    elif "insufficient" in desc:
        return "Bounce"
    else:
        return "Business Expense"

# ---------------- MAIN ----------------
if uploaded_files:
    final = pd.DataFrame()

    for file in uploaded_files:
        if file.name.endswith(".pdf"):
            df = extract_pdf(file)
            df = process_df(df)
        else:
            df = pd.read_excel(file)

        final = pd.concat([final, df], ignore_index=True)

    if not final.empty:
        final["Party"] = final["Description"].apply(extract_party)
        final["Category"] = final["Description"].apply(categorize)

        final = final.sort_values("Date")

        # Running Balance
        final["Balance"] = final["Credit"].cumsum() - final["Debit"].cumsum()

        # ---------------- DASHBOARD ----------------
        st.subheader("📊 Summary")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Credit", f"₹ {final['Credit'].sum():,.2f}")
        col2.metric("Total Debit", f"₹ {final['Debit'].sum():,.2f}")
        col3.metric("Net Balance", f"₹ {(final['Credit'].sum()-final['Debit'].sum()):,.2f}")

        st.metric("Avg Balance", f"₹ {final['Balance'].mean():,.2f}")

        # ---------------- CATEGORY VIEW ----------------
        st.subheader("📂 Category Breakdown")
        cat_summary = final.groupby("Category")[["Debit", "Credit"]].sum()
        st.dataframe(cat_summary)

        # ---------------- PARTY VIEW ----------------
        st.subheader("🏢 Party Analysis")
        party_summary = final.groupby("Party")[["Debit", "Credit"]].sum().sort_values("Debit", ascending=False)
        st.dataframe(party_summary.head(20))

        # ---------------- TRANSACTIONS ----------------
        st.subheader("📋 Transactions")
        st.dataframe(final)

        # ---------------- BOUNCES ----------------
        st.subheader("⚠️ Bounced Transactions")
        st.dataframe(final[final["Category"]=="Bounce"])

        # ---------------- DOWNLOAD ----------------
        final.to_excel("AARS_Report.xlsx", index=False)

        with open("AARS_Report.xlsx", "rb") as f:
            st.download_button("⬇ Download Report", f, "AARS_Report.xlsx")
