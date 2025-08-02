import streamlit as st
import pandas as pd
from datetime import datetime

# Page Config
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")

# Load Excel
@st.cache_data
def load_data():
    df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')
    df['ordered'] = False
    df['order_date'] = pd.NaT
    return df

# Initialize or load data into session_state
if 'df' not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

# App Title
st.title("🧪 MMCCCL Lab Supply Tracker")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Current Inventory", "📦 Item Location", "⚠️ Reorder List", "📝 Notes/Future"])

# Tab 1: Inventory Meter
with tab1:
    st.header("📊 Inventory Level & Update Tracker")
    cat_selected = st.selectbox("Select Catalog Number", df['cat_no.'].unique())

    item_data = df[df['cat_no.'] == cat_selected].copy()
    item_name = item_data['item'].values[0]
    total_qty = item_data['quantity'].sum()

    st.metric(label=f"{item_name} (Cat#: {cat_selected})", value=total_qty)

    add_qty = st.number_input("Add quantity to update", min_value=0, step=1)

    if st.button("Update Quantity"):
        idxs = df[df['cat_no.'] == cat_selected].index
        if not idxs.empty:
            idx = idxs[0]
            df.at[idx, 'quantity'] += add_qty
            st.success(f"Updated quantity of {item_name} to {df.at[idx, 'quantity']}")
        else:
            st.error("Item not found!")

# Tab 2: Item Location
with tab2:
    st.header("📦 Item Shelf & Location")
    location_df = df[['item', 'cat_no.', 'location', 'shelf']].sort_values(by='item')
    st.dataframe(location_df, use_container_width=True)

# Tab 3: Reorder List
with tab3:
    st.header("⚠️ Items Needing Reorder (Expired)")
    today = datetime.now()
    expired_items = df[df['expiration'] < today].copy()

    if not expired_items.empty:
        st.warning("Some items are past expiration and may need to be reordered.")

        for idx, row in expired_items.iterrows():
            col1, col2, col3 = st.columns([5, 2, 3])
            with col1:
                st.markdown(f"**{row['item']}** (Cat#: {row['cat_no.']}) - Exp: {row['expiration'].date()}")
            with col2:
                ordered = st.checkbox("Ordered", key=f"ordered_{idx}", value=row['ordered'])
            with col3:
                order_date = st.date_input("Order Date", value=row['order_date'] if pd.notna(row['order_date']) else today, key=f"order_date_{idx}")

            # Save changes to the session state DataFrame
            df.at[idx, 'ordered'] = ordered
            df.at[idx, 'order_date'] = order_date if ordered else pd.NaT

        # Display updated reorder table
        st.subheader("📋 Current Reorder Status")
        st.dataframe(df[df['expiration'] < today][['item', 'cat_no.', 'quantity', 'expiration', 'ordered', 'order_date']], use_container_width=True)
    else:
        st.success("No expired items at the moment.")

# Tab 4: Notes or Future Feature
with tab4:
    st.header("📝 Notes or Future Additions")
    st.info("This tab can be used for adding reorder buttons, PDF/CSV export, or lab manager notes.")
