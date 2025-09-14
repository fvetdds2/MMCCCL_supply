import streamlit as st
import pandas as pd
from datetime import datetime
import io

# Page setup
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")

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

    # Coercions / defaults
    if 'expiration' in df.columns:
        df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')
    else:
        df['expiration'] = pd.NaT

    if 'ordered' not in df.columns:
        df['ordered'] = False
    if 'order_date' not in df.columns:
        df['order_date'] = pd.NaT
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')

    if 'quantity' in df.columns:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    else:
        df['quantity'] = 0

    for col in ['location', 'shelf', 'order_unit']:
        if col not in df.columns:
            df[col] = ""

    # Ensure key columns exist (strings)
    for col in ['cat_no.', 'item', 'lot #']:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(str)

    return df

# ---- Session State Init ----
if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'log' not in st.session_state:
    st.session_state.log = pd.DataFrame(
        columns=['timestamp', 'cat_no.', 'action', 'quantity', 'initials', 'lot #', 'expiration']
    )

if 'location_audit_log' not in st.session_state:
    st.session_state.location_audit_log = pd.DataFrame(
        columns=['timestamp', 'user', 'cat_no.', 'item', 'field', 'old_value', 'new_value']
    )

if 'order_log' not in st.session_state:
    st.session_state.order_log = pd.DataFrame(
        columns=['timestamp', 'user', 'cat_no.', 'item', 'expiration', 'order_unit', 'quantity_order']
    )

# --- Global User Initials Input ---
if 'user_initials' not in st.session_state:
    st.session_state.user_initials = ""

st.session_state.user_initials = st.text_input(
    "Enter your initials (for audit tracking):",
    value=st.session_state.user_initials
).upper()

if not st.session_state.user_initials:
    st.warning("Please enter your initials to continue.")
    st.stop()

user_initials = st.session_state.user_initials
df = st.session_state.df
log_df = st.session_state.log
audit_df = st.session_state.location_audit_log

# ---- Tabs ----
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Add or Remove items in the inventory + Update Log",
    "📦 Editable Item Locations",
    "⏰ Needed to order & Expired & Expiring in 60 Days",
    "📁 Export Data into excel file"
])

# Utility: ensure openpyxl workbook has a visible active sheet
def _ensure_visible_active_sheet(writer):
    wb = writer.book
    if not wb.worksheets:
        wb.create_sheet("Sheet1")
    # Make sure every sheet is visible
    for ws in wb.worksheets:
        ws.sheet_state = "visible"
    wb.active = 0

