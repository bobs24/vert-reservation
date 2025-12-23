import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.express as px
import uuid

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Voila Reservation System", 
    layout="wide", 
    page_icon="🍽️",
    initial_sidebar_state="collapsed"
)

# Custom Theme (Green #12784A)
st.markdown("""
    <style>
    .stApp { background-color: #f4f4f4; }
    .main .block-container {
        background-color: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        max-width: 95%;
    }
    h1, h2, h3 { color: #12784A; }
    div[data-testid="stForm"] { border: 2px solid #12784A; border-radius: 10px; padding: 20px; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .stButton>button[kind="primary"] { background-color: #12784A; border-color: #12784A; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SECURE DATABASE CONNECTION ---
# We use @st.cache_resource to keep the connection open (faster)
@st.cache_resource
def get_connection():
    try:
        # Looks for credentials in Streamlit Secrets
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"🔥 Connection Error: {e}")
        return None

# The ID of your Google Sheet
SHEET_ID = '1tZ2uHxY--NeEoknNBQBeMFyuyOfTnmE4HIG6camwHsc'

# --- 3. CRUD FUNCTIONS (Create, Read, Update) ---

def load_data():
    """Fetches data from Google Sheets."""
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
        
        # Convert date strings to datetime objects for calculations
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End'] = pd.to_datetime(df['End'], errors='coerce')
            
        return df
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        return pd.DataFrame()

def add_reservation(payload):
    """Writes a new row to Google Sheets."""
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    # Check if header exists, if not create it (safety check)
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
    """
    Updates specific cells in Google Sheets.
    changes_dict = {'ID_123': 'Cancelled', 'ID_456': 'Reserved'}
    """
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    # Get all IDs from the sheet (Column F is index 6)
    # Note: gspread is 1-indexed. If ID is the 6th column:
    id_list = sheet.col_values(6) 
    
    updates = []
    
    for row_id, new_status in changes_dict.items():
        try:
            # Find the row number (add 1 because list is 0-indexed but sheet is 1-indexed)
            row_num = id_list.index(row_id) + 1
            # Status is in Column E (5th column)
            updates.append({
                'range': f'E{row_num}',
                'values': [[new_status]]
            })
        except ValueError:
            continue # ID not found
            
    if updates:
        sheet.batch_update(updates)

# --- 4. UI LOGIC ---

tab1, tab2 = st.tabs(["📝 New Reservation", "📊 Dashboard Manager"])

# ==========================================
# TAB 1: RESERVATION FORM
# ==========================================
with tab1:
    st.header("New Reservation")
    
    # Load data once to get customer list
    df_cached = load_data()
    previous_customers = sorted(df_cached["Customer Name"].dropna().unique().tolist()) if not df_cached.empty else []

    with st.form("res_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            # Date with Monday Warning
            res_date = st.date_input("Date", min_value=datetime.now())
            if res_date.weekday() == 0:
                st.warning("⚠️ Selected Date is a Monday.")
        
        with c2:
            # Smart Autocomplete
            cust_select = st.selectbox("Customer (Select Existing)", [""] + previous_customers)
            cust_new = st.text_input("Or Type New Customer Name")
            final_cust = cust_new if cust_new else cust_select

        c3, c4, c5 = st.columns(3)
        with c3: res_time = st.time_input("Time", step=900)
        with c4: pax = st.number_input("Pax", min_value=1, max_value=50, step=1)
        with c5: duration = st.selectbox("Duration (Hours)", [1, 2, 3, 4, 5], index=1)

        c6, c7 = st.columns(2)
        with c6: 
            table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
            table = st.selectbox("Table", table_list)
        with c7: occasion = st.text_input("Occasion")

        notes = st.text_area("Special Requests / Notes")
        
        submitted = st.form_submit_button("Confirm Reservation", type="primary")

        if submitted:
            if not final_cust:
                st.error("❌ Customer Name is required.")
            else:
                with st.spinner("Saving to Google Sheets..."):
                    start_dt = datetime.combine(res_date, res_time)
                    end_dt = start_dt + timedelta(hours=duration)
                    
                    payload = {
                        "Table": table,
                        "Customer Name": final_cust,
                        "Start": start_dt,
                        "End": end_dt,
                        "Status": "Reserved",
                        "ID": str(uuid.uuid4())[:8],
                        "Notes": f"{occasion} | {notes}",
                        "Pax": pax
                    }
                    
                    add_reservation(payload)
                    st.toast("✅ Reservation Saved Successfully!", icon="🎉")
                    # Force reload on next action
                    st.cache_resource.clear()

# ==========================================
# TAB 2: DASHBOARD
# ==========================================
with tab2:
    st.header("Daily Operations")
    
    # Always fetch fresh data for the dashboard
    df = load_data()
    
    if df.empty:
        st.info("No reservations found in database.")
    else:
        # FILTER
        c_filter, _ = st.columns([1, 4])
        with c_filter:
            view_date = st.date_input("Filter Date", datetime.now())
            
        # Filter Logic
        mask = (df['Start'].dt.date == view_date)
        df_day = df.loc[mask].copy()
        
        # 1. GANTT CHART
        if not df_day.empty:
            st.subheader(f"Timeline: {view_date.strftime('%d %b %Y')}")
            
            # Colors: Green for Reserved, Red for Cancelled
            colors = {"Reserved": "#12784A", "Cancelled": "#D32F2F"}
            
            fig = px.timeline(
                df_day, 
                x_start="Start", x_end="End", y="Table",
                color="Status", color_discrete_map=colors,
                hover_data=["Customer Name", "Pax", "Notes"],
                height=350
            )
            
            # Set fixed business hours view (10 AM to 11 PM)
            fig.update_layout(
                xaxis_range=[
                    datetime.combine(view_date, time(10, 0)),
                    datetime.combine(view_date, time(23, 0))
                ],
                yaxis={'categoryorder':'array', 'categoryarray': [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]}
            )
            st.plotly_chart(fig, use_container_width=True)

        # 2. MANAGER TABLE (EDIT STATUS)
        st.subheader("Manage Reservations")
        st.caption("Change status below and click 'Save Changes' to update Google Sheets.")

        # Show relevant columns
        edit_cols = ["Status", "Table", "Customer Name", "Start", "End", "Pax", "ID"]
        
        if not df_day.empty:
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
                    "ID": st.column_config.TextColumn("ID", disabled=True)
                },
                disabled=["Table", "Customer Name", "Start", "End", "Pax", "ID"],
                hide_index=True,
                key="data_editor"
            )

            if st.button("Save Changes to Database", type="primary"):
                changes = {}
                # Detect changes
                for index, row in edited_df.iterrows():
                    original_status = df.loc[df['ID'] == row['ID'], 'Status'].values[0]
                    if row['Status'] != original_status:
                        changes[row['ID']] = row['Status']
                
                if changes:
                    with st.spinner(f"Updating {len(changes)} reservation(s)..."):
                        update_status_batch(changes)
                        st.toast("✅ Database Updated!", icon="💾")
                        st.cache_resource.clear() # Clear cache
                        st.rerun() # Refresh page
                else:
                    st.info("No changes detected.")
        else:
            st.info(f"No reservations for {view_date.strftime('%d %b %Y')}")