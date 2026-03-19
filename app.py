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

# --- IMPROVED UI STYLING (MODERN SAAS LOOK) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    .stApp { background-color: #FDFDFD; font-family: "Inter", sans-serif; }
    .block-container { padding-top: 2rem; }
    
    /* Global Card Style */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #F1F5F9;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    h1 { font-weight: 800 !important; color: #0F172A !important; letter-spacing: -1px; }
    h3 { font-weight: 700 !important; color: #334155 !important; margin-bottom: 1rem !important; }
    
    /* Tab Styling */
    button[data-baseweb="tab"] { font-size: 15px !important; font-weight: 600 !important; border-radius: 8px 8px 0 0 !important; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #F8FAFC !important; color: #10B981 !important; border-bottom: 3px solid #10B981 !important; }
    
    /* Input Styling */
    div[data-baseweb="input"], .stDateInput > div, .stTimeInput > div, .stMultiSelect > div {
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
    }
    
    /* Button Styling */
    .stButton > button {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        color: white !important;
        font-weight: 700;
        border: none;
        border-radius: 10px;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35); }
    
    /* Success/Error Alerts */
    .stAlert { border-radius: 12px !important; border: none !important; }
</style>
""", unsafe_allow_html=True)

# --- DATA LAYER ---
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

def load_data():
    client = get_connection()
    if not client: return pd.DataFrame()
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        expected_cols = ["Table", "Customer Name", "Phone Number", "Start", "End", "Status", "ID", "Notes", "Pax"]
        for col in expected_cols:
            if col not in df.columns: df[col] = ""
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End'] = pd.to_datetime(df['End'], errors='coerce')
            df['Pax'] = pd.to_numeric(df['Pax'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def check_availability(new_start, new_end, requested_tables, existing_df):
    if existing_df.empty: return True, []
    active = existing_df[existing_df['Status'] == 'Reserved'].copy()
    conflicts = []
    for _, row in active.iterrows():
        if (new_start < row['End']) and (new_end > row['Start']):
            row_tables = [t.strip() for t in str(row['Table']).split(',')]
            overlap_tables = set(requested_tables).intersection(set(row_tables))
            if overlap_tables:
                conflicts.append(f"{row['Customer Name']} ({', '.join(overlap_tables)})")
    return (len(conflicts) == 0), conflicts

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

# --- MAIN APP ---
st.title("🍽️ Vert Reservation")
tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 SCHEDULE GRID"])

df_all = load_data()

with tab1:
    st.subheader("Booking Details")
    c_date, c_guest = st.columns([1, 1])
    with c_date:
        res_date = st.date_input("Select Date", min_value=datetime.now())
    
    if res_date.weekday() == 0:
        st.error("⛔ **STOP!** Monday selected. (Venue Closed)")

    search_options = []
    if not df_all.empty:
        temp_df = df_all[["Customer Name", "Phone Number"]].drop_duplicates()
        search_options = (temp_df["Customer Name"].astype(str) + " | " + temp_df["Phone Number"].astype(str)).tolist()
    
    with c_guest:
        guest_search = st.selectbox("Search Guest (Auto-fill)", ["+ Add New Guest"] + sorted(search_options))
    
    val_name, val_phone = (guest_search.split(" | ") if guest_search != "+ Add New Guest" else ("", ""))

    with st.form("res_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1: final_cust = st.text_input("Customer Name", value=val_name, placeholder="John Doe")
        with c2: final_phone = st.text_input("Phone Number", value=val_phone, placeholder="0812...")
        
        c3, c4, c5, c6 = st.columns(4)
        with c3: pax = st.number_input("Guests", min_value=1, value=2)
        with c4: res_time = st.time_input("Time", value=time(12, 0))
        with c5: duration = st.selectbox("Duration", [1, 2, 3, 4, 5], index=1, format_func=lambda x: f"{x} Hours")
        with c6: 
            table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
            tables = st.multiselect("Table(s)", table_list)
        
        notes = st.text_input("Notes", placeholder="Anniversary, allergy, etc.")
        submit = st.form_submit_button("✅ CONFIRM RESERVATION")
        
        if submit:
            start_dt = datetime.combine(res_date, res_time)
            end_dt = start_dt + timedelta(hours=duration)
            is_available, conflicts = check_availability(start_dt, end_dt, tables, df_all)
            
            if not (final_cust and final_phone and tables):
                st.error("Missing details. Please ensure Name, Phone, and Table are selected.")
            elif not is_available:
                st.error(f"⚠️ **TABLE CONFLICT!** {', '.join(conflicts)}")
            else:
                with st.spinner("Processing..."):
                    payload = {
                        "Table": tables, "Customer Name": final_cust, "Phone Number": final_phone,
                        "Start": start_dt, "End": end_dt,
                        "Status": "Reserved", "ID": str(uuid.uuid4())[:8], "Notes": notes, "Pax": pax
                    }
                    add_reservation(payload)
                    st.balloons() 
                    st.cache_resource.clear()
                    st.rerun()

with tab2:
    col_f1, _ = st.columns([1, 2])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="grid_view_final")

    df_day = df_all[df_all['Start'].dt.date == view_date].copy() if not df_all.empty else pd.DataFrame()
    
    # --- IMMEDIATE FILTERING FOR GANTT ---
    # Only show 'Reserved' status in the chart. Cancelled removed immediately.
    confirmed = df_day[df_day['Status'] == 'Reserved'] if not df_day.empty else pd.DataFrame()
    
    # --- METRICS BAR ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Reservations", len(confirmed))
    m2.metric("Total Pax", int(confirmed['Pax'].sum() if not confirmed.empty else 0))
    m3.metric("Capacity", f"{confirmed['Table'].str.split(', ').explode().nunique() if not confirmed.empty else 0}/10", delta="Tables")
    
    # --- GANTT CHART (CLEANER & FASTER) ---
    all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
    start_view = datetime.combine(view_date, time(10, 0))
    end_view = datetime.combine(view_date, time(23, 0))

    if not confirmed.empty:
        plot_df = confirmed.assign(Table=confirmed['Table'].str.split(', ')).explode('Table')
    else:
        plot_df = pd.DataFrame(columns=["Table", "Start", "End", "Customer Name", "Pax"])

    # Create invisible dummy records for all tables to ensure they always show on Y-axis
    skeleton = pd.DataFrame([{"Table": t, "Start": start_view, "End": start_view, "Status": "Hidden"} for t in all_tables])
    final_plot_df = pd.concat([plot_df, skeleton], ignore_index=True)

    fig = px.timeline(
        final_plot_df, 
        x_start="Start", x_end="End", y="Table",
        hover_data={"Table": True, "Customer Name": True, "Pax": True, "Start": "|%H:%M"},
        color_discrete_sequence=["#10B981"] # The "Vert" Green
    )
    
    fig.update_traces(
        marker_line_color='white', marker_line_width=2, opacity=0.9,
        hovertemplate="<b>%{y}</b><br>Guest: %{customdata[1]}<br>Pax: %{customdata[2]}<br>Time: %{start|%H:%M}"
    )

    fig.update_layout(
        xaxis_range=[start_view, end_view],
        xaxis=dict(tickformat="%H:%M", gridcolor="#F1F5F9", side="top", title="", dtick=3600000),
        yaxis=dict(categoryorder="array", categoryarray=all_tables[::-1], title="", gridcolor="#F1F5F9"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=450,
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- STATUS MANAGEMENT ---
    st.markdown("---")
    header_col, toggle_col = st.columns([2, 1])
    with header_col:
        st.subheader("Manage Bookings")
    with toggle_col:
        show_cancelled = st.toggle("Show Archive (Cancelled)", value=False)

    if not df_day.empty:
        df_display = df_day.copy() if show_cancelled else df_day[df_day['Status'] != 'Cancelled'].copy()

        if not df_display.empty:
            edited_df = st.data_editor(
                df_display[["Status", "Start", "Table", "Customer Name", "Pax", "ID"]].sort_values("Start"),
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=["Reserved", "Cancelled"], required=True),
                    "Start": st.column_config.DatetimeColumn("Arrival", format="HH:mm", disabled=True),
                    "ID": None 
                },
                hide_index=True, use_container_width=True, key="editor_v3"
            )

            if st.button("💾 APPLY CHANGES", use_container_width=True):
                changes = {}
                for _, row in edited_df.iterrows():
                    orig_status = df_day.loc[df_day['ID'] == row['ID'], 'Status'].values[0]
                    if row['Status'] != orig_status:
                        changes[row['ID']] = row['Status']
                
                if changes:
                    update_status_batch(changes)
                    st.toast("Database Updated!", icon="✅")
                    st.cache_resource.clear()
                    st.rerun()
        else:
            st.info("No active bookings for this date.")
