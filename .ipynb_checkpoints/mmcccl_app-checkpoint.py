import streamlit as st
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Lab Supply Tracker", layout="wide")


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


    st.image("mmcccl_logo.png", width=800)


# ---- Load Excel Data ----
@st.cache_data
def load_data():
    """Loads and preprocesses the data from the Excel file."""
    # The excel file name should be 'MMCCCL_supply_july.xlsx'
    try:
        df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    except FileNotFoundError:
        st.error("Error: The file 'MMCCCL_supply_july.xlsx' was not found.")
        return pd.DataFrame() # Return an empty DataFrame to prevent errors
    
    # Convert 'expiration' to datetime, handling potential errors
    df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')
    
    # Ensure 'ordered' and 'order_date' columns exist
    if 'ordered' not in df.columns:
        df['ordered'] = False
    if 'order_date' not in df.columns:
        df['order_date'] = pd.NaT
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    
    return df

# ---- Session State Init ----
# Initialize session state for the DataFrame and the log
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'log' not in st.session_state:
    # Now includes 'lot_number' and 'expiration' in the log DataFrame
    st.session_state.log = pd.DataFrame(columns=['timestamp', 'cat_no.', 'action', 'quantity', 'initials', 'lot_number', 'expiration'])

# Get the DataFrames from session state
df = st.session_state.df
log_df = st.session_state.log

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
    all_cat_nos = df['cat_no.'].astype(str).unique()
    filtered_cat_nos = sorted(
        [
            cat
            for cat in all_cat_nos
            if pd.notna(cat) and (search_term.lower() in str(cat).lower())
        ]
    )
    if not filtered_cat_nos:
        st.warning("No catalog numbers found.")
    else:
        selected_cat = st.selectbox("Select Catalog Number", filtered_cat_nos)
    
        # Ensure that selected_cat is a valid number before proceeding
        if selected_cat:
            item_data = df[df['cat_no.'] == selected_cat]
            item_name = item_data['item'].values[0] if not item_data.empty else "N/A"
            total_qty = item_data['quantity'].sum() if not item_data.empty else 0
            st.metric(label=f"{item_name} (Cat#: {selected_cat})", value=total_qty)

            initials = st.text_input("Your initials:")
            
            # Use columns for a cleaner layout
            col1, col2 = st.columns(2)
            with col1:
                add_qty = st.number_input("Add Quantity", min_value=0, step=1, key="add_qty")
                remove_qty = st.number_input("Remove Quantity", min_value=0, step=1, key="remove_qty")
            with col2:
                # New input fields for lot number and expiration date
                lot_number = st.text_input("Lot Number", key="lot_number")
                expiration_date = st.date_input("Expiration Date", key="expiration_date")

            if st.button("Submit Update"):
                if not initials:
                    st.error("Please enter your initials to submit an update.")
                else:
                    idxs = df[df['cat_no.'] == selected_cat].index
                    if not idxs.empty:
                        idx = idxs[0]
                        net_change = add_qty - remove_qty
                        df.at[idx, 'quantity'] += net_change

                        timestamp = datetime.now()
                        
                        # Log additions with lot number and expiration date
                        if add_qty > 0:
                            new_log = pd.DataFrame([{
                                'timestamp': timestamp,
                                'cat_no.': selected_cat,
                                'action': 'Add',
                                'quantity': add_qty,
                                'initials': initials,
                                'lot_number': lot_number,
                                'expiration': expiration_date
                            }])
                            st.session_state.log = pd.concat([st.session_state.log, new_log], ignore_index=True)

                        # Log removals with lot number and expiration date
                        if remove_qty > 0:
                            new_log = pd.DataFrame([{
                                'timestamp': timestamp,
                                'cat_no.': selected_cat,
                                'action': 'Remove',
                                'quantity': remove_qty,
                                'initials': initials,
                                'lot_number': lot_number,
                                'expiration': expiration_date
                            }])
                            st.session_state.log = pd.concat([st.session_state.log, new_log], ignore_index=True)

                        st.success(f"Inventory updated. New quantity: {df.at[idx, 'quantity']}")
                    else:
                        st.error("Item not found!")

    # Show history for this item
    st.markdown("#### 🔁 Update History")
    # Check if a catalog number is selected before filtering the log
    if 'selected_cat' in locals() and selected_cat:
        history = log_df[log_df['cat_no.'] == selected_cat].sort_values(by='timestamp', ascending=False)
        st.dataframe(history, use_container_width=True)
    else:
        st.info("Please select a catalog number to view its history.")


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
