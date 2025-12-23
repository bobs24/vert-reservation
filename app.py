import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.express as px
import uuid

# --- 1. PAGE CONFIGURATION & "ADVANCED" UI STYLING ---
st.set_page_config(
    page_title="Voila Reservation Manager", 
    layout="wide", 
    page_icon="🍽️",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Larger Fonts and Clean Look
st.markdown("""
    <style>
    /* GLOBAL FONT SIZE INCREASE */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Input Labels */
    .stSelectbox label, .stTextInput label, .stDateInput label, .stTimeInput label, .stNumberInput label, .stTextArea label {
        font-size: 1.2rem !important;
        color: #12784A !important;
        font-weight: 600 !important;
    }
    
    /* Input Text inside boxes */
    .stInput, .stSelectbox div[data-baseweb="select"] {
        font-size: 1.1rem;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        font-size: 1.2rem;
        padding: 15px 30px;
    }
    
    /* Buttons */
    button {
        font-size: 1.3rem !important;
        padding: 0.5rem 2rem !important;
    }
    
    /* Metrics at top of dashboard */
    div[data-testid="metric-container"] {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 5px solid #12784A;
    }
    
    /* Hide the default Streamlit header */
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets not found. Please configure Streamlit Secrets.")
            return None
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return None

SHEET_ID = '1tZ2uHxY--NeEoknNBQBeMFyuyOfTnmE4HIG6camwHsc'

# --- 3. DATA FUNCTIONS ---
def load_data():
    client = get_connection()
    if not client: return pd.DataFrame()
    
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Ensure standard columns exist
        expected_cols = ["Table", "Customer Name", "Start", "End", "Status", "ID", "Notes", "Pax"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        
        # Convert date strings to datetime objects
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End'] = pd.to_datetime(df['End'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        return pd.DataFrame()

def add_reservation(payload):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    if not sheet.row_values(1):
        sheet.append_row(["Table", "Customer Name", "Start", "End", "Status", "ID", "Notes", "Pax"])
    
    sheet.append_row([
        payload["Table"],
        payload["Customer Name"],
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
    id_list = sheet.col_values(6) # Assuming ID is 6th column
    updates = []
    
    for row_id, new_status in changes_dict.items():
        try:
            row_num = id_list.index(row_id) + 1
            updates.append({
                'range': f'E{row_num}', # Status is 5th column (E)
                'values': [[new_status]]
            })
        except ValueError:
            continue
    if updates:
        sheet.batch_update(updates)

# --- 4. MAIN UI ---
st.title("🍽️ Voila Reservation Manager")

tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 DASHBOARD & GANTT"])

# ==========================================
# TAB 1: BOOKING FORM
# ==========================================
with tab1:
    # Load customer data for autocomplete
    df_cached = load_data()
    previous_customers = sorted(df_cached["Customer Name"].dropna().unique().tolist()) if not df_cached.empty else []

    with st.container():
        # Using columns to create a "Card" layout centered on screen
        _, col_center, _ = st.columns([1, 8, 1])
        
        with col_center:
            with st.form("res_form", clear_on_submit=True):
                st.subheader("Guest Details")
                
                # DATE & MONDAY CHECK (Immediate)
                c_date, c_time = st.columns(2)
                with c_date:
                    res_date = st.date_input("Date", min_value=datetime.now())
                    # IMMEDIATE WARNING LOGIC
                    if res_date.weekday() == 0:
                        st.error("⚠️ WARNING: You selected a MONDAY. We are usually closed.")

                with c_time:
                    res_time = st.time_input("Time", value=time(12, 0), step=900)

                c_cust, c_pax = st.columns([3, 1])
                with c_cust:
                    cust_select = st.selectbox("Customer Search (Type to find)", [""] + previous_customers)
                    cust_new = st.text_input("...or Enter New Customer Name")
                    final_cust = cust_new if cust_new else cust_select
                with c_pax:
                    pax = st.number_input("Pax", min_value=1, max_value=50, value=2)

                st.subheader("Table & Preferences")
                c_tbl, c_dur = st.columns(2)
                with c_tbl:
                    # STRICT ORDER for Tables
                    table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
                    table = st.selectbox("Assign Table", table_list)
                with c_dur:
                    duration = st.selectbox("Duration", [1, 2, 3, 4, 5], index=1, format_func=lambda x: f"{x} Hours")

                occasion = st.text_input("Occasion (Birthday, Anniversary, etc.)")
                notes = st.text_area("Staff Notes / Special Requests")
                
                submitted = st.form_submit_button("✅ CONFIRM RESERVATION", type="primary")

                if submitted:
                    if not final_cust:
                        st.error("❌ Error: Customer Name is missing.")
                    else:
                        with st.spinner("Saving to database..."):
                            start_dt = datetime.combine(res_date, res_time)
                            end_dt = start_dt + timedelta(hours=duration)
                            
                            # Clean notes (No more '|' prefix)
                            final_notes = f"{occasion} - {notes}" if occasion else notes
                            
                            payload = {
                                "Table": table,
                                "Customer Name": final_cust,
                                "Start": start_dt,
                                "End": end_dt,
                                "Status": "Reserved",
                                "ID": str(uuid.uuid4())[:8],
                                "Notes": final_notes,
                                "Pax": pax
                            }
                            
                            add_reservation(payload)
                            st.toast(f"Booking saved for {final_cust}!", icon="🎉")
                            st.cache_resource.clear()

# ==========================================
# TAB 2: ADVANCED DASHBOARD
# ==========================================
with tab2:
    # 1. FILTER BAR
    col_f1, col_f2, col_f3 = st.columns([2, 5, 2])
    with col_f1:
        view_date = st.date_input("📅 Select Date to View", datetime.now(), key="view_date")
    
    # Refresh Data
    df = load_data()
    
    if df.empty:
        st.info("Database is empty.")
    else:
        # Filter for selected day
        mask = (df['Start'].dt.date == view_date)
        df_day = df.loc[mask].copy()

        # 2. TOP METRICS (Visual Summary)
        m1, m2, m3 = st.columns(3)
        total_res = len(df_day[df_day['Status'] == 'Reserved'])
        total_pax = df_day[df_day['Status'] == 'Reserved']['Pax'].sum()
        cancelled_count = len(df_day[df_day['Status'] == 'Cancelled'])

        m1.metric("Confirmed Bookings", total_res)
        m2.metric("Expected Guests (Pax)", int(total_pax))
        m3.metric("Cancellations", cancelled_count)

        st.divider()

        # 3. GANTT CHART (The Logic You Requested)
        st.subheader(f"Timeline: {view_date.strftime('%d %b %Y')}")
        
        # FILTER OUT CANCELLED for the Chart Only
        df_chart = df_day[df_day['Status'] != 'Cancelled']
        
        # Define ALL tables explicitly so they show up on Y-Axis even if empty
        ALL_TABLES = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
        
        if not df_chart.empty:
            colors = {"Reserved": "#12784A"} # Only Green needed as Cancelled is hidden
            
            fig = px.timeline(
                df_chart, 
                x_start="Start", x_end="End", y="Table",
                color="Status", 
                color_discrete_map=colors,
                hover_data=["Customer Name", "Pax", "Notes"],
                height=500, # Taller chart
                text="Customer Name" # Show name on the bar
            )
            
            # ADVANCED LAYOUT: Force Y-Axis to show all tables
            fig.update_layout(
                xaxis_range=[
                    datetime.combine(view_date, time(10, 0)),
                    datetime.combine(view_date, time(23, 0))
                ],
                yaxis={
                    'categoryorder':'array', 
                    'categoryarray': ALL_TABLES, # This forces the order
                    'title': "Tables",
                    'type': 'category' # Ensure it treats it as categories, not text
                },
                plot_bgcolor="white",
                font=dict(size=16), # Larger font for chart
                showlegend=False
            )
            # Make bars thicker
            fig.update_traces(width=0.6)
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No active reservations for this day (or all are cancelled).")

        # 4. MANAGER TABLE (Full Data including Cancelled)
        st.divider()
        st.subheader("📋 Reservation List (Edit Status)")
        
        edit_cols = ["Status", "Table", "Customer Name", "Start", "End", "Pax", "Notes", "ID"]
        
        if not df_day.empty:
            # Sort by time
            df_day = df_day.sort_values(by="Start")
            
            edited_df = st.data_editor(
                df_day[edit_cols],
                column_config={
                    "Status": st.column_config.SelectboxColumn(
                        "Status", 
                        options=["Reserved", "Cancelled"], 
                        required=True, 
                        width="medium"
                    ),
                    "Start": st.column_config.DatetimeColumn("Start", format="HH:mm"),
                    "End": st.column_config.DatetimeColumn("End", format="HH:mm"),
                    "ID": st.column_config.TextColumn("ID", disabled=True),
                    "Notes": st.column_config.TextColumn("Notes", width="large"),
                    "Table": st.column_config.TextColumn("Table", disabled=True),
                    "Customer Name": st.column_config.TextColumn("Customer", disabled=True),
                },
                hide_index=True,
                key="data_editor",
                use_container_width=True,
                num_rows="fixed"
            )

            # SAVE BUTTON
            if st.button("💾 SAVE STATUS CHANGES", type="primary"):
                changes = {}
                for index, row in edited_df.iterrows():
                    original = df.loc[df['ID'] == row['ID'], 'Status'].values[0]
                    if row['Status'] != original:
                        changes[row['ID']] = row['Status']
                
                if changes:
                    with st.spinner("Updating Database..."):
                        update_status_batch(changes)
                        st.toast("Database Updated Successfully!", icon="💾")
                        st.cache_resource.clear()
                        st.rerun()
                else:
                    st.info("No status changes detected.")