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

# --- 2. CSS OVERRIDES (STAYING AS IS) ---
st.markdown("""
    <style>
    .stApp { background-color: #F4F6F8; color: #654321; font-family: 'Inter', sans-serif; }
    input { background-color: #FFFFFF !important; color: #000000 !important; }
    div[data-baseweb="select"] > div, div[data-baseweb="base-input"], div[data-baseweb="input"] {
        background-color: #FFFFFF !important; color: #000000 !important; border-color: #E0E0E0 !important;
    }
    .stMarkdown label, .stSelectbox label, .stTextInput label, .stDateInput label, .stTimeInput label, .stNumberInput label, .stMultiSelect label {
        color: #12784A !important; font-weight: 700 !important; font-size: 1rem !important;
    }
    .stButton > button { background-color: #888888 !important; color: #FFFFFF !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets: return None
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
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
        # Added Phone Number to expected columns
        expected_cols = ["Table", "Customer Name", "Phone Number", "Start", "End", "Status", "ID", "Notes", "Pax"]
        for col in expected_cols:
            if col not in df.columns: df[col] = ""
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End'] = pd.to_datetime(df['End'], errors='coerce')
            df['Phone Number'] = df['Phone Number'].astype(str)
        return df
    except: return pd.DataFrame()

def add_reservation(payload):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    # Updated Header Row
    if not sheet.row_values(1):
        sheet.append_row(["Table", "Customer Name", "Phone Number", "Start", "End", "Status", "ID", "Notes", "Pax"])
    
    table_str = ", ".join(payload["Table"])
    sheet.append_row([
        table_str, payload["Customer Name"], payload["Phone Number"],
        str(payload["Start"]), str(payload["End"]), payload["Status"], 
        payload["ID"], payload["Notes"], payload["Pax"]
    ])

def update_status_batch(changes_dict):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    id_list = sheet.col_values(7) # ID is now column G (7th)
    updates = []
    for row_id, new_status in changes_dict.items():
        try:
            row_num = id_list.index(row_id) + 1
            updates.append({'range': f'F{row_num}', 'values': [[new_status]]}) # Status is F
        except: continue
    if updates: sheet.batch_update(updates)

# --- 5. MAIN UI ---
st.title("🍽️ Vert Reservation Manager")
tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 SCHEDULE GRID"])

with tab1:
    df_cached = load_data()
    
    # --- SMART SEARCH LOGIC ---
    st.subheader("🔍 Quick Search Existing Guest")
    col_search1, col_search2 = st.columns(2)
    
    selected_name = ""
    selected_phone = ""

    if not df_cached.empty:
        # Create a unique list of Customer-Phone pairs
        guest_list = df_cached[["Customer Name", "Phone Number"]].drop_duplicates()
        guest_list["Display"] = guest_list["Customer Name"] + " (" + guest_list["Phone Number"] + ")"
        
        with col_search1:
            search_choice = st.selectbox("Search by Name or Phone", ["-- New Guest --"] + guest_list["Display"].tolist())
            
        if search_choice != "-- New Guest --":
            match = guest_list[guest_list["Display"] == search_choice].iloc[0]
            selected_name = match["Customer Name"]
            selected_phone = match["Phone Number"]

    st.markdown("---")
    
    with st.form("res_form", clear_on_submit=True):
        st.subheader("👤 Guest Information")
        c1, c2 = st.columns(2)
        with c1:
            final_name = st.text_input("Customer Name", value=selected_name)
        with c2:
            final_phone = st.text_input("Phone Number", value=selected_phone)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📅 Date & Table Details")
        
        c_date, c_time, c_pax, c_dur = st.columns(4)
        with c_date:
            res_date = st.date_input("Date", min_value=datetime.now())
        with c_time:
            res_time = st.time_input("Time", value=time(12, 0), step=900)
        with c_pax:
            pax = st.number_input("Pax", min_value=1, value=2)
        with c_dur:
            duration = st.selectbox("Duration", [1, 2, 3, 4], index=1, format_func=lambda x: f"{x} Hours")

        table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
        tables = st.multiselect("Assign Table(s)", table_list)
        notes = st.text_input("Special Requests")

        submitted = st.form_submit_button("✅ CONFIRM RESERVATION")
        
        if submitted:
            if not final_name or not final_phone:
                st.error("Name and Phone Number are required.")
            elif not tables:
                st.error("Please select at least one table.")
            elif res_date.weekday() == 0:
                st.error("Venue is closed on Mondays.")
            else:
                with st.spinner("Processing..."):
                    start_dt = datetime.combine(res_date, res_time)
                    end_dt = start_dt + timedelta(hours=duration)
                    payload = {
                        "Table": tables, "Customer Name": final_name, "Phone Number": final_phone,
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
    view_date = st.date_input("📅 View Schedule For", datetime.now())
    df = load_data()
    
    if not df.empty:
        mask = (df['Start'].dt.date == view_date) & (df['Status'] != 'Cancelled')
        df_plot = df.loc[mask].copy()
        
        start_view = datetime.combine(view_date, time(10, 0))
        end_view = datetime.combine(view_date, time(22, 0))
        all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]

        if not df_plot.empty:
            df_plot = df_plot.assign(Table=df_plot['Table'].str.split(', ')).explode('Table')
            
            fig = px.timeline(
                df_plot, x_start="Start", x_end="End", y="Table",
                hover_name="Customer Name",
                hover_data={"Phone Number": True, "Pax": True, "Start": "|%H:%M", "End": "|%H:%M"},
                color_discrete_sequence=["#12784A"]
            )
            fig.update_layout(
                xaxis_range=[start_view, end_view],
                yaxis=dict(categoryorder="array", categoryarray=all_tables),
                height=500, plot_bgcolor="white"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Status Management")
        mask_all = (df['Start'].dt.date == view_date)
        df_all = df.loc[mask_all].copy().sort_values("Start")
        
        edited_df = st.data_editor(
            df_all[["Status", "Table", "Customer Name", "Phone Number", "Pax", "ID"]],
            column_config={"ID": st.column_config.TextColumn("ID", disabled=True)},
            hide_index=True, use_container_width=True
        )

        if st.button("💾 SAVE CHANGES"):
            changes = {row['ID']: row['Status'] for _, row in edited_df.iterrows() 
                       if row['Status'] != df.loc[df['ID'] == row['ID'], 'Status'].values[0]}
            if changes:
                update_status_batch(changes)
                st.success("Database Updated!")
                st.cache_resource.clear()
                st.rerun()
