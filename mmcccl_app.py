import streamlit as st
import pandas as pd
from datetime import datetime

# Load Excel
@st.cache_data
def load_data():
    df = pd.read_excel("MMCCCL_supply_july.xlsx")
    df['expiration_date'] = pd.to_datetime(df['expiration_date'], errors='coerce')
    return df

df = load_data()

# App Title
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")
st.title("🧪 MMCCCL Lab Supply Tracker")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Inventory Meter", "📦 Item Location", "⚠️ Reorder List", "📝 Notes/Future"])

# Tab 1: Inventory Meter
with tab1:
    st.header("📊 Inventory Level & Update Tracker")
    cat_selected = st.selectbox("Select Catalog Number", df['cat_no'].unique())

    item_data = df[df['cat_no'] == cat_selected].copy()
    item_name = item_data['item'].values[0]
    total_qty = item_data['quantity'].sum()

    st.metric(label=f"{item_name} (Cat#: {cat_selected})", value=total_qty)

    add_qty = st.number_input("Add quantity to update", min_value=0, step=1)

    if st.button("Update Quantity"):
        idx = df[df['cat_no'] == cat_selected].index[0]
        df.at[idx, 'quantity'] += add_qty
        st.success(f"Updated quantity of {item_name} to {df.at[idx, 'quantity']}")

# Tab 2: Item Location
with tab2:
    st.header("📦 Item Shelf & Location")
    location_df = df[['item', 'cat_no', 'location', 'shelf']].sort_values(by='item')
    st.dataframe(location_df, use_container_width=True)

# Tab 3: Reorder List
with tab3:
    st.header("⚠️ Items Needing Reorder (Expired)")
    today = datetime.now()
    expired_items = df[df['expiration_date'] < today].copy()

    if not expired_items.empty:
        st.warning("Some items are past expiration and need to be reordered.")
        st.dataframe(expired_items[['item', 'cat_no', 'quantity', 'expiration_date']], use_container_width=True)
    else:
        st.success("No expired items at the moment.")

# Tab 4: Notes or Future Feature
with tab4:
    st.header("📝 Notes or Future Additions")
    st.info("This tab can be used for adding reorder buttons, PDF export, or lab manager notes.")