# ---- Tab 1 ----
with tab1:
    st.subheader("📊 Inventory Level & Tracker")

    # Safe string dtypes for search
    st.session_state.df['cat_no.'] = st.session_state.df['cat_no.'].astype(str)
    st.session_state.df['item'] = st.session_state.df['item'].astype(str)

    search_term = st.text_input("Search catalog number or item name:").lower().strip()
    if search_term:
        mask = (
            st.session_state.df['cat_no.'].str.lower().str.contains(search_term, na=False) |
            st.session_state.df['item'].str.lower().str.contains(search_term, na=False)
        )
        filtered_cat_nos = sorted(st.session_state.df[mask]['cat_no.'].unique())
    else:
        filtered_cat_nos = sorted(st.session_state.df['cat_no.'].unique())

    if not filtered_cat_nos:
        st.warning("No catalog numbers or items found.")
    else:
        selected_cat = st.selectbox("Select Catalog Number", filtered_cat_nos)
        item_data = st.session_state.df[st.session_state.df['cat_no.'] == selected_cat]
        item_name = item_data['item'].values[0] if not item_data.empty else "N/A"
        total_qty = int(item_data['quantity'].sum()) if not item_data.empty else 0

        st.metric(label=f"{item_name} (Cat#: {selected_cat})", value=total_qty)

        col1, col2 = st.columns(2)
        with col1:
            add_qty = st.number_input("Add Quantity", min_value=0, step=1, key="add_qty")
            lot_number_add = st.text_input("Lot Number (Add)", key="lot_number_add")
            expiration_date_add = st.date_input("Expiration Date (Add)", key="expiration_date_add")
        with col2:
            remove_qty_input = st.number_input("Remove Quantity", min_value=0, step=1, key="remove_qty")
            lot_opts = item_data['lot #'].dropna().unique() if 'lot #' in item_data.columns else []
            lot_number_remove = st.selectbox("Lot Number (Remove)", lot_opts)
            exp_opts = item_data['expiration'].dropna().unique()
            expiration_remove = st.selectbox("Expiration Date (Remove)", exp_opts)

        if st.button("Submit Update"):
            timestamp = datetime.now()

            # ADD path
            if add_qty > 0:
                new_row = {
                    'item': item_name,
                    'cat_no.': selected_cat,
                    'quantity': int(add_qty),
                    'location': item_data['location'].iloc[0] if not item_data.empty else "",
                    'shelf': item_data['shelf'].iloc[0] if not item_data.empty else "",
                    'expiration': pd.to_datetime(expiration_date_add),
                    'lot #': str(lot_number_add),
                    'ordered': False,
                    'order_date': pd.NaT,
                    'order_unit': item_data['order_unit'].iloc[0] if 'order_unit' in item_data.columns and not item_data.empty else ""
                }
                st.session_state.df = pd.concat(
                    [st.session_state.df, pd.DataFrame([new_row])],
                    ignore_index=True
                )

                st.session_state.log = pd.concat(
                    [st.session_state.log, pd.DataFrame([{
                        'timestamp': timestamp,
                        'cat_no.': selected_cat,
                        'action': 'Add',
                        'quantity': int(add_qty),
                        'initials': user_initials,
                        'lot #': str(lot_number_add),
                        'expiration': pd.to_datetime(expiration_date_add)
                    }])],
                    ignore_index=True
                )

            # REMOVE path (track actual removed qty)
            removed_qty_total = 0
            if remove_qty_input > 0:
                idx_match = st.session_state.df[
                    (st.session_state.df['cat_no.'] == selected_cat) &
                    (st.session_state.df['lot #'] == str(lot_number_remove)) &
                    (st.session_state.df['expiration'] == pd.to_datetime(expiration_remove))
                ].index

                remaining_to_remove = int(remove_qty_input)
                for i in idx_match:
                    available = int(st.session_state.df.at[i, 'quantity'])
                    if available <= 0:
                        continue
                    if remaining_to_remove >= available:
                        remaining_to_remove -= available
                        removed_qty_total += available
                        st.session_state.df.at[i, 'quantity'] = 0
                    else:
                        st.session_state.df.at[i, 'quantity'] = available - remaining_to_remove
                        removed_qty_total += remaining_to_remove
                        remaining_to_remove = 0
                        break

                # Log only if something was removed
                if removed_qty_total > 0:
                    st.session_state.log = pd.concat(
                        [st.session_state.log, pd.DataFrame([{
                            'timestamp': timestamp,
                            'cat_no.': selected_cat,
                            'action': 'Remove',
                            'quantity': int(removed_qty_total),
                            'initials': user_initials,
                            'lot #': str(lot_number_remove),
                            'expiration': pd.to_datetime(expiration_remove)
                        }])],
                        ignore_index=True
                    )

            # Normalize df and drop zeros
            st.session_state.df['quantity'] = pd.to_numeric(
                st.session_state.df['quantity'], errors='coerce'
            ).fillna(0).astype(int)
            st.session_state.df = st.session_state.df[st.session_state.df['quantity'] > 0].copy()

            st.success("Inventory successfully updated.")
            st.rerun()

        st.markdown("#### 🔁 Update History")
        if not st.session_state.log.empty:
            st.dataframe(
                st.session_state.log[st.session_state.log['cat_no.'] == selected_cat].sort_values(
                    by='timestamp', ascending=False
                ),
                use_container_width=True
            )
        else:
            st.info("No updates logged yet for this item.")

