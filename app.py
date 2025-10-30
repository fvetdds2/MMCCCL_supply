import streamlit as st
import base64
import pandas as pd
import plotly.express as px
from io import BytesIO
from pathlib import Path

st.set_page_config(page_title="In Situ Tissue-Omics Core Dashboard", layout="wide")

# --- Custom CSS with color enforcement ---
st.markdown("""
    <style>
    .header-container {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 2.25rem;
        margin-bottom: 1.5rem;
    }
    .core-title-block {
        display: flex;
        flex-direction: column;
        justify-content: center;
        line-height: 1.2;
    }
    .core-title {
        color: #7A004B !important;   /* Enforced purple */
        font-size: 2.6rem;
        font-weight: 800;
        font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
        letter-spacing: 0.5px;
        margin: 0;
        line-height: 1.2;
    }
    .dashboard-subtitle {
        color: #004B8D !important;   /* Enforced blue */
        font-size: 1.1rem;
        font-weight: 600;
        font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
        margin-top: .35rem;
        opacity: 0.95;
    }
    </style>
""", unsafe_allow_html=True)

# --- Load and Display Logo ---
logo_path = "mmcccl_logo.png"
try:
    with open(logo_path, "rb") as f:
        logo_base64 = base64.b64encode(f.read()).decode()
    logo_html = f"<img src='data:image/png;base64,{logo_base64}' width='280'>"
except FileNotFoundError:
    logo_html = "<div style='color:red;'>Logo not found</div>"

# --- Header Layout ---
st.markdown(f"""
    <div class='header-container'>
        {logo_html}
        <div class='core-title-block'>
            <h1 class='core-title'>In Situ Tissue-Omics Core</h1>
            <h2 class='dashboard-subtitle'>Translational Pathology Shared Resource Core Activity Dashboard</h2>
        </div>
    </div>
""", unsafe_allow_html=True)

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
    3. *Dr. Menaka Thounaojam* - Frozen sections from unfixed snap frozen mouse eye tissue.
       **Status:** In process of optimizing sectioning protocol
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

# --- reprocell breast File ---
    reprocell_path = Path("reprocell_breast_stock.xlsx")
    if reprocell_path.exists():
        st.markdown("#### 🧬 Reprocell Breast Cancer Tissue Stock")
        reprocell_df = pd.read_excel(reprocell_path)
        st.dataframe(reprocell_df, use_container_width=True)
        reprocell_buffer = BytesIO()
        with pd.ExcelWriter(reprocell_buffer, engine="openpyxl") as writer:
            reprocell_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Download Reprocell Stock File",
            data=reprocell_buffer.getvalue(),
            file_name="Reprocell_stock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Reprocell_stock.xlsx not found in the directory.")

# --- reprocell breast File ---
    reprocell_path = Path("reprocell_biobank_2.xlsx")
    if reprocell2_path.exists():
        st.markdown("#### 🧬 Additional Reprocell Breast Cancer Tissue Stock")
        reprocell2_df = pd.read_excel(reprocell2_path)
        st.dataframe(reprocell2_df, use_container_width=True)
        reprocell2_buffer = BytesIO()
        with pd.ExcelWriter(reprocell2_buffer, engine="openpyxl") as writer:
            reprocell2_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Download Reprocell Stock2 File",
            data=reprocell2_buffer.getvalue(),
            file_name="Reprocell2_stock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Reprocell_biobank_2.xlsx not found in the directory.")
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

    