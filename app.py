import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.graph_objects as go
import uuid
import plotly.express as px

st.set_page_config(
    page_title="Vert Reservation Manager", 
    layout="wide", 
    page_icon="🍽️",
    initial_sidebar_state="collapsed"
)

# --- IMPROVED UI STYLING ---
st.markdown("""
<style>

/* ---------- GLOBAL APP ---------- */

.stApp {
    background-color: #F8FAFC;
    font-family: "Inter", sans-serif;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}


/* ---------- HEADERS ---------- */

h1 {
    font-size: 34px !important;
    font-weight: 800 !important;
    color: #0F172A !important;
}

h2, h3 {
    font-weight: 700 !important;
    color: #1E293B !important;
}

/* ---------- TABS (NEW BOOKING / SCHEDULE GRID) ---------- */

button[data-baseweb="tab"] {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #334155 !important;
    padding: 10px 18px !important;
}

/* active tab */

button[data-baseweb="tab"][aria-selected="true"] {
    color: #0F172A !important;
    border-bottom: 3px solid #FACC15 !important;
}

/* hover */

button[data-baseweb="tab"]:hover {
    color: #000000 !important;
}

/* ---------- LABELS ---------- */

[data-testid="stWidgetLabel"] {
    background: none !important;
    border: none !important;
    padding: 0 !important;
    margin-bottom: 6px !important;
}

[data-testid="stWidgetLabel"] p {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #334155 !important;
}


/* ---------- INPUT BOX SYSTEM ---------- */

div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="select"] > div,
.stDateInput > div,
.stTimeInput > div,
.stNumberInput > div {

    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    min-height: 42px;
    transition: 0.2s border ease;
}

/* Focus state */

div[data-baseweb="input"]:focus-within,
div[data-baseweb="base-input"]:focus-within,
div[data-baseweb="select"] > div:focus-within,
.stDateInput > div:focus-within,
.stTimeInput > div:focus-within {
    border: 1px solid #FACC15 !important;
    box-shadow: 0 0 0 1px #FACC15;
}


/* ---------- INPUT TEXT COLOR FIX ---------- */

/* All text inputs */

input,
textarea {
    color: #000000 !important;
    font-size: 15px !important;
    font-weight: 500 !important;
}

/* Selectbox + Multiselect */

div[data-baseweb="select"]:not([data-testid="stDataEditor"] *) * {
    color: #000000 !important;
}

/* Dropdown list */

div[role="listbox"] div {
    color: #FFFFFF !important;
}

[data-testid="stDataEditor"] div[data-baseweb="select"] * {
    color: inherit !important;
}

/* Number input */

.stNumberInput input {
    color: #000000 !important;
}

/* Date / time input */

.stDateInput input,
.stTimeInput input {
    color: #000000 !important;
}

/* Placeholder text */

input::placeholder {
    color: #64748B !important;
}


/* ---------- MULTISELECT TAGS ---------- */

span[data-baseweb="tag"] {
    background-color: #FEF08A !important;
    color: #1E293B !important;
    border-radius: 6px !important;
}


/* ---------- BUTTON ---------- */

.stButton > button {

    background-color: #FACC15 !important;
    color: #000 !important;
    font-weight: 700;
    border-radius: 8px;
    border: none;
    height: 44px;
    transition: 0.2s;
}

.stButton > button:hover {

    background-color: #EAB308 !important;
    transform: translateY(-1px);

}


/* ---------- METRICS ---------- */

[data-testid="stMetricValue"] {

    color: #16A34A;
    font-weight: 800;
    font-size: 28px;

}

[data-testid="stMetricLabel"] {

    font-weight: 600;
    color: #475569;

}


/* ---------- DATA EDITOR FULL STYLE ---------- */

/* Main table container */

[data-testid="stDataEditor"] {
    border-radius: 10px;
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF !important;
}

/* Table cells */
[data-testid="stDataEditor"] td {
    background-color: #FFFFFF !important;
    color: #000000 !important;
    font-size: 14px !important;
}

/* Header row */
[data-testid="stDataEditor"] th {
    background-color: #F8FAFC !important;
    color: #334155 !important;
    font-weight: 700 !important;
}

/* FIX FOR DATA EDITOR DROPDOWN TEXT */
/* This ensures that when you click a cell to edit, the text is visible */
[data-testid="stDataEditor"] div[data-baseweb="select"] * {
    color: inherit !important; 
}

/* This targets the popup list specifically to ensure black text on the white menu */
[data-testid="stDataEditor"] div[role="listbox"] div {
    color: #000000 !important;
}


/* ---------- DIVIDERS ---------- */

hr {
    border-color: #E2E8F0;
}

</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets: return None
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"DB Connection Error: {e}")
        return None

SHEET_ID = '1eUi8Neog9mXb5J17G3WTvCehtR0Bz3-mKkw49gG8tAE'

def load_data():
    client = get_connection()
    if not client: return pd.DataFrame()
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End'] = pd.to_datetime(df['End'], errors='coerce')
        return df
    except: return pd.DataFrame()

def add_reservation(payload):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    table_str = ", ".join(payload["Table"])
    row_data = [
        table_str, payload["Customer Name"], payload["Phone Number"],
        payload["Start"].strftime("%Y-%m-%d %H:%M:%S"), 
        payload["End"].strftime("%Y-%m-%d %H:%M:%S"), 
        payload["Status"], payload["ID"], payload["Notes"], payload["Pax"]
    ]
    sheet.append_row(row_data, value_input_option='USER_ENTERED')

def update_status_batch(changes_dict):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    id_list = sheet.col_values(7)
    updates = []
    for row_id, new_status in changes_dict.items():
        try:
            row_num = id_list.index(row_id) + 1
            updates.append({'range': f'F{row_num}', 'values': [[new_status]]})
        except: continue
    if updates: sheet.batch_update(updates)

st.title("🍽️ Vert Reservation Manager")
tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 SCHEDULE GRID"])

# --- TAB 1: NEW BOOKING ---
with tab1:
    st.subheader("📅 Date & Time")
    c_date, _ = st.columns([1, 3])
    with c_date:
        res_date = st.date_input("Select Date", min_value=datetime.now())
    
    if res_date.weekday() == 0:
        st.error("⛔ **STOP!** Monday selected. (Venue Closed)")

    st.markdown("---")
    df_cached = load_data()
    search_options = []
    if not df_cached.empty:
        temp_df = df_cached[["Customer Name", "Phone Number"]].drop_duplicates()
        search_options = (temp_df["Customer Name"].astype(str) + " | " + temp_df["Phone Number"].astype(str)).tolist()
    
    st.subheader("👤 Guest Information")
    guest_search = st.selectbox("Search Guest", ["+ Add New Guest"] + sorted(search_options))
    val_name, val_phone = (guest_search.split(" | ") if guest_search != "+ Add New Guest" else ("", ""))

    with st.form("res_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1: final_cust = st.text_input("Customer Name", value=val_name)
        with c2: final_phone = st.text_input("Phone Number", value=val_phone)
        
        c3, c4, c5, c6 = st.columns(4)
        with c3: pax = st.number_input("Guests", min_value=1, value=2)
        with c4: res_time = st.time_input("Time", value=time(12, 0))
        with c5: duration = st.selectbox("Duration", [1, 2, 3], index=1, format_func=lambda x: f"{x} Hours")
        with c6: tables = st.multiselect("Table(s)", [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"])
        
        notes = st.text_input("Notes")
        if st.form_submit_button("✅ CONFIRM"):
            if final_cust and final_phone and tables:
                start_dt = datetime.combine(res_date, res_time)
                payload = {
                    "Table": tables, "Customer Name": final_cust, "Phone Number": final_phone,
                    "Start": start_dt, "End": start_dt + timedelta(hours=duration),
                    "Status": "Reserved", "ID": str(uuid.uuid4())[:8], "Notes": notes, "Pax": pax
                }
                add_reservation(payload)
                st.cache_resource.clear()
                st.rerun()

# --- TAB 2: SCHEDULE & STATUS ---
with tab2:
    col_f1, _ = st.columns([1, 2])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now())

    df = load_data()
    df_day = df[df['Start'].dt.date == view_date].copy() if not df.empty else pd.DataFrame()
    
    # ... (Plotly Chart Logic remains the same as your original) ...
    # Skipping the long Plotly code block for brevity, but keep yours there!

    # --- 📋 PROFESSIONAL STATUS MANAGEMENT ---
    st.markdown("---")
    header_col, toggle_col = st.columns([2, 1])
    with header_col:
        st.markdown("### 📋 Status Management")
        st.caption("Manage active bookings or archive cancellations.")
    with toggle_col:
        show_cancelled = st.toggle("Show Cancelled Bookings", value=False)

    if not df_day.empty:
        # Filter logic
        df_display = df_day.copy() if show_cancelled else df_day[df_day['Status'] != 'Cancelled'].copy()

        if not df_display.empty:
            edited_df = st.data_editor(
                df_display[["Status", "Start", "Table", "Customer Name", "Phone Number", "Pax", "Notes", "ID"]].sort_values("Start"),
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=["Reserved", "Cancelled"], required=True),
                    "Start": st.column_config.DatetimeColumn("Arrival", format="HH:mm", disabled=True),
                    "Customer Name": st.column_config.TextColumn("Guest", disabled=True),
                    "ID": None
                },
                hide_index=True, use_container_width=True, key="status_editor_v2"
            )

            if st.button("💾 COMMIT CHANGES", use_container_width=True):
                changes = {row['ID']: row['Status'] for _, row in edited_df.iterrows() 
                           if row['Status'] != df_day.loc[df_day['ID'] == row['ID'], 'Status'].values[0]}
                if changes:
                    update_status_batch(changes)
                    st.toast("Record updated!", icon="✅")
                    st.cache_resource.clear()
                    st.rerun()
        else:
            st.info("No active reservations to display.")
    else:
        st.info("No data for this date.")
