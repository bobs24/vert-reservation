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
    col_f1, _ = st.columns([1, 4])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="view_date")

    df = load_data()
    mask = (df['Start'].dt.date == view_date) & (df['Status'] != 'Cancelled') if not df.empty else []
    df_plot = df.loc[mask].copy() if not df.empty else pd.DataFrame()

    start_view = datetime.combine(view_date, time(10, 0))
    end_view = datetime.combine(view_date, time(22, 0))
    all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]

    if not df_plot.empty:
        df_plot = df_plot.assign(Table=df_plot['Table'].str.split(', ')).explode('Table')

    dummy_df = pd.DataFrame({"Table": all_tables, "Start": [start_view]*len(all_tables), "End": [start_view]*len(all_tables), "Customer Name": [""]*len(all_tables), "Pax": [None]*len(all_tables)})
    plot_df = pd.concat([dummy_df, df_plot], ignore_index=True)

    fig = px.timeline(
        plot_df, x_start="Start", x_end="End", y="Table", hover_name="Customer Name",
        hover_data={"Pax": True, "Start": "|%H:%M", "End": "|%H:%M", "Table": False},
        color_discrete_sequence=["#12784A"]
    )

    fig.update_layout(
        xaxis_range=[start_view, end_view],
        xaxis=dict(title="Time", tickformat="%H:%M", dtick=1800000, gridcolor="#EEEEEE"),
        yaxis=dict(title="", categoryorder="array", categoryarray=all_tables, gridcolor="#EEEEEE"),
        plot_bgcolor="white", paper_bgcolor="#F4F6F8", height=600, margin=dict(l=150, r=20, t=40, b=50)
    )

    fig.update_traces(marker_line_color="white", marker_line_width=2, opacity=0.9)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Status Reservation")

    if not df.empty:
        mask_all = (df['Start'].dt.date == view_date)
        df_all = df.loc[mask_all].copy().sort_values("Start")

        edited_df = st.data_editor(
            df_all[["Status", "Table", "Customer Name", "Phone Number", "Start", "End", "Notes", "ID"]],
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Reserved", "Cancelled"], required=True),
                "Start": st.column_config.DatetimeColumn("Start", format="HH:mm"),
                "End": st.column_config.DatetimeColumn("End", format="HH:mm"),
                "ID": st.column_config.TextColumn("ID", disabled=True),
            },
            hide_index=True, use_container_width=True
        )

        if st.button("💾 SAVE CHANGES"):
            changes = {}
            for i, row in edited_df.iterrows():
                orig = df.loc[df['ID'] == row['ID'], 'Status'].values[0]
                if row['Status'] != orig: changes[row['ID']] = row['Status']
            if changes:
                update_status_batch(changes)
                st.success("Database Updated!")
                st.cache_resource.clear()
                st.rerun()
