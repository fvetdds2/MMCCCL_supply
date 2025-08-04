import streamlit as st
import pandas as pd
import numpy as np
import cv2
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, WebRtcMode
import av
import json
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
    st.subheader("📦 Add Inventory Items")

    # Mode selection
    mode = st.radio("Choose Input Method:", ["Manual Entry", "QR Code Scanner"])

    if mode == "Manual Entry":
        with st.form("manual_entry_form"):
            cat_no = st.text_input("Catalog Number")
            item_name = st.text_input("Item Name")
            quantity = st.number_input("Quantity", step=1, min_value=1)
            location = st.text_input("Location")
            expiration = st.date_input("Expiration Date")

            submit = st.form_submit_button("Add to Inventory")
            if submit:
                new_entry = {
                    "timestamp": datetime.now(),
                    "cat_no.": cat_no,
                    "item_name": item_name,
                    "quantity": quantity,
                    "location": location,
                    "expiration": expiration
                }
                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                st.success("Item added successfully!")

    else:
        st.info("Align a QR code with camera. It must contain JSON like: "
                "`{\"cat_no\": \"ABC123\", \"item_name\": \"Buffer\", \"quantity\": 10, \"location\": \"Shelf A\", \"expiration\": \"2025-10-10\"}`")

        scanned_data = st.empty()

        class VideoProcessor(VideoProcessorBase):
            def __init__(self):
                self.qr_data = None

            def recv(self, frame):
                img = frame.to_ndarray(format="bgr24")
                qr = cv2.QRCodeDetector()
                data, bbox, _ = qr.detectAndDecode(img)

                if bbox is not None:
                    bbox = bbox.astype(int)
                    for i in range(len(bbox[0])):
                        pt1 = tuple(bbox[0][i])
                        pt2 = tuple(bbox[0][(i+1) % len(bbox[0])])
                        cv2.line(img, pt1, pt2, (0, 255, 0), 2)

                    if data:
                        self.qr_data = data
                        cv2.putText(img, f"Scanned: {data[:30]}", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

                return av.VideoFrame.from_ndarray(img, format="bgr24")

        ctx = webrtc_streamer(
            key="qr-scanner",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=VideoProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

        if ctx.video_processor and ctx.video_processor.qr_data:
            try:
                parsed = json.loads(ctx.video_processor.qr_data)
                parsed["timestamp"] = datetime.now()
                parsed["expiration"] = pd.to_datetime(parsed.get("expiration"), errors='coerce')

                df = pd.concat([df, pd.DataFrame([parsed])], ignore_index=True)
                scanned_data.success(f"Item added: {parsed.get('item_name')}")

                # Reset the QR data so it doesn't keep adding
                ctx.video_processor.qr_data = None

            except Exception as e:
                scanned_data.error(f"Invalid QR data: {e}")

# ---- Tab 2: Item Locations ----
with tab2:
    st.subheader("📦 Item Locations")
    if not df.empty:
        st.dataframe(df[['item', 'cat_no.', 'location', 'shelf']].sort_values('item'), use_container_width=True)

# ---- Tab 3: Expiring Items ----
# ---- Tab 3 ----
with tab3:
    st.subheader("⚠️ Items Needing Reorder (Expired)")
    today = datetime.now()

    df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')  # Ensure datetime
    expired = df[df['expiration'].notna() & (df['expiration'] < today)]

    if expired.empty:
        st.success("🎉 No expired items!")
    else:
        st.warning("Some items are expired:")
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
        st.dataframe(expired[['item', 'cat_no.', 'quantity', 'expiration', 'ordered', 'order_date']], use_container_width=True)

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