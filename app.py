import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.graph_objects as go
import uuid

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Voila Manager", 
    layout="wide", 
    page_icon="🍽️",
    initial_sidebar_state="collapsed"
)

# --- 2. ELEGANT CSS OVERRIDES (FIXED) ---
st.markdown("""
    <style>
    /* 1. FORCE LIGHT THEME BACKGROUND & DARK TEXT */
    .stApp {
        background-color: #F4F6F8;
        font-family: 'Inter', sans-serif;
        color: #333333 !important; /* Forces text to be dark even in Dark Mode */
    }
    
    /* Force Headers to be Dark */
    h1, h2, h3, h4, h5, h6, p, li, div {
        color: #333333 !important;
    }

    /* 2. CARD CONTAINER STYLE */
    .css-card {
        background-color: white;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border: 1px solid #E0E0E0;
        margin-bottom: 20px;
    }
    
    /* 3. INPUT FIELD STYLING (Force White Background / Dark Text) */
    .stTextInput input, 
    .stSelectbox div[data-baseweb="select"], 
    .stNumberInput input, 
    .stDateInput input, 
    .stTimeInput input, 
    .stMultiSelect div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        color: #333333 !important;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
    }
    
    /* Dropdown Options Styling (Fix for Dark Mode invisible text) */
    div[data-baseweb="popover"], div[data-baseweb="menu"] {
        background-color: #FFFFFF !important;
        color: #333333 !important;
    }
    
    /* Focus State (Green Border) */
    .stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within, .stMultiSelect div[data-baseweb="select"]:focus-within {
        border-color: #12784A !important;
        box-shadow: 0 0 0 1px #12784A !important;
    }

    /* 4. LABELS */
    .stSelectbox label, .stTextInput label, .stDateInput label, .stTimeInput label, .stNumberInput label, .stMultiSelect label {
        color: #12784A !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        margin-bottom: 5px !important;
    }
    
    /* 5. BUTTONS */
    .stButton > button {
        width: 100%;
        background-color: #12784A !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
        font-weight: 600 !important;
        border: none !important;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background-color: #0e5e3a !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(18, 120, 74, 0.2);
    }
    
    /* 6. TABS STYLING */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #555555 !important;
        font-weight: 600;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #12784A !important;
        border-bottom-color: #12784A !important;
    }

    /* 7. ALERTS */
    .stAlert {
        border-radius: 8px;
        border: none;
        color: #333333 !important; /* Ensure alert text is readable */
    }
    
    /* Hide Default Header */
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            # st.error("Secrets not found.") 
            return None
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"DB Connection Error: {e}")
        return None

SHEET_ID = '1tZ2uHxY--NeEoknNBQBeMFyuyOfTnmE4HIG6camwHsc'

# --- 4. DATA FUNCTIONS ---
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
    
    # Payload table is now a list like ['Table 1', 'Table 2']. Join them into a string.
    table_str = ", ".join(payload["Table"])
    
    sheet.append_row([
        table_str, 
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
            updates.append({'range': f'E{row_num}', 'values': [[new_status]]})
        except: continue
    if updates: sheet.batch_update(updates)

# --- 5. MAIN UI ---
st.title("🍽️ Voila Reservation Manager")

tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 SCHEDULE GRID"])

# ==========================================
# TAB 1: ELEGANT FORM
# ==========================================
with tab1:
    with st.container():
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        
        # --- 1. DATE PICKER & WARNING (Instant) ---
        c_date, c_pad = st.columns([1, 2])
        with c_date:
            res_date = st.date_input("Select Date", min_value=datetime.now())
            
        if res_date.weekday() == 0:
            st.error("⛔ **STOP!** Monday selected. (Venue Closed)")
        
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 2. THE FORM ---
    with st.form("res_form", clear_on_submit=True):
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        
        st.markdown("### 👤 Guest Information")
        
        df_cached = load_data()
        prev_customers = sorted(df_cached["Customer Name"].dropna().unique().tolist()) if not df_cached.empty else []

        c1, c2 = st.columns(2)
        with c1:
            cust_select = st.selectbox("Search Existing Customer", [""] + prev_customers)
        with c2:
            cust_new = st.text_input("Or Enter New Name")
        
        final_cust = cust_new if cust_new else cust_select
        
        st.markdown("---") 
        st.markdown("### 🍽️ Table Details")
        
        c3, c4, c5, c6 = st.columns(4)
        with c3:
            pax = st.number_input("Guests (Pax)", min_value=1, value=2)
        with c4:
            res_time = st.time_input("Time", value=time(12, 0), step=900)
        with c5:
            duration = st.selectbox("Duration", [1, 2, 3, 4], index=1, format_func=lambda x: f"{x} Hours")
        with c6:
            # CHANGED: Multi-select for multiple tables
            table_list = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
            tables = st.multiselect("Assign Table(s)", table_list)

        st.markdown("### 📝 Notes")
        notes = st.text_input("Special Requests (Birthday, Allergy, Highchair...)")
        
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("✅ CONFIRM RESERVATION")
        
        st.markdown('</div>', unsafe_allow_html=True)

        if submitted:
            if not final_cust:
                st.error("Please provide a Customer Name.")
            elif not tables:
                st.error("Please select at least one table.")
            else:
                with st.spinner("Processing..."):
                    start_dt = datetime.combine(res_date, res_time)
                    end_dt = start_dt + timedelta(hours=duration)
                    payload = {
                        "Table": tables, # List of tables
                        "Customer Name": final_cust,
                        "Start": start_dt, "End": end_dt, "Status": "Reserved",
                        "ID": str(uuid.uuid4())[:8], "Notes": notes, "Pax": pax
                    }
                    add_reservation(payload)
                    st.toast("Reservation Created!", icon="🎉")
                    st.cache_resource.clear()

# ==========================================
# TAB 2: GRID VISUAL
# ==========================================
with tab2:
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    
    col_f1, _ = st.columns([1, 4])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="view_date")
        
    df = load_data()
    
    if df.empty:
        st.info("No Data.")
    else:
        # Filter Data & Exclude Cancelled
        mask = (df['Start'].dt.date == view_date) & (df['Status'] != 'Cancelled')
        df_day = df.loc[mask].copy()

        # --- GRID LOGIC ---
        time_slots = []
        current_t = datetime.combine(view_date, time(10, 0))
        end_t = datetime.combine(view_date, time(22, 0))
        while current_t <= end_t:
            time_slots.append(current_t)
            current_t += timedelta(minutes=30)
            
        time_labels = [t.strftime('%H:%M') for t in time_slots]
        all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]
        
        z_data = [] 
        text_data = [] 
        
        for tbl in all_tables:
            row_z = []
            row_text = []
            for t_slot in time_slots:
                is_booked = 0
                hover_txt = "Available"
                
                # Check for table match. 
                # Since 'Table' col can now be "Table 1, Table 2", we check if current 'tbl' is IN that string
                res_match = df_day[
                    (df_day['Table'].str.contains(tbl, na=False)) & 
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

        # PLOT
        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=time_labels,
            y=all_tables,
            text=text_data,
            hoverinfo="text",
            colorscale=[[0, '#F8F9FA'], [1, '#12784A']], 
            showscale=False,
            xgap=2, 
            ygap=2
        ))
        
        # ADDED: Explicit font color for the chart so labels are visible
        fig.update_layout(
            title=dict(text=f"Schedule: {view_date.strftime('%d %b %Y')}", font=dict(color="#333333")),
            height=500,
            xaxis_title="Time",
            yaxis_autorange="reversed",
            plot_bgcolor="white",
            paper_bgcolor="white", # Ensures chart background is white
            font=dict(color="#333333"), # Ensures axes labels are dark
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # --- MANAGER LIST ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.subheader("📋 Status Manager")
    
    if not df.empty:
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
    st.markdown('</div>', unsafe_allow_html=True)