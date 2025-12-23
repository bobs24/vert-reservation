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

# --- CSS STYLING (Refined for Contrast) ---
# We rely on config.toml for base colors, but use this for specific component styling
st.markdown("""
    <style>
    /* Main container styling to create the 'Card' effect */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem;
    }
    
    /* Make the tabs look more solid */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #12784A;
        color: white;
    }
    
    /* Force high contrast on input labels */
    .stSelectbox label, .stTextInput label, .stDateInput label, .stTimeInput label, .stNumberInput label, .stTextArea label {
        color: #12784A !important;
        font-weight: bold;
    }
    
    /* Button Styling */
    div.stButton > button {
        background-color: #12784A;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #0e5e3a;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Toast Notification Styling */
    div[data-testid="stToast"] {
        background-color: #12784A;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. SECURE DATABASE CONNECTION ---
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

# --- 3. CRUD FUNCTIONS ---
def load_data():
    client = get_connection()
    if not client: return pd.DataFrame()
    
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        expected_cols = ["Table", "Customer Name", "Start", "End", "Status", "ID", "Notes", "Pax"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        
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
    id_list = sheet.col_values(6) 
    updates = []
    
    for row_id, new_status in changes_dict.items():
        try:
            row_num = id_list.index(row_id) + 1
            updates.append({
                'range': f'E{row_num}',
                'values': [[new_status]]
            })
        except ValueError:
            continue
            
    if updates:
        sheet.batch_update(updates)

# --- 4. UI LAYOUT ---

st.title("🍽️ Voila Reservation Manager")

tab1, tab2 = st.tabs(["📝 New Reservation", "📊 Dashboard"])

# ==========================================
# TAB 1: FORM
# ==========================================
with tab1:
    # Container for the form to give it a 'Paper' look
    with st.container():
        st.markdown("### Create New Booking")
        
        # Load customer data for autocomplete
        df_cached = load_data()
        previous_customers = sorted(df_cached["Customer Name"].dropna().unique().tolist()) if not df_cached.empty else []

        with st.form("res_form", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                res_date = st.date_input("Date", min_value=datetime.now())
                if res_date.weekday() == 0:
                    st.warning("⚠️ Note: Selected Date is a Monday.")
                
                res_time = st.time_input("Time", step=900)
                duration = st.selectbox("Duration", [1, 2, 3, 4, 5], index=1, format_func=lambda x: f"{x} Hours")
                
            with col2:
                cust_select = st.selectbox("Customer Search", [""] + previous_customers)
                cust_new = st.text_input("...or New Customer Name")
                final_cust = cust_new if cust_new else cust_select
                
                pax = st.number_input("Pax", min_value=1, max_value=50, step=1)
                
            st.markdown("---")
            col3, col4 = st.columns([1, 1])
            with col3:
                table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
                table = st.selectbox("Table Preference", table_list)
            with col4:
                occasion = st.text_input("Occasion (Optional)")

            notes = st.text_area("Notes / Special Requests")
            
            submitted = st.form_submit_button("Confirm Reservation", type="primary")

            if submitted:
                if not final_cust:
                    st.error("❌ Customer Name is required.")
                else:
                    with st.spinner("Syncing with Google Sheets..."):
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
                        st.toast(f"Reservation for {final_cust} Saved!", icon="✅")
                        st.cache_resource.clear()

# ==========================================
# TAB 2: DASHBOARD
# ==========================================
with tab2:
    st.markdown("### Daily Operations View")
    
    df = load_data()
    
    if df.empty:
        st.info("Database is empty.")
    else:
        # Filter Bar
        col_f1, col_f2 = st.columns([1, 5])
        with col_f1:
            view_date = st.date_input("Select Date", datetime.now(), key="view_date")
            
        mask = (df['Start'].dt.date == view_date)
        df_day = df.loc[mask].copy()
        
        if not df_day.empty:
            # GANTT CHART
            colors = {"Reserved": "#12784A", "Cancelled": "#D32F2F"}
            fig = px.timeline(
                df_day, 
                x_start="Start", x_end="End", y="Table",
                color="Status", color_discrete_map=colors,
                hover_data=["Customer Name", "Pax"],
                height=400,
                title=f"Schedule for {view_date.strftime('%d %b %Y')}"
            )
            fig.update_layout(
                xaxis_range=[
                    datetime.combine(view_date, time(10, 0)),
                    datetime.combine(view_date, time(23, 0))
                ],
                yaxis={'categoryorder':'array', 'categoryarray': [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]},
                plot_bgcolor="white",
                font=dict(size=14)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # DATA EDITOR
            st.divider()
            st.subheader("Edit Reservations")
            
            edit_cols = ["Status", "Table", "Customer Name", "Start", "End", "Pax", "ID"]
            
            edited_df = st.data_editor(
                df_day[edit_cols],
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=["Reserved", "Cancelled"], required=True, width="medium"),
                    "Start": st.column_config.DatetimeColumn("Start", format="HH:mm"),
                    "End": st.column_config.DatetimeColumn("End", format="HH:mm"),
                    "ID": st.column_config.TextColumn("ID", disabled=True),
                    "Table": st.column_config.TextColumn("Table", disabled=True),
                    "Customer Name": st.column_config.TextColumn("Customer", disabled=True),
                },
                hide_index=True,
                key="data_editor",
                use_container_width=True
            )

            if st.button("Save Changes to Database", type="primary"):
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
        else:
            st.info(f"No reservations found for {view_date.strftime('%d %b %Y')}")