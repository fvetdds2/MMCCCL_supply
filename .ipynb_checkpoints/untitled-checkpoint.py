import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="In Situ Tissue-Omics Core Dashboard", layout="wide")

st.title("In Situ Tissue-Omics Core Dashboard")

# ---- File Upload ----
uploaded_file = st.file_uploader("", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    # Ensure columns exist
    expected_cols = ["Date", "Requester Name", "Service Type", "Sample Type", "Quantity"]
    if not all(col in df.columns for col in expected_cols):
        st.error(f"Excel file must contain these columns: {expected_cols}")
    else:
        # ---- Overview Metrics ----
        total_services = len(df)
        total_slides = df["Quantity"].sum()
        unique_requesters = df["Requester Name"].nunique()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Requests", total_services)
        col2.metric("Total Slides Processed", total_slides)
        col3.metric("Unique Requesters", unique_requesters)

        st.divider()

        # ---- Aggregation ----
        st.subheader("📊 Summary by Service Type")
        service_summary = df.groupby("Service Type")["Quantity"].sum().reset_index()
        st.dataframe(service_summary, use_container_width=True)

        fig_service = px.bar(service_summary, x="Service Type", y="Quantity", text="Quantity",
                             title="Slides by Service Type", color="Service Type")
        st.plotly_chart(fig_service, use_container_width=True)

        st.subheader("👩‍🔬 Summary by Requester")
        requester_summary = df.groupby("Requester Name")["Quantity"].sum().reset_index()
        st.dataframe(requester_summary, use_container_width=True)

        fig_requester = px.bar(requester_summary, x="Requester Name", y="Quantity", text="Quantity",
                               title="Slides by Requester", color="Requester Name")
        st.plotly_chart(fig_requester, use_container_width=True)

        # ---- Optional Time Trend ----
        st.subheader("📅 Activity Over Time")
        df["Date"] = pd.to_datetime(df["Date"])
        time_summary = df.groupby("Date")["Quantity"].sum().reset_index()

        fig_time = px.line(time_summary, x="Date", y="Quantity", markers=True,
                           title="Service Volume Over Time")
        st.plotly_chart(fig_time, use_container_width=True)
else:
    st.info("👆 Please upload an Excel file to begin.")
