import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.graph_objects as go
import uuid
import plotly.express as px

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Vert Reservation Manager", 
    layout="wide", 
    page_icon="🍽️",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS OVERRIDES (VERT PREMIUM UI) ---
st.markdown("""
    <style>
    /* 1. GLOBAL BACKGROUND & BASE TEXT */
    .stApp {
        background-color: #F4F6F8 !important; /* Your light grey */
        color: #4A321F !important; /* Deepened your brown for legibility */
        font-family: 'Inter', sans-serif;
    }

    /* 2. CARD EFFECT FOR INPUTS */
    input, div[data-baseweb="base-input"], div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    /* 3. LABELS - VERT GREEN */
    .stMarkdown label, .stSelectbox label, .stTextInput label, .stDateInput label, .stTimeInput label, .stNumberInput label, .stMultiSelect label {
        color: #12784A !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        font-size: 0.8rem !important;
    }

    /* 4. TABS - MODERN & FLAT */
    button[data-baseweb="tab"] {
        color: #654321 !important; /* Your Brown */
        font-weight: 600 !important;
        border: none !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #12784A !important; /* Green instead of Blue */
        border-bottom: 3px solid #12784A !important;
        background-color: rgba(18, 120, 74, 0.05) !important;
    }

    /* 5. BUTTONS - SMOOTH & DARK GREY */
    .stButton > button {
        background-color: #374151 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        padding: 0.5rem 2rem !important;
        border: none !important;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #12784A !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* 6. METRIC CARDS STYLE */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px !important;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            return None
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"DB Connection Error: {e}")
        return None

SHEET_ID = '1eUi8Neog9mXb5J17G3WTvCehtR0Bz3-mKkw49gG8tAE'

# --- 4. DATA FUNCTIONS ---
def load_data():
    client = get_connection()
    if not client: return pd.DataFrame()
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        # UPDATED: Added Phone Number to expected columns
        expected_cols = ["Table", "Customer Name", "Phone Number", "Start", "End", "Status", "ID", "Notes", "Pax"]
        for col in expected_cols:
            if col not in df.columns: df[col] = ""
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End'] = pd.to_datetime(df['End'], errors='coerce')
        return df
    except: return pd.DataFrame()

def add_reservation(payload):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    if not sheet.row_values(1):
        # UPDATED: Added Phone Number
        sheet.append_row(["Table", "Customer Name", "Phone Number", "Start", "End", "Status", "ID", "Notes", "Pax"])

    table_str = ", ".join(payload["Table"])
    sheet.append_row([
        table_str, 
        payload["Customer Name"], 
        payload["Phone Number"], # NEW COLUMN
        str(payload["Start"]), 
        str(payload["End"]), 
        payload["Status"], 
        payload["ID"], 
        payload["Notes"], 
        payload["Pax"]
    ])

def update_status_batch(changes_dict):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    id_list = sheet.col_values(7) # ID shifted to 7th column
    updates = []
    for row_id, new_status in changes_dict.items():
        try:
            row_num = id_list.index(row_id) + 1
            updates.append({'range': f'F{row_num}', 'values': [[new_status]]}) # Status shifted to F
        except: continue
    if updates: sheet.batch_update(updates)

# --- 5. MAIN UI ---
st.title("🍽️ Vert Reservation Manager")

tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 SCHEDULE GRID"])

# ==========================================
# TAB 1: FORM (Clean Layout)
# ==========================================
with tab1:
    with st.container():
        st.subheader("📅 Date & Time")
        c_date, c_pad = st.columns([1, 3])
        with c_date:
            res_date = st.date_input("Select Date", min_value=datetime.now())
        if res_date.weekday() == 0:
            st.error("⛔ **STOP!** Monday selected. (Venue Closed)")

    st.markdown("---")

    # --- NEW LOGIC: Relationship Search ---
    df_cached = load_data()
    search_options = []
    if not df_cached.empty:
        # Create a searchable string "Name | Phone"
        temp_df = df_cached[["Customer Name", "Phone Number"]].drop_duplicates()
        search_options = (temp_df["Customer Name"].astype(str) + " | " + temp_df["Phone Number"].astype(str)).tolist()
    
    st.subheader("👤 Guest Information")
    # This acts as the "search-as-you-type" relationship field
    guest_search = st.selectbox("Search by Name or Phone (Suggests Existing)", ["+ Add New Guest"] + sorted(search_options))
    
    # Logic to pre-fill based on search
    val_name = ""
    val_phone = ""
    if guest_search != "+ Add New Guest":
        val_name, val_phone = guest_search.split(" | ")

    with st.form("res_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            final_cust = st.text_input("Customer Name", value=val_name)
        with c2:
            final_phone = st.text_input("Phone Number", value=val_phone)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("🍽️ Table Details")

        c3, c4, c5, c6 = st.columns(4)
        with c3:
            pax = st.number_input("Guests (Pax)", min_value=1, value=2)
        with c4:
            res_time = st.time_input("Time", value=time(12, 0), step=900)
        with c5:
            duration = st.selectbox("Duration", [1, 2, 3, 4], index=1, format_func=lambda x: f"{x} Hours")
        with c6:
            table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
            tables = st.multiselect("Assign Table(s)", table_list)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📝 Notes")
        notes = st.text_input("Special Requests (Birthday, Allergy, etc.)")

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("✅ CONFIRM RESERVATION")

        if submitted:
            if not final_cust or not final_phone:
                st.error("Please provide both Customer Name and Phone Number.")
            elif not tables:
                st.error("Please select at least one table.")
            else:
                with st.spinner("Processing..."):
                    start_dt = datetime.combine(res_date, res_time)
                    end_dt = start_dt + timedelta(hours=duration)
                    payload = {
                        "Table": tables,
                        "Customer Name": final_cust,
                        "Phone Number": final_phone,
                        "Start": start_dt, "End": end_dt, "Status": "Reserved",
                        "ID": str(uuid.uuid4())[:8], "Notes": notes, "Pax": pax
                    }
                    add_reservation(payload)
                    st.toast("Reservation Created!", icon="🎉")
                    st.cache_resource.clear()
                    st.rerun()

# ==========================================
# TAB 2: GRID VISUAL (Always Visible)
# ==========================================
with tab2:
    # --- 1. Top Controls & Metrics ---
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="view_grid_date")

    df = load_data()
    df_day = df[df['Start'].dt.date == view_date].copy() if not df.empty else pd.DataFrame()
    
    # Simple Metrics
    confirmed = df_day[df_day['Status'] == 'Reserved'] if not df_day.empty else pd.DataFrame()
    with col_f2:
        st.metric("Total Bookings", len(confirmed))
    with col_f3:
        st.metric("Total Guests", int(confirmed['Pax'].sum()) if not confirmed.empty else 0)

    # --- 2. The Perpetual Grid Logic ---
    start_view = datetime.combine(view_date, time(10, 0))
    end_view = datetime.combine(view_date, time(23, 0))
    all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]

    # Build Skeleton: This ensures every table shows up even if empty
    skeleton_data = []
    for t in all_tables:
        skeleton_data.append({
            "Table": t, "Start": start_view, "End": start_view, 
            "Customer Name": "", "IsDummy": True
        })
    skeleton_df = pd.DataFrame(skeleton_data)

    # Process Actual Data
    plot_df = confirmed.copy() if not confirmed.empty else pd.DataFrame()
    if not plot_df.empty:
        plot_df = plot_df.assign(Table=plot_df['Table'].str.split(', ')).explode('Table')
        plot_df['IsDummy'] = False
        # Combine skeleton and actual data
        final_plot_df = pd.concat([skeleton_df, plot_df], ignore_index=True)
    else:
        final_plot_df = skeleton_df

    # Create Figure
    fig = px.timeline(
        final_plot_df, 
        x_start="Start", x_end="End", y="Table", 
        hover_name="Customer Name",
        # Use opacity to hide the skeleton "dots"
        color="IsDummy",
        color_discrete_map={True: "rgba(0,0,0,0)", False: "#12784A"}
    )

    fig.update_layout(
        xaxis_range=[start_view, end_view],
        xaxis=dict(
            tickformat="%H:%M", dtick=3600000, 
            gridcolor="#F0F0F0", side="top", title="",
            fixedrange=True
        ),
        yaxis=dict(
            categoryorder="array", categoryarray=all_tables[::-1], 
            gridcolor="#F0F0F0", title="",
            fixedrange=True
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=500,
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False
    )
    
    fig.update_traces(marker_line_width=0, selector=dict(name="True")) # Hide skeleton lines
    fig.update_traces(marker_line_color="white", marker_line_width=2, marker_cornerradius=5, selector=dict(name="False"))

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- 3. Status Management ---
    st.markdown("---")
    st.subheader("📋 Booking Details")

    if not df_day.empty:
        edited_df = st.data_editor(
            df_day[["Status", "Start", "Table", "Customer Name", "Pax", "ID"]].sort_values("Start"),
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Reserved", "Cancelled"], required=True),
                "Start": st.column_config.DatetimeColumn("Time", format="HH:mm"),
                "ID": None # Keeps ID hidden from user but available for logic
            },
            hide_index=True,
            use_container_width=True,
            key="grid_editor_v3"
        )

        if st.button("💾 SAVE CHANGES"):
            changes = {row['ID']: row['Status'] for _, row in edited_df.iterrows() 
                       if row['Status'] != df_day.loc[df_day['ID'] == row['ID'], 'Status'].values[0]}
            if changes:
                update_status_batch(changes)
                st.success("Updated successfully!")
                st.cache_resource.clear()
                st.rerun()
    else:
        st.info("No activity for this date. The grid above is open for bookings.")

