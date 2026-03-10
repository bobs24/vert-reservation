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

# --- 2. CSS OVERRIDES (FORCE CONTRAST & FULL WIDTH) ---
st.markdown("""
    <style>
    /* 1. FORCE BACKGROUND & TEXT CONTRAST */
    .stApp {
        background-color: #F4F6F8 !important;
    }

    /* Target every possible text element to be Dark Brown */
    .stApp, .stApp p, .stApp div, .stApp span, .stApp label {
        color: #4A321F !important; 
    }

    /* 2. FIX INPUT BOXES (ENLARGE & FILL) */
    div[data-baseweb="input"], div[data-baseweb="select"], .stTextInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #D1D5DB !important;
        width: 100% !important; /* Forces box to fill the column */
        border-radius: 4px !important;
    }

    /* 3. LABELS - VERT GREEN */
    .stMarkdown label, [data-testid="stWidgetLabel"] p {
        color: #12784A !important;
        font-weight: 800 !important;
        font-size: 0.9rem !important;
    }

    /* 4. BUTTONS - LARGE & VISIBLE */
    .stButton > button {
        width: 100% !important;
        background-color: #4A321F !important;
        color: #FFFFFF !important;
        border-radius: 5px !important;
        border: none !important;
        height: 3rem !important;
    }

    /* 5. TAB STYLING */
    button[data-baseweb="tab"] p {
        color: #4A321F !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        border-bottom-color: #12784A !important;
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

with tab2:
    # --- Top Bar ---
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="v_date_final_fix")

    df = load_data()
    df_day = df[df['Start'].dt.date == view_date].copy() if not df.empty else pd.DataFrame()
    confirmed = df_day[df_day['Status'] == 'Reserved'] if not df_day.empty else pd.DataFrame()

    # --- Permanent Gantt Chart ---
    start_view = datetime.combine(view_date, time(10, 0))
    end_view = datetime.combine(view_date, time(23, 0))
    all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]

    # Skeleton Construction
    skeleton_df = pd.DataFrame([{"Table": t, "Start": start_view, "End": start_view, "IsDummy": True, "Customer Name": ""} for t in all_tables])

    if not confirmed.empty:
        plot_df = confirmed.copy()
        plot_df = plot_df.assign(Table=plot_df['Table'].str.split(', ')).explode('Table')
        plot_df['IsDummy'] = False
        final_plot_df = pd.concat([skeleton_df, plot_df], ignore_index=True)
    else:
        final_plot_df = skeleton_df

    # Create Figure with STRICT hover removal
    fig = px.timeline(
        final_plot_df, 
        x_start="Start", x_end="End", y="Table", 
        hover_name="Customer Name",
        color="IsDummy",
        color_discrete_map={True: "rgba(0,0,0,0)", False: "#12784A"}
    )

    # REMOVE IS_DUMMY FROM HOVER COMPLETELY
    fig.update_traces(
        hovertemplate="<b>%{hovertext}</b><br>Time: %{base|%H:%M} - %{x|%H:%M}<extra></extra>",
        selector=dict(name="False") # Only show hover for actual bookings
    )
    fig.update_traces(hoverinfo='none', selector=dict(name="True")) # Disable hover for skeleton

    fig.update_layout(
        xaxis_range=[start_view, end_view],
        xaxis=dict(
            tickformat="%H:%M", dtick=3600000, 
            gridcolor="#D1D5DB", side="top", title="", 
            tickfont=dict(color="#4A321F", size=12) 
        ),
        yaxis=dict(
            categoryorder="array", categoryarray=all_tables[::-1], 
            gridcolor="#D1D5DB", title="", 
            tickfont=dict(color="#4A321F", size=12) 
        ),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        height=500,
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False,
        font=dict(color="#4A321F") # Force chart text to Dark Brown
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- Management Editor ---
    st.markdown("### 📋 Status Management")
    if not df_day.empty:
        st.data_editor(
            df_day[["Status", "Start", "Table", "Customer Name", "Pax", "ID"]].sort_values("Start"),
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Reserved", "Cancelled"]),
                "Start": st.column_config.DatetimeColumn("Time", format="HH:mm"),
                "ID": None
            },
            hide_index=True, use_container_width=True, key="editor_fix_final"
        )


