import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.express as px
import uuid

# --- 1. CONFIG & SYSTEM SETUP ---
st.set_page_config(
    page_title="Vert Reservation Manager",
    layout="wide",
    page_icon="🍽️",
    initial_sidebar_state="collapsed"
)

# Implementation of your exact CSS protocol
st.markdown("""
<style>
    .stApp { background-color: #F8FAFC; font-family: "Inter", sans-serif; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { font-size: 34px !important; font-weight: 800 !important; color: #0F172A !important; }
    h2, h3 { font-weight: 700 !important; color: #1E293B !important; }

    /* Tabs styling */
    button[data-baseweb="tab"] { font-size: 16px !important; font-weight: 700 !important; color: #334155 !important; padding: 10px 18px !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #0F172A !important; border-bottom: 3px solid #FACC15 !important; }

    /* Input Box System */
    div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] > div,
    .stDateInput > div, .stTimeInput > div, .stNumberInput > div {
        background-color: #FFFFFF !important; border: 1px solid #CBD5E1 !important; border-radius: 8px !important; min-height: 42px;
    }
    
    /* Input Text Fixes */
    input, textarea { color: #000000 !important; font-size: 15px !important; font-weight: 500 !important; }
    div[data-baseweb="select"]:not([data-testid="stDataEditor"] *) * { color: #000000 !important; }

    /* Button Styling */
    .stButton > button {
        background-color: #FACC15 !important; color: #000 !important; font-weight: 700; border-radius: 8px; border: none; height: 44px; width: 100%; transition: 0.2s;
    }
    .stButton > button:hover { background-color: #EAB308 !important; transform: translateY(-1px); }

    /* Metrics */
    [data-testid="stMetricValue"] { color: #16A34A; font-weight: 800; font-size: 28px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE (SINGLE SOURCE OF TRUTH) ---
SHEET_ID = '1eUi8Neog9mXb5J17G3WTvCehtR0Bz3-mKkw49gG8tAE'

@st.cache_resource
def get_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Missing GCP Credentials in Secrets.")
        return None
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def load_clean_data():
    client = get_client()
    if not client: return pd.DataFrame()
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty: return df
        # Ensure strict typing for data quality
        df['Start'] = pd.to_datetime(df['Start'])
        df['End'] = pd.to_datetime(df['End'])
        df['Pax'] = pd.to_numeric(df['Pax']).fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame()

# --- 3. LOGIC MODULES ---
def check_conflicts(start_dt, end_dt, target_tables, df):
    if df.empty: return False, []
    # Only check active reservations
    active = df[df['Status'] == 'Reserved']
    conflicts = []
    
    for _, row in active.iterrows():
        # Time Overlap Logic: (StartA < EndB) and (EndA > StartB)
        if (start_dt < row['End']) and (end_dt > row['Start']):
            existing_tables = [t.strip() for t in str(row['Table']).split(',')]
            intersection = set(target_tables).intersection(set(existing_tables))
            if intersection:
                conflicts.append(f"{row['Customer Name']} ({', '.join(intersection)})")
    return (len(conflicts) > 0), conflicts

# --- 4. INTERFACE ---
st.title("🍽️ Vert Reservation Manager")
tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 SCHEDULE GRID"])
df_main = load_clean_data()

with tab1:
    st.subheader("Booking Details")
    # Quick search for returning guests
    search_list = []
    if not df_main.empty:
        search_list = (df_main['Customer Name'] + " | " + df_main['Phone Number']).unique().tolist()
    
    selected_guest = st.selectbox("Guest Search", ["New Guest"] + sorted(search_list))
    init_name = selected_guest.split(" | ")[0] if "|" in selected_guest else ""
    init_phone = selected_guest.split(" | ")[1] if "|" in selected_guest else ""

    with st.form("booking_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", value=init_name)
        phone = c2.text_input("Phone", value=init_phone)
        
        c3, c4, c5, c6 = st.columns(4)
        b_date = c3.date_input("Date", value=datetime.now())
        b_time = c4.time_input("Time", value=time(18, 0))
        b_pax = c5.number_input("Pax", min_value=1, step=1)
        b_dur = c6.selectbox("Duration", [1, 2, 3], format_func=lambda x: f"{x} hours")
        
        b_tables = st.multiselect("Select Table(s)", [f"Table {i}" for i in range(1, 9)] + ["VIP", "Outdoor"])
        b_notes = st.text_input("Notes")
        
        if st.form_submit_button("CREATE RESERVATION"):
            start_val = datetime.combine(b_date, b_time)
            end_val = start_val + timedelta(hours=b_dur)
            
            has_conflict, details = check_conflicts(start_val, end_val, b_tables, df_main)
            
            if not (name and phone and b_tables):
                st.warning("Missing required fields.")
            elif has_conflict:
                st.error(f"Overlap detected: {', '.join(details)}")
            else:
                client = get_client()
                sheet = client.open_by_key(SHEET_ID).sheet1
                new_row = [", ".join(b_tables), name, phone, str(start_val), str(end_val), "Reserved", str(uuid.uuid4())[:8], b_notes, b_pax]
                sheet.append_row(new_row, value_input_option="USER_ENTERED")
                st.success(f"Reserved {name} successfully!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    view_date = st.date_input("Filter Date", value=datetime.now())
    day_df = df_main[df_main['Start'].dt.date == view_date] if not df_main.empty else pd.DataFrame()
    
    # KPIs
    confirmed = day_df[day_df['Status'] == 'Reserved']
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Bookings", len(confirmed))
    k2.metric("Total Pax", int(confirmed['Pax'].sum()) if not confirmed.empty else 0)
    
    # Calculate utilization
    occ = (confirmed['Table'].str.split(', ').explode().nunique() / 10) * 100 if not confirmed.empty else 0
    k3.metric("Table Occupancy", f"{occ:.0f}%")

    # Gantt Visualization
    if not confirmed.empty:
        # Explode tables so one bar shows per table
        viz_df = confirmed.assign(Table=confirmed['Table'].str.split(', ')).explode('Table')
        
        # Consistent Color Logic
        viz_df['Color'] = viz_df['Table'].apply(lambda x: "#F59E0B" if "VIP" in x else ("#10B981" if "Outdoor" in x else "#3B82F6"))
        
        fig = px.timeline(viz_df, x_start="Start", x_end="End", y="Table", text="Customer Name", color="Color", color_discrete_map="identity")
        fig.update_layout(xaxis=dict(tickformat="%H:%M", side="top", title=""), yaxis=dict(title="", categoryorder="total ascending"), plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active reservations for this day.")

    # Status Editor
    st.markdown("---")
    st.subheader("Manage Status")
    if not day_df.empty:
        # We only allow editing the Status column
        edited_df = st.data_editor(
            day_df[['Status', 'Start', 'Customer Name', 'Table', 'ID']],
            column_config={
                "Status": st.column_config.SelectboxColumn(options=["Reserved", "Cancelled"]),
                "ID": None, # Hide ID
                "Start": st.column_config.DatetimeColumn(format="HH:mm", disabled=True)
            },
            hide_index=True, use_container_width=True
        )
        
        if st.button("SAVE CHANGES"):
            # Update Logic
            client = get_client()
            sheet = client.open_by_key(SHEET_ID).sheet1
            all_ids = sheet.col_values(7)
            
            updates = []
            for _, row in edited_df.iterrows():
                try:
                    row_idx = all_ids.index(row['ID']) + 1
                    updates.append({'range': f'F{row_idx}', 'values': [[row['Status']]]})
                except: continue
            
            if updates:
                sheet.batch_update(updates)
                st.cache_resource.clear()
                st.rerun()
