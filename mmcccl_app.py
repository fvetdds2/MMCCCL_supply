import streamlit as st
import pandas as pd
from datetime import datetime
import io

# ----------------------------
# Page setup & styles
# ----------------------------
st.set_page_config(page_title="Lab Supply Tracker", layout="wide")

st.markdown("""
    <style>
    .big-font { font-size: 3em !important; font-weight: bold; color: #0072b2; padding-top: 2rem; }
    .main-header { color: #0072b2; font-size: 2.5em; font-weight: 600; margin-bottom: 0; }
    .secondary-header { color: #4b8c6a; font-size: 1.5em; font-weight: 500; margin-top: 0; }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 1.25rem; }
    </style>
    """, unsafe_allow_html=True)

st.image("mmcccl_logo.png", use_container_width=True)

# ----------------------------
# Robust Excel writer (ALWAYS creates a visible sheet)
# ----------------------------
def build_excel_bytes(sheets: dict) -> bytes:
    """
    Write a dict of {sheet_name: DataFrame} to an in-memory Excel file safely.
    - Writes all DataFrames (even if empty) so at least one sheet exists.
    - If no valid DataFrame provided, writes a small 'Info' sheet.
    - For openpyxl, forces first sheet visible & active.
    - Prefers xlsxwriter if installed (more forgiving); falls back to openpyxl.
    """
    output = io.BytesIO()

    # Prefer xlsxwriter if available
    try:
        import xlsxwriter  # noqa: F401
        engine = "xlsxwriter"
    except Exception:
        engine = "openpyxl"

    with pd.ExcelWriter(output, engine=engine) as writer:
        wrote_any = False
        for name, df in (sheets or {}).items():
            if isinstance(df, pd.DataFrame):
                safe_name = (str(name) or "Sheet1")[:31]
                # Write even if empty -> guarantees at least one sheet exists
                df.to_excel(writer, sheet_name=safe_name, index=False)
                wrote_any = True

        if not wrote_any:
            pd.DataFrame({"Info": ["No data available to export."]}).to_excel(
                writer, sheet_name="Info", index=False
            )

        # Ensure at least one visible, active sheet when using openpyxl
        if engine == "openpyxl":
            book = writer.book
            # Unhide all sheets just in case
            for ws in book.worksheets:
                ws.sheet_state = "visible"
            # Activate the first sheet
            book.active = 0

    return output.getvalue()

# ----------------------------
# Data loading
# ----------------------------
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    except FileNotFoundError:
        st.error("Error: File 'MMCCCL_supply_july.xlsx' not found.")
        return pd.DataFrame()

    # Normalize types/columns
    df['expiration'] = pd.to_datetime(df.get('expiration'), errors='coerce')
    if 'ordered' not in df.columns: df['ordered'] = False
    if 'order_date' not in df.columns: df['order_date'] = pd.NaT
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    df['quantity'] = pd.to_numeric(df.get('quantity'), errors='coerce').fillna(0).astype(int)
    if 'location' not in df.columns: df['location'] = ""
    if 'shelf' not in df.columns: df['shelf'] = ""
    if 'order_unit' not in df.columns: df['order_unit'] = ""
    if 'minimum_stock_level' not in df.columns: df['minimum_stock_level'] = 0
    if 'cat_no.' in df.columns: df['cat_no.'] = df['cat_no.'].astype(str)
    if 'item' in df.columns: df['item'] = df['item'].astype(str)
    return df

# ----------------------------
# Session state init
# ----------------------------
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

# ----------------------------
# Gate on user initials
# ----------------------------
if 'user_initials' not in st.session_state:
    st.session_state.user_initials = ""

st.session_state.user_initials = st.text_input(
    "Enter your initials (for audit tracking):",
    value=st.session_state.user_initials,
    key="initials_input"
)

if not st.session_state.user_initials:
    st.warning("Please enter your initials to continue.")
    st.stop()

user_initials = st.session_state.user_initials
df = st.session_state.df  # alias

# ----------------------------
# Tabs
# ----------------------------
tab1, tab2, tab3 = st.tabs(
    ["📊 Inventory + Update Log", "📦 Item Locations", "⏰ Needed to order & Expired"]
)

