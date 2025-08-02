import streamlit as st
import pandas as pd
from datetime import datetime
import io

# Page setup
st.set_page_config(page_title="Lab Supply Tracker", layout="wide")

# --- Style ---
st.markdown("""
    <style>
    .big-font {
        font-size: 3em !important;
        font-weight: bold;
        color: #0072b2;
        padding-top: 2rem;
    }
    .main-header {
        color: #0072b2;
        font-size: 2.5em;
        font-weight: 600;
        margin-bottom: 0;
    }
    .secondary-header {
        color: #4b8c6a;
        font-size: 1.5em;
        font-weight: 500;
        margin-top: 0;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.25rem;
    }
    </style>
    """, unsafe_allow_html=True)

st.image("mmcccl_logo.png", use_container_width=True)

# ---- Load Excel Data ----
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    except FileNotFoundError:
        st.error("Error: File 'MMCCCL_supply_july.xlsx' not found.")
        return pd.DataFrame()

    df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')
    if 'ordered' not in df.columns:
        df['ordered'] = False
    if 'order_date' not in df.columns:
        df['order_date'] = pd.NaT
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    return df

# ---- Session State Init ----
if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'log' not in st.session_state:
    st.session_state.log = pd.DataFrame(columns=['timestamp', 'cat_no.', 'action', 'quantity', 'initials', 'lot_number', 'expiration'])

df = st.session_state.df
log_df = st.session_state.log

# ---- Tabs ----
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Inventory + Update Log",
    "📦 Item Locations",
    "⏰ Expiring Soon",
    "📁 Export Data"
])

# ---- Tab 1 ----
with tab1:
    st.subheader("📊 Inventory Level & Tracker")

    search_term = st.text_input("Search catalog number:")
    all_cat_nos = df['cat_no.'].astype(str).unique()
    filtered_cat_nos = sorted([cat for cat in all_cat_nos if search_term.lower() in str(cat).lower()])

    if not filtered_cat_nos:
        st.warning("No catalog numbers found.")
    else:
        selected_cat = st.selectbox("Select Catalog Number", filtered_cat_nos)
        item_data = df[df['cat_no.'] == selected_cat]
        item_name = item_data['item'].values[0] if not item_data.empty else "N/A"
        total_qty = item_data['quantity'].sum() if not item_data.empty else 0
        st.metric(label=f"{item_name} (Cat#: {selected_cat})", value=total_qty)

        initials = st.text_input("Your initials:")

        col1, col2 = st.columns(2)
        with col1:
            add_qty = st.number_input("Add Quantity", min_value=0, step=1, key="add_qty")
            remove_qty = st.number_input("Remove Quantity", min_value=0, step=1, key="remove_qty")
        with col2:
            lot_number = st.text_input("Lot Number", key="lot_number")
            expiration_date = st.date_input("Expiration Date", key="expiration_date")

        if st.button("Submit Update"):
            if not initials:
                st.error("Please enter your initials.")
            else:
                timestamp = datetime.now()

                # Add item
                if add_qty > 0:
                    new_row = {
                        'item': item_name,
                        'cat_no.': selected_cat,
                        'quantity': add_qty,
                        'location': item_data['location'].iloc[0] if not item_data.empty else "",
                        'shelf': item_data['shelf'].iloc[0] if not item_data.empty else "",
                        'expiration': expiration_date,
                        'ordered': False,
                        'order_date': pd.NaT
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                    log_df = pd.concat([log_df, pd.DataFrame([{
                        'timestamp': timestamp,
                        'cat_no.': selected_cat,
                        'action': 'Add',
                        'quantity': add_qty,
                        'initials': initials,
                        'lot_number': lot_number,
                        'expiration': expiration_date
                    }])], ignore_index=True)

                # Remove quantity
                if remove_qty > 0:
                    to_deduct = remove_qty
                    indices = df[df['cat_no.'] == selected_cat].sort_values(by='expiration').index
                    for i in indices:
                        if to_deduct <= 0:
                            break
                        available = df.at[i, 'quantity']
                        if available <= to_deduct:
                            to_deduct -= available
                            df.at[i, 'quantity'] = 0
                        else:
                            df.at[i, 'quantity'] -= to_deduct
                            to_deduct = 0

                    log_df = pd.concat([log_df, pd.DataFrame([{
                        'timestamp': timestamp,
                        'cat_no.': selected_cat,
                        'action': 'Remove',
                        'quantity': remove_qty,
                        'initials': initials,
                        'lot_number': lot_number,
                        'expiration': expiration_date
                    }])], ignore_index=True)

                df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
                st.session_state.df = df[df['quantity'] > 0].copy()
                st.session_state.log = log_df
                st.success("Inventory successfully updated.")
                st.rerun()

        # Show history
        st.markdown("#### 🔁 Update History")
        history = log_df[log_df['cat_no.'] == selected_cat].sort_values(by='timestamp', ascending=False)
        st.dataframe(history, use_container_width=True)
# ---- Tab 2: Item Locations ----
with tab2:
    st.subheader("📦 Item Locations")
    if not df.empty:
        st.dataframe(df[['item', 'cat_no.', 'location', 'shelf']].sort_values('item'), use_container_width=True)

# ---- Tab 3: Expiring Items ----
with tab3:
    st.subheader("⚠️ Items Needing Reorder (Expired)")
    today = datetime.now()
    
    if not df.empty:
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
    if not df.empty and not st.session_state.log.empty:
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
    else:
        st.warning("No data to export.")