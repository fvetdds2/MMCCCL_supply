import streamlit as st
import pandas as pd
from datetime import datetime, date
import io

# --- Page setup ---
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")

# --- Styles ---
st.markdown("""
    <style>
    .big-font { font-size: 3em !important; font-weight: bold; color: #0072b2; padding-top: 2rem; }
    .main-header { color: #0072b2; font-size: 2.5em; font-weight: 600; margin-bottom: 0; }
    .secondary-header { color: #4b8c6a; font-size: 1.5em; font-weight: 500; margin-top: 0; }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 1.25rem; }
    </style>
    """, unsafe_allow_html=True)

st.image("mmcccl_logo.png", use_container_width=True)

# --- Helpers ---
def to_dt(x):
    try:
        return pd.to_datetime(x) if x else pd.NaT
    except:
        return pd.NaT

def excel_safe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64tz_dtype(out[col]):
            out[col] = out[col].dt.tz_convert(None)
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col], errors="coerce")
        if out[col].dtype == "object":
            out[col] = out[col].map(lambda x: x if isinstance(x, (str, int, float, bool, type(None), pd.Timestamp)) else str(x))
    return out

# --- Load Data ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
        df = df.dropna(axis=1, how='all')  # Drop all empty columns
    except FileNotFoundError:
        st.error("Excel file not found.")
        return pd.DataFrame(columns=[
            'item','cat_no.','quantity','location','shelf','expiration','lot #',
            'ordered','order_date','order_unit','minimum_stock_level'])

    df['expiration'] = pd.to_datetime(df.get('expiration'), errors='coerce')
    df['ordered'] = df.get('ordered', False)
    df['order_date'] = pd.to_datetime(df.get('order_date'), errors='coerce')
    df['quantity'] = pd.to_numeric(df.get('quantity'), errors='coerce').fillna(0).astype(int)

    for col in ['location','shelf','order_unit','cat_no.','item','lot #']:
        df[col] = df.get(col, "").astype(str)

    df['minimum_stock_level'] = pd.to_numeric(df.get('minimum_stock_level'), errors='coerce').fillna(0).astype(int)

    return df

# --- Init session state ---
if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'log' not in st.session_state:
    st.session_state.log = pd.DataFrame(columns=['timestamp', 'cat_no.', 'action', 'quantity', 'initials', 'lot #', 'expiration'])

if 'user_initials' not in st.session_state:
    st.session_state.user_initials = ""

st.session_state.user_initials = st.text_input("Enter your initials:", value=st.session_state.user_initials).upper()

if not st.session_state.user_initials:
    st.warning("Please enter your initials to proceed.")
    st.stop()

# --- Tabs ---
tab1, tab4 = st.tabs(["📊 Inventory Tracker", "📁 Export Data"])

# --- Tab 1: Inventory Interaction ---
with tab1:
    st.subheader("📦 Inventory Level")
    df = st.session_state.df
    df['cat_no.'] = df['cat_no.'].astype(str)
    df['item'] = df['item'].astype(str)

    search_term = st.text_input("Search catalog number or item name:").lower().strip()
    if search_term:
        mask = df['cat_no.'].str.lower().str.contains(search_term) | df['item'].str.lower().str.contains(search_term)
        filtered = df[mask]
    else:
        filtered = df

    if filtered.empty:
        st.warning("No matching items found.")
    else:
        st.dataframe(filtered)

# --- Tab 4: Export ---
with tab4:
    st.subheader("📁 Download Inventory")

    df_to_save = excel_safe(st.session_state.df.dropna(axis=1, how='all'))
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_to_save.to_excel(writer, sheet_name="Inventory", index=False)

    st.download_button(
        label="📥 Download Current Inventory as Excel",
        data=buffer.getvalue(),
        file_name="MMCCCL_Inventory_Export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
