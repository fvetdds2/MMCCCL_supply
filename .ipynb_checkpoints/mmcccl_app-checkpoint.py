import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- Function: Safe Excel String Conversion ---
def excel_safe(df):
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d')
    return df

# Page setup
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")

# ---- Load Excel Data ----
@st.cache_data

def load_data():
    try:
        df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    except FileNotFoundError:
        st.error("Error: File 'MMCCCL_supply_july.xlsx' not found.")
        return pd.DataFrame()

    df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')
    if 'ordered' not in df.columns: df['ordered'] = False
    if 'order_date' not in df.columns: df['order_date'] = pd.NaT
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    if 'location' not in df.columns: df['location'] = ""
    if 'shelf' not in df.columns: df['shelf'] = ""
    if 'order_unit' not in df.columns: df['order_unit'] = ""
    if 'minimum_stock_level' not in df.columns: df['minimum_stock_level'] = 0
    return df

# ---- Session State Init ----
if 'df' not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

# ---- Tab: Export Inventory ----
st.subheader("📁 Export Inventory")

if not df.empty:
    # Clean: drop empty cols/rows
    df_to_save = df.dropna(axis=1, how='all')
    df_to_save = df_to_save.dropna(axis=0, how='all')

    if df_to_save.empty:
        st.error("No data available to export. Please ensure the inventory is not empty.")
    else:
        df_to_save = excel_safe(df_to_save)

        # Use in-memory buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_to_save.to_excel(writer, sheet_name="Inventory", index=False)

        st.download_button(
            label="📥 Download Inventory Excel File",
            data=output.getvalue(),
            file_name=f"mmcccl_inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.warning("No data to export.")
