import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from pathlib import Path

# -------------------------------------------------
# PAGE SETUP
# -------------------------------------------------
st.set_page_config(page_title="Translational Pathology Shared Resource Core Activity Dashboard", layout="wide")

# --- Custom Header Layout ---
st.markdown("""
    <style>
    .main-header { color:#0072b2; font-size:2rem; font-weight:700; margin:.25rem 0 .5rem 0; }
    .subtle { color:#666; font-size:.95rem; margin-bottom:.75rem; }
    .metric { font-size:1.5rem; font-weight:600; }
    .pill { display:inline-block; padding:.1rem .5rem; border-radius:999px; background:#eef1f4; margin-right:.25rem; }
    </style>
""", unsafe_allow_html=True)

# --- Logo and Title ---
col_logo, col_title = st.columns([1, 3])
with col_logo:
    try:
        st.image("mmcccl_logo.png", width=350)
    except:
        st.write("")
with col_title:
    st.markdown("<h1 class='main-header'>Translational Pathology Shared Resource Core Activity Dashboard</h1>", unsafe_allow_html=True)

# -------------------------------------------------
# TABS
# -------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📦 Delivered Services",
    "⏳ Pending Services",
    "🧫 FFPE Cancer Tissue Repository",
    "💰 Recovery Cost"
])

# -------------------------------------------------
# TAB 1: DELIVERED SERVICES
# -------------------------------------------------
with tab1:
    DEFAULT_FILE = Path("lab_record.xlsx")

    if DEFAULT_FILE.exists():
        df = pd.read_excel(DEFAULT_FILE)
    else:
        st.error("❌ No data file found. Please place 'lab_record.xlsx' in the same directory.")
        st.stop()

    required_cols = ["Date", "Requester Name", "Service Type", "Sample Type", "Quantity"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"Excel file must contain these columns: {required_cols}")
        st.stop()

    df["Date"] = pd.to_datetime(df["Date"])
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)

    total_services = len(df)
    slide_df_for_metrics = df[df["Service Type"] != "FFPE Processing & Embedding"]
    total_slides_processed = slide_df_for_metrics["Quantity"].sum()
    unique_requesters = df["Requester Name"].nunique()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Service Entries (all)", total_services)
    col2.metric("Total Slides Processed (excl. FFPE Processing & Embedding)", total_slides_processed)
    col3.metric("Unique Requesters (all)", unique_requesters)

    st.divider()

    grouped = (
        df.groupby(["Date", "Requester Name", "Service Type", "Sample Type"], as_index=False)
          .agg({"Quantity": "sum"})
    )

    st.subheader("📅 Provided Service Summary (All Services)")
    daily_summary = (
        grouped.groupby(["Date", "Requester Name"], as_index=False)
               .agg({"Quantity": "sum"})
               .sort_values("Date", ascending=False)
    )
    st.dataframe(daily_summary, use_container_width=True)

    st.divider()

    slide_df = grouped[grouped["Service Type"] != "FFPE Processing & Embedding"].copy()

    st.subheader("📊 Quantity by Service Type (Slide Generation)")
    service_summary = slide_df.groupby("Service Type", as_index=False)["Quantity"].sum()
    fig_service = px.bar(service_summary, x="Service Type", y="Quantity", text="Quantity",
                         title="Quantity by Service Type (Slide Generation)", color="Service Type")
    st.plotly_chart(fig_service, use_container_width=True)

    st.subheader("👩‍🔬 Quantity by Requester (Slide Generation)")
    requester_summary = slide_df.groupby("Requester Name", as_index=False)["Quantity"].sum()
    fig_requester = px.bar(requester_summary, x="Requester Name", y="Quantity", text="Quantity",
                           title="Quantity by Requester (Slide Generation)", color="Requester Name")
    st.plotly_chart(fig_requester, use_container_width=True)

    st.subheader("📈 Histology Slide Generation Over Time")
    time_summary = slide_df.groupby("Date", as_index=False)["Quantity"].sum()
    fig_time = px.line(time_summary, x="Date", y="Quantity", markers=True,
                       title="No of Histology Slides Over Time (excl. FFPE Processing & Embedding)")
    st.plotly_chart(fig_time, use_container_width=True)

    st.divider()

    st.subheader("🧱 FFPE Processing & Embedding Trend Over Time")
    ffpe_df = grouped[grouped["Service Type"] == "FFPE Processing & Embedding"]

    if not ffpe_df.empty:
        ffpe_trend = ffpe_df.groupby("Date", as_index=False)["Quantity"].sum()
        fig_ffpe = px.line(ffpe_trend, x="Date", y="Quantity", markers=True,
                           title="FFPE Processing & Embedding Volume Over Time",
                           color_discrete_sequence=["#FF7F50"])
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
    st.subheader("📋 Full Service Report (All Entries)")
    st.dataframe(grouped.sort_values("Date", ascending=False), use_container_width=True)