# ---- Tab 2 ----
with tab2:
    st.subheader("📦 Item Locations")

    # Ensure session state variables exist
    if "df" not in st.session_state:
        st.session_state.df = pd.DataFrame(columns=["item", "cat_no.", "location", "shelf"])
    if "location_audit_log" not in st.session_state:
        st.session_state.location_audit_log = pd.DataFrame(columns=[
            "timestamp", "user", "cat_no.", "item", "field", "old_value", "new_value"
        ])

    # Force editable columns to be strings
    st.session_state.df["location"] = st.session_state.df["location"].astype(str)
    st.session_state.df["shelf"] = st.session_state.df["shelf"].astype(str)

    # Make editable copy with original index preserved
    editable_df = st.session_state.df.copy()
    editable_df.reset_index(inplace=True)  # keep original index as a column
    editable_df.rename(columns={"index": "orig_index"}, inplace=True)

    # Let user edit location and shelf
    edited_df = st.data_editor(
        editable_df[["orig_index", "item", "cat_no.", "location", "shelf"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "orig_index": st.column_config.Column(disabled=True, width="small"),
            "item": st.column_config.Column(disabled=True),
            "cat_no.": st.column_config.Column(disabled=True),
            "location": st.column_config.Column(required=True),
            "shelf": st.column_config.Column(required=True)
        }
    )

    if st.button("💾 Save Location Changes"):
        changes_made, audit_entries = False, []

        for _, row in edited_df.iterrows():
            idx = row["orig_index"]
            for field in ["location", "shelf"]:
                old_value = str(st.session_state.df.at[idx, field])
                new_value = str(row[field])
                if old_value != new_value:
                    st.session_state.df.at[idx, field] = new_value
                    changes_made = True
                    audit_entries.append({
                        "timestamp": datetime.now(),
                        "user": st.session_state.user_initials or "N/A",
                        "cat_no.": st.session_state.df.at[idx, "cat_no."],
                        "item": st.session_state.df.at[idx, "item"],
                        "field": field,
                        "old_value": old_value,
                        "new_value": new_value
                    })

        if changes_made:
            st.session_state.location_audit_log = pd.concat(
                [st.session_state.location_audit_log, pd.DataFrame(audit_entries)],
                ignore_index=True
            )
            st.success("✅ Location/Shelf changes saved.")
        else:
            st.info("No changes detected.")

    # Show audit log
    st.markdown("### 📜 Location Change Audit Log")
    st.dataframe(
        st.session_state.location_audit_log.sort_values(by="timestamp", ascending=False),
        use_container_width=True
    )

    # Download updated inventory + logs (INCLUDES FULL DATA SHEET)
    if not st.session_state.df.empty:
        output_loc = io.BytesIO()
        with pd.ExcelWriter(output_loc, engine="openpyxl") as writer:
            # Full current data (what you asked to show)
            st.session_state.df.to_excel(writer, sheet_name="Inventory", index=False)
            # Location changes
            st.session_state.location_audit_log.to_excel(writer, sheet_name="Location_Audit_Log", index=False)
            # Update log (adds/removes)
            st.session_state.log.to_excel(writer, sheet_name="Update_Log", index=False)
            # Order log
            st.session_state.order_log.to_excel(writer, sheet_name="Order_Log", index=False)

            # ✅ Prevent "At least one sheet must be visible"
            _ensure_visible_active_sheet(writer)

        st.download_button(
            label="📥 Download Updated Inventory (Excel)",
            data=output_loc.getvalue(),
            file_name="MMCCCL_supply_updated_locations.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---- Tab 3 ----
with tab3:
    st.subheader("⚠️ Items Needing Reorder / Attention")

    if "order_log" not in st.session_state:
        st.session_state.order_log = pd.DataFrame(columns=[
            "timestamp", "user", "cat_no.", "item", "expiration", "order_unit", "quantity_order"
        ])

    today = datetime.now()
    two_months_from_now = today + pd.DateOffset(months=2)

    # --- Identify Expired & Soon to Expire ---
    expired = df[df['expiration'].notna() & (df['expiration'] < today)]
    soon_expire = df[df['expiration'].notna() & (df['expiration'] >= today) & (df['expiration'] <= two_months_from_now)]

    # --- Identify Urgent Reorder (Low Stock) ---
    if "minimum_stock_level" not in df.columns:
        df["minimum_stock_level"] = 0  # default if missing

    urgent_reorder = df[df["quantity"] <= df["minimum_stock_level"]]

    # --- Counts for Alerts ---
    expired_count = expired.shape[0]
    soon_count = soon_expire.shape[0]
    urgent_count = urgent_reorder.shape[0]

    # --- Alerts ---
    if expired_count > 0:
        st.markdown(f"""
            <p style="font-size:28px; color:#696969; font-weight:bold;">
                🚨 {expired_count} item{'s' if expired_count > 1 else ''} have EXPIRED! (gray highlight in the table)
            </p>
            <p style="font-size:18px; color:#696969;">
                Please remove or exchange them immediately.
            </p>
        """, unsafe_allow_html=True)
    if urgent_count > 0:
        st.markdown(f"""
            <p style="font-size:26px; color:#b30000; font-weight:bold;">
                🔴 URGENT: {urgent_count} item{'s' if urgent_count > 1 else ''} are at or below minimum stock level! (orange highlight in the table)
            </p>
            <p style="font-size:16px; color:#b30000;">
                Reorder immediately to avoid supply shortages.
            </p>
        """, unsafe_allow_html=True)
    if soon_count > 0:
        st.markdown(f"""
            <p style="font-size:22px; color:#008000; font-weight:bold;">
                ⚠️ {soon_count} item{'s' if soon_count > 1 else ''} will expire within 2 months. (green highlight in the table)
            </p>
            <p style="font-size:16px; color:#008000;">
                Consider reordering soon.
            </p>
        """, unsafe_allow_html=True)

    # --- Combine All Items to Show ---
    reorder_items = pd.concat([expired, soon_expire, urgent_reorder]).drop_duplicates()

    search_term = st.text_input("🔍 Search item or catalog no.").lower().strip()
    if search_term:
        reorder_items = reorder_items[
            reorder_items['item'].str.lower().str.contains(search_term, na=False) |
            reorder_items['cat_no.'].str.lower().str.contains(search_term, na=False)
        ]

    if reorder_items.empty:
        st.success("🎉 No expired, soon-to-expire, or low-stock items!")
        st.stop()

    if "Order Qty" not in reorder_items.columns:
        reorder_items["Order Qty"] = 0

    # Highlighting function for display only
    def highlight_row(row):
        if row["quantity"] <= row["minimum_stock_level"]:
            return ['background-color: lightcoral'] * len(row)
        elif pd.notna(row["expiration"]) and row["expiration"] < today:
            return ['background-color: lightgray'] * len(row)
        elif pd.notna(row["expiration"]) and today <= row["expiration"] <= two_months_from_now:
            return ['background-color: lightgreen'] * len(row)
        else:
            return [''] * len(row)

    # Display a colored (non-editable) view
    display_df = reorder_items[['item', 'cat_no.', 'quantity', 'minimum_stock_level', 'order_unit', 'expiration', 'Order Qty']].copy()
    st.markdown("#### Items Requiring Attention (colored)")
    st.dataframe(
        display_df.style.apply(highlight_row, axis=1),
        use_container_width=True
    )

    st.markdown("#### Enter Order Quantities")
edited_df = st.data_editor(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "item": st.column_config.Column(disabled=True),
        "cat_no.": st.column_config.Column(disabled=True),
        "quantity": st.column_config.Column(disabled=True),
        "minimum_stock_level": st.column_config.Column(disabled=True),  # ✅ add the value
        "order_unit": st.column_config.Column(disabled=True),
        "expiration": st.column_config.Column(disabled=True),
        "Order Qty": st.column_config.NumberColumn(min_value=0, step=1),
    },
    key="order_qty_editor",
)