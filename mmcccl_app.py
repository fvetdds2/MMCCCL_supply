import streamlit as st
import pandas as pd
from datetime import datetime
import io

# Page setup
st.set_page_config(page_title="Lab Supply Tracker", layout="wide")

# --- Style ---
st.markdown("""
    <style>
    .big-font { font-size: 3em !important; font-weight: bold; color: #0072b2; padding-top: 2rem; }
    .main-header { color: #0072b2; font-size: 2.5em; font-weight: 600; margin-bottom: 0; }
    .secondary-header { color: #4b8c6a; font-size: 1.5em; font-weight: 500; margin-top: 0; }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 1.25rem; }
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
    if 'ordered' not in df.columns: df['ordered'] = False
    if 'order_date' not in df.columns: df['order_date'] = pd.NaT
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    if 'location' not in df.columns: df['location'] = ""
    if 'shelf' not in df.columns: df['shelf'] = ""
    if 'order_unit' not in df.columns: df['order_unit'] = ""
    return df

# ---- Session State Init ----
if 'df' not in st.session_state: st.session_state.df = load_data()
if 'log' not in st.session_state:
    st.session_state.log = pd.DataFrame(columns=['timestamp', 'cat_no.', 'action', 'quantity', 'initials', 'lot #', 'expiration'])
if 'location_audit_log' not in st.session_state:
    st.session_state.location_audit_log = pd.DataFrame(columns=['timestamp', 'user', 'cat_no.', 'item', 'field', 'old_value', 'new_value'])
if 'order_log' not in st.session_state:
    st.session_state.order_log = pd.DataFrame(columns=['timestamp', 'user', 'cat_no.', 'item', 'expiration', 'order_unit', 'quantity_order'])

# --- Global User Initials Input ---
if 'user_initials' not in st.session_state: st.session_state.user_initials = ""
st.session_state.user_initials = st.text_input("Enter your initials (for audit tracking):", value=st.session_state.user_initials)
if not st.session_state.user_initials:
    st.warning("Please enter your initials to continue.")
    st.stop()

user_initials = st.session_state.user_initials
df = st.session_state.df
log_df = st.session_state.log
audit_df = st.session_state.location_audit_log

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
    search_term = st.text_input("Search catalog number or item name:").lower()
    df['cat_no.'] = df['cat_no.'].astype(str)
    df['item'] = df['item'].astype(str)

    filtered_cat_nos = sorted(df[df['cat_no.'].str.lower().str.contains(search_term) | df['item'].str.lower().str.contains(search_term)]['cat_no.'].unique())
    if not filtered_cat_nos:
        st.warning("No catalog numbers or items found.")
    else:
        selected_cat = st.selectbox("Select Catalog Number", filtered_cat_nos)
        item_data = df[df['cat_no.'] == selected_cat]
        item_name = item_data['item'].values[0] if not item_data.empty else "N/A"
        total_qty = item_data['quantity'].sum() if not item_data.empty else 0
        st.metric(label=f"{item_name} (Cat#: {selected_cat})", value=total_qty)

        col1, col2 = st.columns(2)
        with col1:
            add_qty = st.number_input("Add Quantity", min_value=0, step=1, key="add_qty")
            lot_number_add = st.text_input("Lot Number (Add)", key="lot_number_add")
            expiration_date_add = st.date_input("Expiration Date (Add)", key="expiration_date_add")
        with col2:
            remove_qty = st.number_input("Remove Quantity", min_value=0, step=1, key="remove_qty")
            lot_number_remove = st.selectbox("Lot Number (Remove)", item_data['lot #'].dropna().unique() if 'lot #' in item_data.columns else [])
            expiration_remove = st.selectbox("Expiration Date (Remove)", item_data['expiration'].dropna().unique())

        if st.button("Submit Update"):
            timestamp = datetime.now()
            if add_qty > 0:
                new_row = {
                    'item': item_name,
                    'cat_no.': selected_cat,
                    'quantity': add_qty,
                    'location': item_data['location'].iloc[0] if not item_data.empty else "",
                    'shelf': item_data['shelf'].iloc[0] if not item_data.empty else "",
                    'expiration': expiration_date_add,
                    'lot #': lot_number_add,
                    'ordered': False,
                    'order_date': pd.NaT
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                log_df = pd.concat([log_df, pd.DataFrame([{
                    'timestamp': timestamp, 'cat_no.': selected_cat, 'action': 'Add',
                    'quantity': add_qty, 'initials': user_initials, 'lot #': lot_number_add, 'expiration': expiration_date_add
                }])], ignore_index=True)

            if remove_qty > 0:
                idx_match = df[(df['cat_no.'] == selected_cat) & (df['lot #'] == lot_number_remove) & (df['expiration'] == expiration_remove)].index
                for i in idx_match:
                    available = df.at[i, 'quantity']
                    if remove_qty >= available:
                        remove_qty -= available
                        df.at[i, 'quantity'] = 0
                    else:
                        df.at[i, 'quantity'] -= remove_qty
                        remove_qty = 0
                log_df = pd.concat([log_df, pd.DataFrame([{
                    'timestamp': timestamp, 'cat_no.': selected_cat, 'action': 'Remove',
                    'quantity': st.session_state.remove_qty if 'remove_qty' in st.session_state else 0,
                    'initials': user_initials, 'lot #': lot_number_remove, 'expiration': expiration_remove
                }])], ignore_index=True)

            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
            st.session_state.df = df[df['quantity'] > 0].copy()
            st.session_state.log = log_df
            st.success("Inventory successfully updated.")

        st.markdown("#### 🔁 Update History")
        st.dataframe(log_df[log_df['cat_no.'] == selected_cat].sort_values(by='timestamp', ascending=False), use_container_width=True)

# ---- Tab 2 ----
with tab2:
    st.subheader("📦 Item Locations")
    editable_df = df[['item', 'cat_no.', 'location', 'shelf']].copy()
    edited_table = st.data_editor(editable_df, use_container_width=True, num_rows="dynamic", key="editable_location",
                                  column_config={"item": st.column_config.Column(disabled=True), "cat_no.": st.column_config.Column(disabled=True)})
    if st.button("💾 Save Changes"):
        changes_made, audit_entries = False, []
        for idx, row in edited_table.iterrows():
            cat, item = row['cat_no.'], row['item']
            old_row = df[(df['cat_no.'] == cat) & (df['item'] == item)].iloc[0]
            for field in ['location', 'shelf']:
                if row[field] != old_row[field]:
                    df.loc[(df['cat_no.'] == cat) & (df['item'] == item), field] = row[field]
                    changes_made = True
                    audit_entries.append({'timestamp': datetime.now(), 'user': user_initials, 'cat_no.': cat, 'item': item,
                                          'field': field, 'old_value': old_row[field], 'new_value': row[field]})
        if changes_made:
            st.session_state.df = df
            st.session_state.location_audit_log = pd.concat([audit_df, pd.DataFrame(audit_entries)], ignore_index=True)
            st.success("Changes saved successfully!")
        else:
            st.info("No changes detected.")
    st.dataframe(audit_df.sort_values(by="timestamp", ascending=False), use_container_width=True)

# ---- Tab 3 ----
with tab3:
    st.subheader("⚠️ Items Needing Reorder")
    today, two_months_from_now = datetime.now(), datetime.now() + pd.DateOffset(months=2)
    expired = df[df['expiration'].notna() & (df['expiration'] < today)]
    soon_expire = df[df['expiration'].notna() & (df['expiration'] >= today) & (df['expiration'] <= two_months_from_now)]
    reorder_items = pd.concat([expired, soon_expire]).drop_duplicates()

    def highlight_rows(row):
        if row['expiration'] < today: return ['background-color: lightblue'] * len(row)
        elif row['expiration'] <= two_months_from_now: return ['background-color: lightcoral'] * len(row)
        return [''] * len(row)

    if reorder_items.empty:
        st.success("🎉 No expired or soon-to-expire items!")
    else:
        st.dataframe(reorder_items[['item', 'cat_no.', 'quantity', 'order_unit', 'expiration']].style.apply(highlight_rows, axis=1), use_container_width=True)
        order_records = []
        for idx, row in reorder_items.iterrows():
            qty = st.number_input(f"Order qty for {row['item']} ({row['order_unit']})", min_value=0, step=1, key=f"order_qty_{idx}")
            if qty > 0:
                order_records.append({'timestamp': datetime.now(), 'user': user_initials, 'cat_no.': row['cat_no.'],
                                      'item': row['item'], 'expiration': row['expiration'], 'order_unit': row['order_unit'], 'quantity_order': qty})
        if st.button("✅ Save Order Log") and order_records:
            st.session_state.order_log = pd.concat([st.session_state.order_log, pd.DataFrame(order_records)], ignore_index=True)
            st.success("Order log saved!")

# ---- Tab 4 ----
with tab4:
    st.subheader("📁 Export Inventory, Update Log, Location Audit Log, and Order Log")
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Inventory', index=False)
            st.session_state.log.to_excel(writer, sheet_name='Update_Log', index=False)
            st.session_state.location_audit_log.to_excel(writer, sheet_name='Location_Audit_Log', index=False)
            st.session_state.order_log.to_excel(writer, sheet_name='Order_Log', index=False)
        st.download_button(label="⬇️ Download Excel", data=output.getvalue(),
                          file_name="MMCCCL_lab_inventory_export.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("No data to export.")