import streamlit as st
import pandas as pd
from datetime import datetime
import io

# ---- Page Config ----
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")

# ---- Load Excel Data ----
@st.cache_data
def load_data():
    df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')
    df['ordered'] = df.get('ordered', False)
    df['order_date'] = pd.to_datetime(df.get('order_date', pd.NaT), errors='coerce')
    return df

# ---- Session State Init ----
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'log' not in st.session_state:
    st.session_state.log = pd.DataFrame(columns=['timestamp', 'cat_no.', 'action', 'quantity', 'initials'])

df = st.session_state.df
log_df = st.session_state.log

# ---- App Title ----
st.title("🧪 MMCCCL Lab Supply Tracker")

# ---- Tabs ----
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Inventory + Update Log",
    "📦 Item Locations",
    "⏰ Expiring Soon",
    "📁 Export Data"
])

# ---- Tab 1: Inventory & Update Tracker ----
with tab1:
    st.subheader("📊 Inventory Level & Tracker")

    search_term = st.text_input("Search catalog number:")
    filtered_cat_nos = sorted(
    [
        cat
        for cat in df['cat_no.'].unique()
        if pd.notna(cat) and (search_term.lower() in str(cat).lower())
    ]
)
    if not filtered_cat_nos:
    st.warning("No catalog numbers found.")
    else:
    selected_cat = st.selectbox("Select Catalog Number", filtered_cat_nos)
    
    item_data = df[df['cat_no.'] == selected_cat]
    item_name = item_data['item'].values[0]
    total_qty = item_data['quantity'].sum()
    st.metric(label=f"{item_name} (Cat#: {selected_cat})", value=total_qty)

    initials = st.text_input("Your initials:")
    add_qty = st.number_input("Add Quantity", min_value=0, step=1)
    remove_qty = st.number_input("Remove Quantity", min_value=0, step=1)

    if st.button("Submit Update"):
        idxs = df[df['cat_no.'] == selected_cat].index
        if not idxs.empty:
            idx = idxs[0]
            net_change = add_qty - remove_qty
            df.at[idx, 'quantity'] += net_change

            # Log each action separately
            timestamp = datetime.now()
            if add_qty > 0:
                new_log = pd.DataFrame([{
                    'timestamp': timestamp,
                    'cat_no.': selected_cat,
                    'action': 'Add',
                    'quantity': add_qty,
                    'initials': initials
                }])
                st.session_state.log = pd.concat([st.session_state.log, new_log], ignore_index=True)

            if remove_qty > 0:
                new_log = pd.DataFrame([{
                    'timestamp': timestamp,
                    'cat_no.': selected_cat,
                    'action': 'Remove',
                    'quantity': remove_qty,
                    'initials': initials
                }])
                st.session_state.log = pd.concat([st.session_state.log, new_log], ignore_index=True)

            st.success(f"Inventory updated. New quantity: {df.at[idx, 'quantity']}")
        else:
            st.error("Item not found!")

    # Show history for this item
    st.markdown("#### 🔁 Update History")
    history = log_df[log_df['cat_no.'] == selected_cat].sort_values(by='timestamp', ascending=False)
    st.dataframe(history, use_container_width=True)

# ---- Tab 2: Item Locations ----
with tab2:
    st.subheader("📦 Item Locations")
    st.dataframe(df[['item', 'cat_no.', 'location', 'shelf']].sort_values('item'), use_container_width=True)

# ---- Tab 3: Expiring Items ----
with tab3:
    st.subheader("⚠️ Items Needing Reorder (Expired)")
    today = datetime.now()
    expired = df[df['expiration'] < today]

    if expired.empty:
        st.success("🎉 No expired items!")
    else:
        st.warning("Some items have passed expiration:")
        for idx, row in expired.iterrows():
            col1, col2, col3 = st.columns([5, 2, 3])
            with col1:
                st.markdown(f"**{row['item']}** (Cat#: {row['cat_no.']}) - Exp: {row['expiration'].date()}")
            with col2:
                ordered = st.checkbox("Ordered", key=f"ordered_{idx}", value=row['ordered'])
            with col3:
                order_date = st.date_input("Order Date", value=row['order_date'] if pd.notna(row['order_date']) else today, key=f"order_date_{idx}")
            df.at[idx, 'ordered'] = ordered
            df.at[idx, 'order_date'] = order_date if ordered else pd.NaT

        st.subheader("📋 Current Reorder Table")
        st.dataframe(df[df['expiration'] < today][['item', 'cat_no.', 'quantity', 'expiration', 'ordered', 'order_date']], use_container_width=True)

# ---- Tab 4: Export Data ----
with tab4:
    st.subheader("📁 Export Inventory and Update Log")

    # Combine data and log in one Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Inventory', index=False)
        st.session_state.log.to_excel(writer, sheet_name='Update_Log', index=False)
    st.download_button(
        label="⬇️ Download Excel",
        data=output.getvalue(),
        file_name="MMCCCL_lab_inventory_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.info("This will include both current inventory and the full update log.")

