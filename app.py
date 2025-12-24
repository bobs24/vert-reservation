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

# --- 2. CSS OVERRIDES (FORCE UNIFORMITY) ---
st.markdown("""
    <style>
    /* 1. GLOBAL BACKGROUND & TEXT */
    .stApp {
        background-color: #F4F6F8; /* Light Grey Background */
        color: #333333;
        font-family: 'Inter', sans-serif;
    }

    /* 2. FORCE ALL INPUTS TO BE WHITE WITH BLACK TEXT */
    /* This targets Text Inputs, Number Inputs, Date Pickers */
    input {
        background-color: #FFFFFF !important;
        color: #000000 !important; 
    }
    
    /* This targets Selectboxes, Multiselects, and Time Pickers */
    div[data-baseweb="select"] > div, 
    div[data-baseweb="base-input"], 
    div[data-baseweb="input"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border-color: #E0E0E0 !important;
    }
    
    /* Force text inside the dropdowns to be black */
    div[data-baseweb="select"] span {
        color: #000000 !important;
    }
    
    /* Fix the 'X' and arrow icons in dropdowns */
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
        background-color: #12784A !important;
        color: white !important;
        border: none !important;
        font-weight: bold;
    }
    
    /* 5. REMOVE WEIRD SPACING AT TOP */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
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
    
    table_str = ", ".join(payload["Table"])
    sheet.append_row([
        table_str, payload["Customer Name"], str(payload["Start"]), 
        str(payload["End"]), payload["Status"], payload["ID"], 
        payload["Notes"], payload["Pax"]
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
# TAB 1: FORM (Clean Layout)
# ==========================================
with tab1:
    # We use a container to visually group, but we don't try to wrap it in HTML div anymore
    with st.container():
        st.subheader("📅 Date & Time")
        c_date, c_pad = st.columns([1, 3])
        with c_date:
            res_date = st.date_input("Select Date", min_value=datetime.now())
        if res_date.weekday() == 0:
            st.error("⛔ **STOP!** Monday selected. (Venue Closed)")

    st.markdown("---") # Simple divider instead of card
    
    with st.form("res_form", clear_on_submit=True):
        st.subheader("👤 Guest Information")
        
        df_cached = load_data()
        prev_customers = sorted(df_cached["Customer Name"].dropna().unique().tolist()) if not df_cached.empty else []

        c1, c2 = st.columns(2)
        with c1:
            cust_select = st.selectbox("Search Existing Customer", [""] + prev_customers)
        with c2:
            cust_new = st.text_input("Or Enter New Name")
        
        final_cust = cust_new if cust_new else cust_select
        
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
            if not final_cust:
                st.error("Please provide a Customer Name.")
            elif not tables:
                st.error("Please select at least one table.")
            else:
                with st.spinner("Processing..."):
                    start_dt = datetime.combine(res_date, res_time)
                    end_dt = start_dt + timedelta(hours=duration)
                    payload = {
                        "Table": tables,
                        "Customer Name": final_cust,
                        "Start": start_dt, "End": end_dt, "Status": "Reserved",
                        "ID": str(uuid.uuid4())[:8], "Notes": notes, "Pax": pax
                    }
                    add_reservation(payload)
                    st.toast("Reservation Created!", icon="🎉")
                    st.cache_resource.clear()

# ==========================================
# TAB 2: GRID VISUAL (Fixed Axis)
# ==========================================
with tab2:
    col_f1, _ = st.columns([1, 4])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="view_date")
        
    df = load_data()
    
    if df.empty:
        st.info("No Data.")
    else:
        mask = (df['Start'].dt.date == view_date) & (df['Status'] != 'Cancelled')
        df_day = df.loc[mask].copy()

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

        fig = go.Figure(data=go.Heatmap(
            z=z_data, x=time_labels, y=all_tables,
            text=text_data, hoverinfo="text",
            colorscale=[[0, '#F8F9FA'], [1, '#12784A']], 
            showscale=False, xgap=2, ygap=2
        ))
        
        # --- FIXED CHART LAYOUT ---
        fig.update_layout(
            title=dict(text=f"Schedule: {view_date.strftime('%d %b %Y')}", font=dict(color="#333333", size=20)),
            height=600, # Increased height
            xaxis_title="Time",
            yaxis_autorange="reversed",
            plot_bgcolor="white",
            paper_bgcolor="#F4F6F8",
            font=dict(color="#333333"),
            # Increased margins so Y-axis labels fit
            margin=dict(l=150, r=20, t=60, b=50),
        )
        # Explicitly set Y-axis font size
        fig.update_yaxes(tickfont=dict(size=14, color='black', family="Arial Black"))
        fig.update_xaxes(tickfont=dict(size=12, color='black'))
        
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
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