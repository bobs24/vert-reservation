import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.graph_objects as go
import uuid

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Voila Reservation Manager", 
    layout="wide", 
    page_icon="🍽️",
    initial_sidebar_state="collapsed"
)

# --- CSS STYLING ---
st.markdown("""
    <style>
    .stApp {background-color: #F8F9FA;}
    h1, h2, h3 {color: #12784A;}
    
    /* Make the Warning HUGE and RED */
    .stAlert {
        font-weight: bold;
        font-size: 1.2rem;
    }
    
    /* Style the Time Grid */
    .js-plotly-plot {
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Bigger Fonts */
    label { font-size: 1.1rem !important; color: #12784A !important; font-weight: bold !important; }
    button { font-size: 1.2rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets not found.")
            return None
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"DB Error: {e}")
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
        expected_cols = ["Table", "Customer Name", "Start", "End", "Status", "ID", "Notes", "Pax"]
        for col in expected_cols:
            if col not in df.columns: df[col] = None
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End'] = pd.to_datetime(df['End'], errors='coerce')
        return df
    except: return pd.DataFrame()

def add_reservation(payload):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    if not sheet.row_values(1):
        sheet.append_row(["Table", "Customer Name", "Start", "End", "Status", "ID", "Notes", "Pax"])
    sheet.append_row([
        payload["Table"], payload["Customer Name"], str(payload["Start"]), 
        str(payload["End"]), payload["Status"], payload["ID"], payload["Notes"], payload["Pax"]
    ])

def update_status_batch(changes_dict):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    id_list = sheet.col_values(6)
    updates = []
    for row_id, new_status in changes_dict.items():
        try:
            row_num = id_list.index(row_id) + 1
            updates.append({'range': f'E{row_num}', 'values': [[new_status]]})
        except: continue
    if updates: sheet.batch_update(updates)

# --- 4. MAIN UI ---
st.title("🍽️ Voila Reservation Manager")

tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 GRID SCHEDULE"])

# ==========================================
# TAB 1: BOOKING FORM
# ==========================================
with tab1:
    # --- LOGIC FIX: DATE PICKER OUTSIDE FORM ---
    # This ensures the warning happens INSTANTLY when you click the date
    col_date_picker, _ = st.columns([1, 2])
    with col_date_picker:
        res_date = st.date_input("📅 Select Reservation Date", min_value=datetime.now())
        
        # INSTANT WARNING
        if res_date.weekday() == 0:
            st.error("⛔ STOP! You selected a MONDAY. We are usually closed.")
        else:
            st.success(f"✅ Selected: {res_date.strftime('%A, %d %B %Y')}")

    # --- THE REST IS INSIDE THE FORM ---
    with st.form("res_form", clear_on_submit=True):
        st.divider()
        df_cached = load_data()
        prev_customers = sorted(df_cached["Customer Name"].dropna().unique().tolist()) if not df_cached.empty else []

        c1, c2 = st.columns(2)
        with c1:
            st.write("#### Guest Info")
            cust_select = st.selectbox("Search Customer", [""] + prev_customers)
            cust_new = st.text_input("Or New Customer Name")
            final_cust = cust_new if cust_new else cust_select
            pax = st.number_input("Pax", min_value=1, value=2)

        with c2:
            st.write("#### Preferences")
            res_time = st.time_input("Time", value=time(12, 0), step=900)
            duration = st.selectbox("Duration", [1, 2, 3, 4], index=1, format_func=lambda x: f"{x} Hours")
            table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
            table = st.selectbox("Table", table_list)

        notes = st.text_input("Notes (Occasion, Highchair, etc)")
        
        submitted = st.form_submit_button("✅ CONFIRM RESERVATION", type="primary")

        if submitted:
            if not final_cust:
                st.error("Name is required.")
            else:
                with st.spinner("Saving..."):
                    start_dt = datetime.combine(res_date, res_time)
                    end_dt = start_dt + timedelta(hours=duration)
                    payload = {
                        "Table": table, "Customer Name": final_cust,
                        "Start": start_dt, "End": end_dt, "Status": "Reserved",
                        "ID": str(uuid.uuid4())[:8], "Notes": notes, "Pax": pax
                    }
                    add_reservation(payload)
                    st.toast("Saved!", icon="🎉")
                    st.cache_resource.clear()

# ==========================================
# TAB 2: GRID VISUAL
# ==========================================
with tab2:
    # FILTER
    col_f1, col_f2 = st.columns([1, 4])
    with col_f1:
        view_date = st.date_input("Filter Date", datetime.now(), key="view_date")
    
    df = load_data()
    
    if df.empty:
        st.info("No Data.")
    else:
        # Filter Data & Exclude Cancelled
        mask = (df['Start'].dt.date == view_date) & (df['Status'] != 'Cancelled')
        df_day = df.loc[mask].copy()

        # --- GRID LOGIC ---
        # 1. Create Time Slots (Columns)
        # From 10:00 to 22:00 in 30 min chunks
        time_slots = []
        current_t = datetime.combine(view_date, time(10, 0))
        end_t = datetime.combine(view_date, time(22, 0))
        while current_t <= end_t:
            time_slots.append(current_t)
            current_t += timedelta(minutes=30)
            
        time_labels = [t.strftime('%H:%M') for t in time_slots]
        
        # 2. Create Tables (Rows)
        all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
        
        # 3. Build Heatmap Matrix (Z values) and Hover Text
        z_data = [] # Color Values (0=Empty, 1=Booked)
        text_data = [] # Text to show on hover
        
        for tbl in all_tables:
            row_z = []
            row_text = []
            for t_slot in time_slots:
                # Default: Empty
                is_booked = 0
                hover_txt = "Available"
                
                # Check if this slot overlaps with any reservation for this table
                # Overlap logic: (Start <= t_slot) AND (End > t_slot)
                res_match = df_day[
                    (df_day['Table'] == tbl) & 
                    (df_day['Start'] <= t_slot) & 
                    (df_day['End'] > t_slot)
                ]
                
                if not res_match.empty:
                    is_booked = 1
                    cust_name = res_match.iloc[0]['Customer Name']
                    pax_num = res_match.iloc[0]['Pax']
                    hover_txt = f"{cust_name} ({pax_num} Pax)"
                
                row_z.append(is_booked)
                row_text.append(hover_txt)
                
            z_data.append(row_z)
            text_data.append(row_text)

        # 4. PLOT HEATMAP (THE GRID)
        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=time_labels,
            y=all_tables,
            text=text_data,
            hoverinfo="text+y+x", # Show Custom text + Table + Time
            colorscale=[[0, '#F0F2F6'], [1, '#12784A']], # 0=Light Grey, 1=Green
            showscale=False, # Hide the color bar
            xgap=1, # Gap between cells
            ygap=1
        ))
        
        fig.update_layout(
            title=f"Schedule Grid: {view_date.strftime('%d %b %Y')}",
            height=500,
            xaxis_title="Time Slots",
            yaxis_autorange="reversed", # Table 1 at top
            plot_bgcolor="white"
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- MANAGER LIST ---
        st.divider()
        st.write("#### 📋 Management List")
        
        # Include Cancelled here so we can see them
        mask_all = (df['Start'].dt.date == view_date)
        df_all = df.loc[mask_all].copy().sort_values("Start")
        
        edited_df = st.data_editor(
            df_all[["Status", "Table", "Customer Name", "Start", "End", "Notes", "ID"]],
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Reserved", "Cancelled"], required=True),
                "Start": st.column_config.DatetimeColumn("Start", format="HH:mm"),
                "End": st.column_config.DatetimeColumn("End", format="HH:mm"),
                "ID": st.column_config.TextColumn("ID", disabled=True),
            },
            hide_index=True,
            use_container_width=True
        )

        if st.button("Save Changes"):
            changes = {}
            for i, row in edited_df.iterrows():
                orig = df.loc[df['ID'] == row['ID'], 'Status'].values[0]
                if row['Status'] != orig: changes[row['ID']] = row['Status']
            if changes:
                update_status_batch(changes)
                st.success("Updated!")
                st.cache_resource.clear()
                st.rerun()