# ----------------------------
# Tab 1: Inventory + Update Log
# ----------------------------
with tab1:
    st.subheader("📊 Inventory Level & Tracker")

    search_term = st.text_input("Search catalog number or item name:", key="tab1_search").lower()
    if 'cat_no.' in st.session_state.df.columns and 'item' in st.session_state.df.columns:
        filtered_cat_nos = sorted(
            st.session_state.df[
                st.session_state.df['cat_no.'].str.lower().str.contains(search_term)
                | st.session_state.df['item'].str.lower().str.contains(search_term)
            ]['cat_no.'].unique()
        )
    else:
        filtered_cat_nos = []

    if not filtered_cat_nos:
        st.warning("No catalog numbers or items found.")
    else:
        selected_cat = st.selectbox("Select Catalog Number", filtered_cat_nos, key="select_cat")
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
            remove_qty = st.number_input("Remove Quantity", min_value=0, step=1, key="remove_qty")
            lot_number_remove = st.selectbox(
                "Lot Number (Remove)",
                item_data['lot #'].dropna().unique().tolist() if 'lot #' in item_data.columns else [],
                key="lot_remove"
            )
            expiration_remove = st.selectbox(
                "Expiration Date (Remove)",
                item_data['expiration'].dropna().unique().tolist(),
                key="exp_remove"
            )

        if st.button("Submit Update", key="submit_update"):
            timestamp = datetime.now()

            # --- Add flow
            if add_qty > 0:
                # Ensure we store a Timestamp to match df type
                exp_ts = pd.to_datetime(expiration_date_add) if pd.notna(expiration_date_add) else pd.NaT
                new_row = {
                    'item': item_name,
                    'cat_no.': selected_cat,
                    'quantity': int(add_qty),
                    'location': item_data['location'].iloc[0] if not item_data.empty else "",
                    'shelf': item_data['shelf'].iloc[0] if not item_data.empty else "",
                    'expiration': exp_ts,
                    'lot #': lot_number_add,
                    'ordered': False,
                    'order_date': pd.NaT
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
                        'lot #': lot_number_add,
                        'expiration': exp_ts
                    }])],
                    ignore_index=True
                )

            # --- Remove flow
            if remove_qty > 0:
                remove_qty_selected = int(remove_qty)
                idx_match = st.session_state.df[
                    (st.session_state.df['cat_no.'] == selected_cat)
                    & (st.session_state.df['lot #'] == lot_number_remove)
                    & (st.session_state.df['expiration'] == expiration_remove)
                ].index

                remaining_to_remove = remove_qty_selected
                for i in idx_match:
                    available = int(st.session_state.df.at[i, 'quantity'])
                    if remaining_to_remove >= available:
                        remaining_to_remove -= available
                        st.session_state.df.at[i, 'quantity'] = 0
                    else:
                        st.session_state.df.at[i, 'quantity'] = available - remaining_to_remove
                        remaining_to_remove = 0

                st.session_state.log = pd.concat(
                    [st.session_state.log, pd.DataFrame([{
                        'timestamp': timestamp,
                        'cat_no.': selected_cat,
                        'action': 'Remove',
                        'quantity': remove_qty_selected,
                        'initials': user_initials,
                        'lot #': lot_number_remove,
                        'expiration': expiration_remove
                    }])],
                    ignore_index=True
                )

            # Clean up empty rows & coerce int
            st.session_state.df['quantity'] = pd.to_numeric(
                st.session_state.df['quantity'], errors='coerce'
            ).fillna(0).astype(int)
            st.session_state.df = st.session_state.df[st.session_state.df['quantity'] > 0].copy()

            st.success("Inventory successfully updated.")
            st.rerun()

        st.markdown("#### 🔁 Update History")
        st.dataframe(
            st.session_state.log[st.session_state.log['cat_no.'] == selected_cat]
            .sort_values(by='timestamp', ascending=False),
            use_container_width=True
        )

        # Download button (Tab 1) — SAFE
        excel_bytes = build_excel_bytes({
            "Inventory": st.session_state.df,
            "Update_Log": st.session_state.log
        })
        st.download_button(
            label="⬇️ Download Updated Inventory + Log",
            data=excel_bytes,
            file_name=f"MMCCCL_inventory_log_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_tab1"
        )

# ----------------------------
# Tab 2: Item locations
# ----------------------------
with tab2:
    st.subheader("📦 Item Locations")

    # Force editable columns to be strings
    st.session_state.df["location"] = st.session_state.df["location"].astype(str)
    st.session_state.df["shelf"] = st.session_state.df["shelf"].astype(str)

    # Make editable copy with original index preserved
    editable_df = st.session_state.df.copy()
    editable_df.reset_index(inplace=True)  # keep original index as a column
    editable_df.rename(columns={"index": "orig_index"}, inplace=True)

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
        },
        key="locations_editor"
    )

    if st.button("💾 Save Location Changes", key="save_locations"):
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

    st.markdown("### 📜 Location Change Audit Log")
    st.dataframe(
        st.session_state.location_audit_log.sort_values(by="timestamp", ascending=False),
        use_container_width=True
    )

    # Download updated inventory + audit log (SAFE)
    excel_bytes_tab2 = build_excel_bytes({
        "Inventory": st.session_state.df,
        "Location_Audit_Log": st.session_state.location_audit_log
    })
    st.download_button(
        label="📥 Download Updated Inventory (Excel)",
        data=excel_bytes_tab2,
        file_name="MMCCCL_supply_updated_locations.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_tab2"
    )

