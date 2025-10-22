import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# -------------------------------------------------
# PAGE SETUP
# -------------------------------------------------
st.set_page_config(page_title="In Situ Tissue-Omics Core Activity Dashboard", layout="wide")

# --- Custom Header Layout ---
st.markdown("""
    <style>
    .main-header { color:#0072b2; font-size:2rem; font-weight:700; margin:.25rem 0 .5rem 0; }
    .subtle { color:#666; font-size:.95rem; margin-bottom:.75rem; }
    .metric { font-size:1.5rem; font-weight:600; }
    .pill { display:inline-block; padding:.1rem .5rem; border-radius:999px; background:#eef1f4; margin-right:.25rem; }
    </style>
""", unsafe_allow_html=True)

# --- Logo and Title in one row ---
col_logo, col_title = st.columns([1, 3])
with col_logo:
    try:
        st.image("mmcccl_logo.png", width=350)
    except:
        st.write("")
with col_title:
    st.markdown("<h1 class='main-header'>In Situ Tissue-Omics Core Activity Dashboard</h1>", unsafe_allow_html=True)

# -------------------------------------------------
# DATA LOADING
# -------------------------------------------------
DEFAULT_FILE = Path("lab_record.xlsx")

if DEFAULT_FILE.exists():
    df = pd.read_excel(DEFAULT_FILE)
else:
    st.error("❌ No data file found. Please place 'lab_record.xlsx' in the same directory.")
    st.stop()

# --- Verify columns ---
required_cols = ["Date", "Requester Name", "Service Type", "Sample Type", "Quantity"]
if not all(col in df.columns for col in required_cols):
    st.error(f"Excel file must contain these columns: {required_cols}")
    st.stop()

# --- Clean & prepare data ---
df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)

# -------------------------------------------------
# METRICS
# -------------------------------------------------
# Total entries (all services)
total_services = len(df)

# Total slides processed (exclude FFPE Processing & Embedding — not slide generation)
slide_df_for_metrics = df[df["Service Type"] != "FFPE Processing & Embedding"]
total_slides_processed = slide_df_for_metrics["Quantity"].sum()

# Unique requesters (all services)
unique_requesters = df["Requester Name"].nunique()

col1, col2, col3 = st.columns(3)
col1.metric("Total Service Entries (all)", total_services)
col2.metric("Total Slides Processed (excl. FFPE Processing & Embedding)", total_slides_processed)
col3.metric("Unique Requesters (all)", unique_requesters)

st.divider()

# -------------------------------------------------
# DATA AGGREGATION
# -------------------------------------------------
grouped = (
    df.groupby(["Date", "Requester Name", "Service Type", "Sample Type"], as_index=False)
      .agg({"Quantity": "sum"})
)

# -------------------------------------------------
# SERVICE SUMMARY
# -------------------------------------------------
st.subheader("📅 Provided Service Summary (All Services)")
daily_summary = (
    grouped.groupby(["Date", "Requester Name"], as_index=False)
           .agg({"Quantity": "sum"})
           .sort_values("Date", ascending=False)
)
st.dataframe(daily_summary, use_container_width=True)

st.divider()

# -------------------------------------------------
# SLIDE-GENERATION ANALYSIS (EXCLUDES FFPE Processing & Embedding)
# -------------------------------------------------
slide_df = grouped[grouped["Service Type"] != "FFPE Processing & Embedding"].copy()

# --- Service Breakdown (slide-generation only) ---
st.subheader("📊 Quantity by Service Type (Slide Generation)")
service_summary = slide_df.groupby("Service Type", as_index=False)["Quantity"].sum()
fig_service = px.bar(
    service_summary,
    x="Service Type",
    y="Quantity",
    text="Quantity",
    title="Quantity by Service Type (Slide Generation)",
    color="Service Type"
)
st.plotly_chart(fig_service, use_container_width=True)

# --- Requester Breakdown (slide-generation only) ---
st.subheader("👩‍🔬 Quantity by Requester (Slide Generation)")
requester_summary = slide_df.groupby("Requester Name", as_index=False)["Quantity"].sum()
fig_requester = px.bar(
    requester_summary,
    x="Requester Name",
    y="Quantity",
    text="Quantity",
    title="Quantity by Requester (Slide Generation)",
    color="Requester Name"
)
st.plotly_chart(fig_requester, use_container_width=True)

# --- Slide Generation Trend (slide-generation only) ---
st.subheader("📈 Histology Slide Generation Over Time")
time_summary = slide_df.groupby("Date", as_index=False)["Quantity"].sum()
fig_time = px.line(
    time_summary,
    x="Date",
    y="Quantity",
    markers=True,
    title="No of Histology Slides Over Time (excl. FFPE Processing & Embedding)"
)
st.plotly_chart(fig_time, use_container_width=True)

st.divider()

# -------------------------------------------------
# FFPE PROCESSING & EMBEDDING TREND (SEPARATE)
# -------------------------------------------------
st.subheader("🧱 FFPE Processing & Embedding Trend Over Time")
ffpe_df = grouped[grouped["Service Type"] == "FFPE Processing & Embedding"]

if not ffpe_df.empty:
    ffpe_trend = ffpe_df.groupby("Date", as_index=False)["Quantity"].sum()
    fig_ffpe = px.line(
        ffpe_trend,
        x="Date",
        y="Quantity",
        markers=True,
        title="FFPE Processing & Embedding Volume Over Time",
        color_discrete_sequence=["#FF7F50"]
    )
    st.plotly_chart(fig_ffpe, use_container_width=True)

    st.subheader("🔍 FFPE Processing & Embedding Summary by Requester")
    ffpe_summary = (
        ffpe_df.groupby("Requester Name", as_index=False)["Quantity"]
        .sum()
        .sort_values("Quantity", ascending=False)
    )
    st.dataframe(ffpe_summary, use_container_width=True)
else:
    st.info("No 'FFPE Processing & Embedding' records found in this dataset.")

st.divider()

# -------------------------------------------------
# FULL SERVICE REPORT
# -------------------------------------------------
st.subheader("📋 Full Service Report (All Entries)")
st.dataframe(grouped.sort_values("Date", ascending=False), use_container_width=True)