# -------------------------------------------------
# TAB 2: PENDING SERVICES
# -------------------------------------------------
with tab2:
    st.subheader("⏳ Pending Service Requests")

    st.markdown("""
    **Pending Requests:**
    1. *Dr. Amadou Gaye* — Matched FFPE and frozen tissue samples from 8 African American and 8 non–African American patients.  
       **Status:** In progress (biobank contact and coordination)
    2. *Dr. Chandravanu Dash* — Frozen mouse brain slide preparation for brain region study.  
       **Status:** In review process
    """)

    # --- Load Excel file for Biobank list ---
    st.markdown("### 📘 List of Biobanks")
    PENDING_FILE = "Cancer_biobanks_USA.xlsx"
    try:
        pending_df = pd.read_excel(PENDING_FILE)
        edited_df = st.data_editor(
            pending_df,
            use_container_width=True,
            num_rows="dynamic",
            key="pending_editor"
        )

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            edited_df.to_excel(writer, index=False, sheet_name="Pending_Services")

        st.download_button(
            label="💾 Download Updated Biobank List",
            data=buffer.getvalue(),
            file_name="Updated_Pending_Services.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Could not read {PENDING_FILE}: {e}")

    st.divider()
    st.subheader("🏷️ Available Tissue Stock Files")

    # --- BioIVT Stock File ---
    bioivt_path = Path("BioIVT_stock.xlsx")
    if bioivt_path.exists():
        st.markdown("#### 🧬 BioIVT Breast Cancer Tissue Stock")
        bioivt_df = pd.read_excel(bioivt_path)
        st.dataframe(bioivt_df, use_container_width=True)
        bioivt_buffer = BytesIO()
        with pd.ExcelWriter(bioivt_buffer, engine="openpyxl") as writer:
            bioivt_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Download BioIVT Stock File",
            data=bioivt_buffer.getvalue(),
            file_name="BioIVT_stock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("BioIVT_stock.xlsx not found in the directory.")

    # --- Cureline Stock File ---
    cureline_path = Path("Cureline_breast_cancer_stock.xlsx")
    if cureline_path.exists():
        st.markdown("#### 🧫 Cureline Breast Cancer Tissue Stock")
        cureline_df = pd.read_excel(cureline_path)
        st.dataframe(cureline_df, use_container_width=True)
        cureline_buffer = BytesIO()
        with pd.ExcelWriter(cureline_buffer, engine="openpyxl") as writer:
            cureline_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Download Cureline Stock File",
            data=cureline_buffer.getvalue(),
            file_name="Cureline_breast_cancer_stock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Cureline_breast_cancer_stock.xlsx not found in the directory.")

# -------------------------------------------------
# TAB 3: FFPE CANCER TISSUE REPOSITORY
# -------------------------------------------------
with tab3:
    st.subheader("🧫 FFPE Cancer Tissue Repository Overview")
    repo_file = Path("ffpe_repository.xlsx")

    if repo_file.exists():
        repo_df = pd.read_excel(repo_file)
        st.dataframe(repo_df, use_container_width=True)

        st.subheader("📈 Repository Summary by Cancer Type")
        if "Cancer Type" in repo_df.columns and "Quantity" in repo_df.columns:
            summary = repo_df.groupby("Cancer Type", as_index=False)["Quantity"].sum()
            fig_repo = px.bar(summary, x="Cancer Type", y="Quantity",
                              title="FFPE Samples by Cancer Type", color="Cancer Type")
            st.plotly_chart(fig_repo, use_container_width=True)
        else:
            st.warning("Columns 'Cancer Type' and 'Quantity' not found in the repository file.")
    else:
        st.info("No FFPE repository file found. Please upload 'ffpe_repository.xlsx'.")

# -------------------------------------------------
# TAB 4: RECOVERY COST
# -------------------------------------------------
with tab4:
    st.subheader("💰 Recovery Cost Overview")
    cost_file = Path("recovery_cost.xlsx")

    if cost_file.exists():
        cost_df = pd.read_excel(cost_file)
        st.dataframe(cost_df, use_container_width=True)

        if "Requester Name" in cost_df.columns and "Cost" in cost_df.columns:
            st.subheader("📊 Cost Breakdown by Requester")
            summary_cost = cost_df.groupby("Requester Name", as_index=False)["Cost"].sum()
            fig_cost = px.bar(summary_cost, x="Requester Name", y="Cost", text="Cost",
                              title="Total Recovery Cost per Requester", color="Requester Name")
            st.plotly_chart(fig_cost, use_container_width=True)

            st.subheader("📈 Monthly Cost Trend")
            if "Date" in cost_df.columns:
                cost_df["Date"] = pd.to_datetime(cost_df["Date"])
                monthly_cost = cost_df.groupby(cost_df["Date"].dt.to_period("M")).sum(numeric_only=True)
                monthly_cost.index = monthly_cost.index.astype(str)
                fig_month = px.line(monthly_cost, x=monthly_cost.index, y="Cost",
                                    title="Monthly Recovery Cost Trend", markers=True)
                st.plotly_chart(fig_month, use_container_width=True)
        else:
            st.warning("The recovery cost file must include 'Requester Name' and 'Cost' columns.")
    else:
        st.info("No recovery cost file found. Please upload 'recovery_cost.xlsx'.")

    