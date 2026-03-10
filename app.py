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

# --- 2. CSS OVERRIDES (FORCE UNIFORMITY) ---
st.markdown("""
    <style>
    /* 1. GLOBAL BACKGROUND & TEXT */
    .stApp {
        background-color: #F4F6F8; /* Light Grey Background */
        color: #654321; /* Dark Brown Text */
        font-family: 'Inter', sans-serif;
    }

    /* 2. FORCE ALL INPUTS TO BE WHITE WITH BLACK TEXT */
    input {
        background-color: #FFFFFF !important;
        color: #000000 !important; 
    }
    
    div[data-baseweb="select"] > div, 
    div[data-baseweb="base-input"], 
    div[data-baseweb="input"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border-color: #E0E0E0 !important;
    }
    
    div[data-baseweb="select"] span {
        color: #000000 !important;
    }
    
    div[data-baseweb="select"] svg {
        fill: #555555 !important;
    }

    /* 3. LABELS */
    .stMarkdown label, .stSelectbox label, .stTextInput label, .stDateInput label, .stTimeInput label, .stNumberInput label, .stMultiSelect label {
        color: #12784A !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
    }

    /* 4. BUTTONS */
    .stButton > button {
        background-color: #888888 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold;
    }
    
    /* 5. REMOVE WEIRD SPACING AT TOP */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
            
    /* 6. TAB STYLING */
    button[data-baseweb="tab"] {
        color: #000000 !important;
        font-weight: 600 !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #0000FF !important;
        border-bottom-color: #12784A !important; 
        background-color: transparent !important;
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
# TAB 2: GRID VISUAL
# ==========================================
with tab2:
    # 1. Top Bar: Date Picker & Quick Stats
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1, 1, 1])
    
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="view_date")

    # Load and filter data
    df = load_data()
    mask_day = (df['Start'].dt.date == view_date) if not df.empty else pd.Series()
    df_day = df.loc[mask_day].copy() if not df.empty else pd.DataFrame()
    
    # Quick Stats (Metric Cards)
    active_res = len(df_day[df_day['Status'] == 'Reserved'])
    total_pax = df_day[df_day['Status'] == 'Reserved']['Pax'].sum()
    
    with col_f2:
        st.metric("Total Bookings", active_res)
    with col_f3:
        st.metric("Total Guests", int(total_pax) if total_pax else 0)
    with col_f4:
        st.metric("Status", "Open" if view_date.weekday() != 0 else "Closed")

    # 2. Timeline Grid Styling
    start_view = datetime.combine(view_date, time(10, 0))
    end_view = datetime.combine(view_date, time(23, 0)) # Extended to 11 PM
    all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]

    # Filter out cancelled for the visual grid only
    df_plot = df_day[df_day['Status'] != 'Cancelled'].copy() if not df_day.empty else pd.DataFrame()

    if not df_plot.empty:
        df_plot = df_plot.assign(Table=df_plot['Table'].str.split(', ')).explode('Table')

    # Create dummy data to ensure all tables show up even if empty
    dummy_df = pd.DataFrame({
        "Table": all_tables, 
        "Start": [start_view]*len(all_tables), 
        "End": [start_view]*len(all_tables), 
        "Customer Name": [""]*len(all_tables)
    })
    
    plot_df = pd.concat([dummy_df, df_plot], ignore_index=True)

    # Professional Plotly Theme
    fig = px.timeline(
        plot_df, 
        x_start="Start", 
        x_end="End", 
        y="Table", 
        hover_name="Customer Name",
        hover_data={"Pax": True, "Start": "|%H:%M", "End": "|%H:%M", "Table": False},
        color_discrete_sequence=["#12784A"] # Vert's Signature Green
    )

    fig.update_layout(
        xaxis_range=[start_view, end_view],
        xaxis=dict(
            title="", 
            tickformat="%H:%M", 
            dtick=3600000, # Hourly ticks
            gridcolor="#EBEBEB",
            side="top" # Move time to top for better readability
        ),
        yaxis=dict(
            title="", 
            categoryorder="array", 
            categoryarray=all_tables[::-1], # Reversed to show Table 1 at top
            gridcolor="#F0F0F0",
            fixedrange=True
        ),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        height=500,
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False,
        font=dict(family="Inter", size=12, color="#654321")
    )

    # Round the edges of the reservation bars
    fig.update_traces(
        marker_line_color="white", 
        marker_line_width=2, 
        opacity=0.85,
        marker=dict(cornerradius=5) # Smooth corners (Plotly 5.11+)
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # 3. Status Management Section
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 Booking Management")

    if not df_day.empty:
        # Sort by start time
        df_display = df_day.sort_values("Start")
        
        # Modern Data Editor
        edited_df = st.data_editor(
            df_display[["Status", "Start", "Table", "Customer Name", "Pax", "Phone Number", "Notes", "ID"]],
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status", 
                    options=["Reserved", "Cancelled"], 
                    required=True,
                    help="Update status to reflect walk-ins or cancellations"
                ),
                "Start": st.column_config.DatetimeColumn("Time", format="HH:mm"),
                "Table": st.column_config.TextColumn("Table", disabled=True),
                "Pax": st.column_config.NumberColumn("Pax", format="%d"),
                "ID": None, # Hide ID from UI but keep in dataframe
            },
            hide_index=True, 
            use_container_width=True,
            key="grid_editor"
        )

        c_save, c_empty = st.columns([1, 5])
        with c_save:
            if st.button("💾 SAVE CHANGES", use_container_width=True):
                changes = {}
                for i, row in edited_df.iterrows():
                    # Compare with original day data
                    orig_status = df_day.loc[df_day['ID'] == row['ID'], 'Status'].values[0]
                    if row['Status'] != orig_status:
                        changes[row['ID']] = row['Status']
                
                if changes:
                    with st.spinner("Updating..."):
                        update_status_batch(changes)
                        st.cache_resource.clear()
                        st.rerun()
                else:
                    st.info("No changes detected.")
    else:
        st.info("No reservations found for this date.")