# ----------------------------
# Tab 3: Needed to order & Expired
# ----------------------------
with tab3:
    st.subheader("⚠️ Items Needing Reorder / Attention")

    today = datetime.now()
    two_months_from_now = today + pd.DateOffset(months=2)

    # Identify Expired & Soon to Expire
    expired = df[df['expiration'].notna() & (df['expiration'] < today)]
    soon_expire = df[df['expiration'].notna() & (df['expiration'] >= today) & (df['expiration'] <= two_months_from_now)]

    # Identify Urgent Reorder (Low Stock)
    if "minimum_stock_level" not in df.columns:
        df["minimum_stock_level"] = 0
    urgent_reorder = df[df["quantity"] <= df["minimum_stock_level"]]

    # Alerts
    expired_count = expired.shape[0]
    soon_count = soon_expire.shape[0]
    urgent_count = urgent_reorder.shape[0]

    if expired_count > 0:
        st.markdown(f"""
            <p style="font-size:28px; color:#696969; font-weight:bold;">
                🚨 {expired_count} item{'s' if expired_count > 1 else ''} have EXPIRED!
            </p>
        """, unsafe_allow_html=True)

    if urgent_count > 0:
        st.markdown(f"""
            <p style="font-size:26px; color:#b30000; font-weight:bold;">
                🔴 URGENT: {urgent_count} item{'s' if urgent_count > 1 else ''} are at or below minimum stock level!
            </p>
        """, unsafe_allow_html=True)

    if soon_count > 0:
        st.markdown(f"""
            <p style="font-size:22px; color:#008000; font-weight:bold;">
                ⚠️ {soon_count} item{'s' if soon_count > 1 else ''} will expire within 2 months.
            </p>
        """, unsafe_allow_html=True)

    # Combine items to show
    reorder_items = pd.concat([expired, soon_expire, urgent_reorder]).drop_duplicates()

    search_term_tab3 = st.text_input("🔍 Search item or catalog no.", key="tab3_search").lower()
    if search_term_tab3 and not reorder_items.empty:
        if 'item' in reorder_items.columns and 'cat_no.' in reorder_items.columns:
            reorder_items = reorder_items[
                reorder_items['item'].str.lower().str.contains(search_term_tab3)
                | reorder_items['cat_no.'].str.lower().str.contains(search_term_tab3)
            ]

    if reorder_items.empty:
        st.success("🎉 No expired, soon-to-expire, or low-stock items!")
        st.stop()

    # Editable "Order Qty" (default 0)
    if "Order Qty" not in reorder_items.columns:
        reorder_items = reorder_items.copy()
        reorder_items["Order Qty"] = 0

    display_df = reorder_items[['item', 'cat_no.', 'quantity', 'minimum_stock_level',
                                'order_unit', 'expiration', 'Order Qty']].copy()

    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "item": st.column_config.Column(disabled=True),
            "cat_no.": st.column_config.Column(disabled=True),
            "quantity": st.column_config.Column(disabled=True),
            "minimum_stock_level": st.column_config.Column(disabled=True),
            "order_unit": st.column_config.Column(disabled=True),
            "expiration": st.column_config.Column(disabled=True),
            "Order Qty": st.column_config.NumberColumn(min_value=0, step=1),
        },
        key="order_qty_editor"
    )

    if st.button("✅ Save Order Log", key="save_order_log"):
        order_records = []
        for _, row in edited_df.reset_index(drop=True).iterrows():
            if int(row.get("Order Qty", 0)) > 0:
                order_records.append({
                    "timestamp": datetime.now(),
                    "user": st.session_state.user_initials or "N/A",
                    "cat_no.": row.get("cat_no."),
                    "item": row.get("item"),
                    "expiration": row.get("expiration"),
                    "order_unit": row.get("order_unit"),
                    "quantity_order": int(row.get("Order Qty", 0))
                })

        if order_records:
            st.session_state.order_log = pd.concat(
                [st.session_state.order_log, pd.DataFrame(order_records)],
                ignore_index=True
            )
            st.success("Order log saved!")
        else:
            st.info("No order quantities entered.")

    if not st.session_state.order_log.empty:
        st.markdown("### 📜 Order Log")
        st.dataframe(
            st.session_state.order_log.sort_values(by="timestamp", ascending=False),
            use_container_width=True
        )
