import streamlit as st
import pandas as pd
import datetime
import os
from io import BytesIO
import base64

# ---- Load Logo ----
st.image("mmcccl_logo.png", width=200)

st.title("Meharry Medical College Consolidated Clinical Laboratory Inventory Tracker")

# ---- Load or Create Inventory Data ----
inventory_file = "inventory.csv"
if os.path.exists(inventory_file):
    df = pd.read_csv(inventory_file)
else:
    df = pd.DataFrame(columns=["Item", "Category", "Quantity", "Unit", "Location", "Expiration Date", "Minimum Stock Level"])
    df.to_csv(inventory_file, index=False)

# ---- Helper Function to Save Data ----
def save_inventory(dataframe):
    dataframe.to_csv(inventory_file, index=False)

# ---- Tabs ----
tab1, tab2, tab3, tab4 = st.tabs(["Add Items", "Update Inventory", "Stock & Expiration Alerts", "Download Data"])

# ---- Tab 1 ----
with tab1:
    st.subheader("➕ Add New Item")
    with st.form("add_item_form"):
        item = st.text_input("Item Name")
        category = st.text_input("Category")
        quantity = st.number_input("Quantity", min_value=0, step=1)
        unit = st.text_input("Unit")
        location = st.text_input("Location")
        expiration_date = st.date_input("Expiration Date", min_value=datetime.date.today())
        min_stock = st.number_input("Minimum Stock Level", min_value=0, step=1)
        submitted = st.form_submit_button("Add Item")
        
        if submitted and item.strip() != "":
            new_row = pd.DataFrame(
                [[item, category, quantity, unit, location, expiration_date, min_stock]],
                columns=df.columns
            )
            df = pd.concat([df, new_row], ignore_index=True)
            save_inventory(df)
            st.success(f"✅ '{item}' has been added to inventory.")

# ---- Tab 2 ----
with tab2:
    st.subheader("✏️ Update Inventory")
    if not df.empty:
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("Save Changes"):
            save_inventory(edited_df)
            df = edited_df
            st.success("💾 Inventory updated successfully!")
    else:
        st.info("📭 No items in inventory yet.")

# ---- Tab 3 ----
with tab3:
    st.subheader("⚠️ Stock & Expiration Alerts")
    
    if not df.empty:
        today = datetime.date.today()
        df["Expiration Date"] = pd.to_datetime(df["Expiration Date"], errors="coerce").dt.date
        
        expired_items = df[df["Expiration Date"] < today]
        expiring_soon_items = df[(df["Expiration Date"] >= today) & (df["Expiration Date"] <= today + datetime.timedelta(days=60))]
        low_stock_items = df[df["Quantity"] <= df["Minimum Stock Level"]]
        
        if not expired_items.empty:
            st.error("❌ Expired Items Detected!")
            st.dataframe(expired_items)
        if not expiring_soon_items.empty:
            st.warning("⏳ Items Expiring Soon (within 60 days)")
            st.dataframe(expiring_soon_items)
        if not low_stock_items.empty:
            st.info("📦 Items at or below minimum stock level")
            st.dataframe(low_stock_items)
        
        st.write("Full Inventory with Color Coding")
        def highlight_row(row):
            if row["Item"] in expired_items["Item"].values:
                return ["background-color: red; color: white"] * len(row)
            elif row["Item"] in expiring_soon_items["Item"].values:
                return ["background-color: yellow; color: black"] * len(row)
            elif row["Item"] in low_stock_items["Item"].values:
                return ["background-color: lightblue; color: black"] * len(row)
            else:
                return [""] * len(row)
        
        st.dataframe(df.style.apply(highlight_row, axis=1))
    else:
        st.info("📭 No items in inventory yet.")

# ---- Tab 4 ----
with tab4:
    st.subheader("📥 Download Inventory Data")
    if not df.empty:
        csv_data = df.to_csv(index=False)
        b64 = base64.b64encode(csv_data.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="inventory.csv">📄 Download CSV File</a>'
        st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("📭 No data available to download.")
