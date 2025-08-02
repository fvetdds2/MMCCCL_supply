import streamlit as st
import pandas as pd
from datetime import datetime
import qrcode
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, WebRtcMode
import av
import cv2
from pyzbar.pyzbar import decode
import io

# Config
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")

# Load Data
@st.cache_data
def load_data():
    df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')
    df['ordered'] = False
    df['order_date'] = pd.NaT
    return df

if 'df' not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

# App Title
st.title("🧪 MMCCCL Lab Supply Tracker")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Current Inventory", "📦 Item Location", "⚠️ Reorder List", "📝 Notes/Future"])

# ------------------------
# 📊 Tab 1: Inventory Tab
# ------------------------
with tab1:
    st.header("📊 Inventory Level & Update Tracker")

    search_cat = st.text_input("🔍 Search Catalog Number").strip()
    filtered_cat_nos = sorted(df[df['cat_no.'].str.contains(search_cat, case=False, na=False)]['cat_no.'].unique())
    cat_selected = st.selectbox("Select Catalog Number", filtered_cat_nos)

    item_data = df[df['cat_no.'] == cat_selected].copy()
    item_name = item_data['item'].values[0]
    current_qty = item_data['quantity'].values[0]

    st.metric(label=f"{item_name} (Cat#: {cat_selected})", value=current_qty)

    new_qty = st.number_input("🔢 New Total Quantity", min_value=0, value=current_qty, step=1)

    if st.button("Update Quantity"):
        idx = item_data.index[0]
        df.at[idx, 'quantity'] = new_qty
        st.success(f"Updated quantity of {item_name} to {new_qty}")

    st.subheader("📷 Update Quantity with QR Scan")

    class QRProcessor(VideoProcessorBase):
        def __init__(self):
            self.last_code = None

        def recv(self, frame):
            img = frame.to_ndarray(format="bgr24")
            codes = decode(img)
            for code in codes:
                data = code.data.decode("utf-8")
                self.last_code = data
                cv2.rectangle(img, (code.rect.left, code.rect.top),
                              (code.rect.left + code.rect.width, code.rect.top + code.rect.height),
                              (0, 255, 0), 2)
                cv2.putText(img, data, (code.rect.left, code.rect.top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            return av.VideoFrame.from_ndarray(img, format="bgr24")

    ctx = webrtc_streamer(key="qr", mode=WebRtcMode.SENDRECV,
                          video_processor_factory=QRProcessor,
                          media_stream_constraints={"video": True, "audio": False},
                          async_processing=True)

    if ctx.video_processor:
        code = ctx.video_processor.last_code
        if code:
            st.success(f"QR Code Detected: {code}")
            if code in df['cat_no.'].values:
                idx = df[df['cat_no.'] == code].index[0]
                df.at[idx, 'quantity'] += 1
                st.success(f"Automatically increased quantity of {df.at[idx, 'item']} (Cat#: {code}) to {df.at[idx, 'quantity']}")
            else:
                st.error("Catalog number not found in inventory!")

# ------------------------
# 📦 Tab 2: Location
# ------------------------
with tab2:
    st.header("📦 Item Shelf & Location")
    location_df = df[['item', 'cat_no.', 'location', 'shelf']].sort_values(by='item')
    st.dataframe(location_df, use_container_width=True)

# ------------------------
# ⚠️ Tab 3: Reorder List
# ------------------------
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
            df.at[idx, 'ordered'] = ordered
            df.at[idx, 'order_date'] = order_date if ordered else pd.NaT

        st.subheader("📋 Current Reorder Status")
        st.dataframe(df[df['expiration'] < today][['item', 'cat_no.', 'quantity', 'expiration', 'ordered', 'order_date']], use_container_width=True)
    else:
        st.success("No expired items at the moment.")

# ------------------------
# 📝 Tab 4: Notes & Export
# ------------------------
with tab4:
    st.header("📝 Notes or Future Additions")
    st.markdown("- Consider adding automated reorder email.")
    st.markdown("- Add supplier info and unit cost.")

    st.subheader("📤 Export Current Inventory")
    to_download = df.copy()
    to_download['expiration'] = to_download['expiration'].dt.date  # format date nicely

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        to_download.to_excel(writer, index=False, sheet_name='Inventory')
        writer.save()
        st.download_button(label="📥 Download Excel Inventory",
                           data=excel_buffer.getvalue(),
                           file_name="MMCCCL_Inventory.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
