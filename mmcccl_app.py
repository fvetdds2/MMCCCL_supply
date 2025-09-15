# mmcccl_app.py
import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import smtplib, ssl
from email.message import EmailMessage

# =========================
# PAGE SETUP & STYLES
# =========================
st.set_page_config(page_title="MMCCCL Lab Supply Tracker", layout="wide")
st.markdown("""
    <style>
    .main-header { color:#0072b2; font-size:2rem; font-weight:700; margin:.25rem 0 .5rem 0; }
    .subtle { color:#666; font-size:.95rem; margin-bottom:.75rem; }
    .metric { font-size:1.5rem; font-weight:700; }
    .pill { display:inline-block; padding:.1rem .5rem; border-radius:999px; background:#eef1f4; margin-right:.25rem; }
    </style>
""", unsafe_allow_html=True)
st.image("mmcccl_logo.png", use_container_width=True)
st.markdown('<div class="main-header">MMCCCL Lab Supply Tracker</div>', unsafe_allow_html=True)
st.markdown('<div class="subtle">Add / edit / delete inventory, export to Excel, and send restock alerts via email.</div>', unsafe_allow_html=True)

# =========================
# EMAIL SETUP (READS FROM st.secrets)
# =========================
"""
Add this to your Streamlit secrets (ℹ️ Settings → Secrets):

[smtp]
host = "smtp.gmail.com"
port = 465
user = "your_gmail_username@gmail.com"
password = "your_app_password"   # Gmail App Password
from_email = "your_gmail_username@gmail.com"
use_ssl = true                   # true = SSL(465), false = STARTTLS(587)
"""

def send_email_alert(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    if "smtp" not in st.secrets:
        return (False, "Missing [smtp] secrets. Configure st.secrets to enable email.")
    smtp_cfg = st.secrets["smtp"]
    host = smtp_cfg.get("host")
    port = int(smtp_cfg.get("port", 0))
    user = smtp_cfg.get("user")
    password = smtp_cfg.get("password")
    from_email = smtp_cfg.get("from_email", user)
    use_ssl = bool(smtp_cfg.get("use_ssl", True))

    if not all([host, port, user, password, from_email]):
        return (False, "Incomplete SMTP settings in st.secrets['smtp'].")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    try:
        if use_ssl or port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(user, password)
                server.send_message(msg)
        return (True, "Email sent.")
    except Exception as e:
        return (False, f"Email failed: {e}")

# =========================
# ROBUST EXCEL BUILDER
# =========================
def build_excel_bytes(sheets: dict) -> bytes:
    """
    Build an Excel file from {sheet_name: DataFrame}.
    Always ensures at least one visible sheet; tries xlsxwriter,
    then falls back to openpyxl if needed.
    """
    output = io.BytesIO()

    # Try xlsxwriter first
    try:
        import xlsxwriter  # noqa: F401
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            wrote_any = False
            for name, df in (sheets or {}).items():
                if isinstance(df, pd.DataFrame):
                    df.to_excel(writer, sheet_name=(str(name) or "Sheet1")[:31], index=False)
                    wrote_any = True
            if not wrote_any:
                pd.DataFrame({"Info": ["No data available to export."]}).to_excel(
                    writer, sheet_name="Info", index=False
                )
        return output.getvalue()
    except Exception:
        pass

    # Fallback: openpyxl manual workbook
    try:
        from openpyxl import Workbook
        from openpyxl.utils.dataframe import dataframe_to_rows
        wb = Workbook()
        ws = wb.active
        ws.title = "Info"
        wrote_any = False
        for name, df in (sheets or {}).items():
            if not isinstance(df, pd.DataFrame):
                continue
            ws2 = wb.create_sheet(title=(str(name) or "Sheet1")[:31])
            if df.shape[1] == 0:
                ws2.append(["No columns in DataFrame"])
            else:
                for r in dataframe_to_rows(df, index=False, header=True):
                    ws2.append(r)
            wrote_any = True
        if wrote_any:
            wb.remove(ws)  # drop Info if real data exists
        else:
            ws.append(["No data available to export."])
        wb.active = 0
        wb.save(output)
        return output.getvalue()
    except Exception as e:
        return f"Could not build Excel file. Error: {e}".encode("utf-8")

# =========================
# DATA LOADING & CLEANING
# =========================
DEFAULT_COLS = [
    "item", "cat_no.", "quantity", "minimum_stock_level",
    "order_unit", "location", "shelf", "lot #", "expiration"
]

@st.cache_data
def load_data():
    try:
        df = pd.read_excel("MMCCCL_supply_july.xlsx", engine="openpyxl")
    except FileNotFoundError:
        df = pd.DataFrame(columns=DEFAULT_COLS)

    # Ensure all columns exist
    for c in DEFAULT_COLS:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")

    # Types
    df["item"] = df["item"].astype(str).fillna("")
    df["cat_no."] = df["cat_no."].astype(str).fillna("")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["minimum_stock_level"] = pd.to_numeric(df["minimum_stock_level"], errors="coerce").fillna(0).astype(int)
    df["order_unit"] = df["order_unit"].astype(str).fillna("")
    df["location"] = df["location"].astype(str).fillna("")
    df["shelf"] = df["shelf"].astype(str).fillna("")
    df["lot #"] = df["lot #"].astype(str).fillna("")
    df["expiration"] = pd.to_datetime(df["expiration"], errors="coerce")
    return df[DEFAULT_COLS].copy()

def clean_inventory_df(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce user-edited DF to correct schema/types, drop empty rows."""
    if df is None or df.empty:
        return pd.DataFrame(columns=DEFAULT_COLS)

    out = df.copy()
    for c in DEFAULT_COLS:
        if c not in out.columns:
            out[c] = pd.NA

    out["item"] = out["item"].astype(str).fillna("")
    out["cat_no."] = out["cat_no."].astype(str).fillna("")
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce").fillna(0).astype(int)
    out["minimum_stock_level"] = pd.to_numeric(out["minimum_stock_level"], errors="coerce").fillna(0).astype(int)
    out["order_unit"] = out["order_unit"].astype(str).fillna("")
    out["location"] = out["location"].astype(str).fillna("")
    out["shelf"] = out["shelf"].astype(str).fillna("")
    out["lot #"] = out["lot #"].astype(str).fillna("")
    out["expiration"] = pd.to_datetime(out["expiration"], errors="coerce")

    # drop fully empty rows (no item AND no cat_no.)
    out = out[~((out["item"] == "") & (out["cat_no."] == ""))].copy()
    return out[DEFAULT_COLS]

# Init session state
if "inventory" not in st.session_state:
    st.session_state.inventory = load_data()

# =========================
# TABS
# =========================
tab1, tab2 = st.tabs(["📦 Inventory Manager", "✉️ Alerts & Email"])

# =========================
# TAB 1 — Inventory Manager
# =========================
with tab1:
    st.subheader("Manage inventory (add / edit / delete)")
    st.caption("Tip: use the last blank row to add items. Use the row menu to delete.")

    edited_df = st.data_editor(
        st.session_state.inventory,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "item": st.column_config.TextColumn("Item", required=True, width="large"),
            "cat_no.": st.column_config.TextColumn("Catalog #", required=False),
            "quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1),
            "minimum_stock_level": st.column_config.NumberColumn("Min Stock", min_value=0, step=1),
            "order_unit": st.column_config.TextColumn("Order Unit"),
            "location": st.column_config.TextColumn("Location"),
            "shelf": st.column_config.TextColumn("Shelf"),
            "lot #": st.column_config.TextColumn("Lot #"),
            "expiration": st.column_config.DateColumn("Expiration (YYYY-MM-DD)", format="YYYY-MM-DD"),
        },
        key="inv_editor"
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("💾 Save changes", type="primary", use_container_width=True):
            st.session_state.inventory = clean_inventory_df(edited_df)
            st.success("Inventory saved.")

    with col_b:
        ts = datetime.now().strftime("%Y-%m-%d")
        bytes_xlsx = build_excel_bytes({"Inventory": st.session_state.inventory})
        st.download_button(
            "⬇️ Download updated Excel",
            data=bytes_xlsx,
            file_name=f"MMCCCL_inventory_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# =========================
# TAB 2 — Alerts & Email (NOW WITH ITEM + CAT NO. IN SUBJECT & BODY)
# =========================
with tab2:
    st.subheader("Restock / Expiry Alerts")

    inv = st.session_state.inventory.copy()
    today = pd.Timestamp(date.today())

    expired = inv[inv["expiration"].notna() & (inv["expiration"] < today)]
    low = inv[inv["quantity"] <= inv["minimum_stock_level"]]

    alerts = pd.concat([expired, low]).drop_duplicates().reset_index(drop=True)
    expired_count = expired.shape[0]
    low_count = low.shape[0]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"<div class='pill'>Expired: <span class='metric'>{expired_count}</span></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='pill'>At/Below Min: <span class='metric'>{low_count}</span></div>", unsafe_allow_html=True)

    if alerts.empty:
        st.success("🎉 No items are expired or at/below minimum stock.")
    else:
        st.markdown("#### Items requiring attention")
        st.dataframe(alerts, use_container_width=True, height=320)

        # --- Build SUBJECT & BODY that include item + cat no. ---
        item_cat_list = (
            alerts[["item", "cat_no."]]
            .astype(str)
            .fillna("")
            .apply(lambda r: f"{r['item']} (Cat#: {r['cat_no.']})", axis=1)
            .tolist()
        )

        if len(item_cat_list) == 1:
            subject = f"[MMCCCL Inventory] Needs attention: {item_cat_list[0]}"
        elif len(item_cat_list) <= 3:
            subject = "[MMCCCL Inventory] Needs attention: " + ", ".join(item_cat_list)
        else:
            subject = (
                f"[MMCCCL Inventory] {len(item_cat_list)} items need attention — "
                + ", ".join(item_cat_list[:3])
                + f", +{len(item_cat_list) - 3} more"
            )

        lines = [
            subject,
            "",
            f"Summary — expired: {expired_count}, at/below min: {low_count}",
            "",
            "Details:"
        ]
        for _, r in alerts.fillna("").iterrows():
            exp_str = r["expiration"].strftime("%Y-%m-%d") if pd.notna(r["expiration"]) else "-"
            lines.append(
                f"- {r['item']} (Cat#: {r['cat_no.']}) | Qty: {r['quantity']} | Min: {r['minimum_stock_level']} | Exp: {exp_str}"
            )
        body = "\n".join(lines)

        # To address (default)
        to_email = st.text_input("Send alert to:", value="ddsrisai@gmail.com", key="alert_to_email")
        st.text_area("Email body (preview)", value=body, height=220)

        send_col1, send_col2 = st.columns([1, 1])
        with send_col1:
            if st.button("✉️ Send restock/expiry email", type="primary", use_container_width=True):
                ok, msg = send_email_alert(to_email, subject, body)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        with send_col2:
            # Optional: download alerts as Excel
            bytes_alerts = build_excel_bytes({"Alerts": alerts})
            st.download_button(
                "⬇️ Download Alerts Excel",
                data=bytes_alerts,
                file_name=f"MMCCCL_alerts_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
