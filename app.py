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

# --- IMPROVED UI STYLING ---
st.markdown("""
<style>

/* ---------- GLOBAL APP ---------- */

.stApp {
    background-color: #F8FAFC;
    font-family: "Inter", sans-serif;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}


/* ---------- HEADERS ---------- */

h1 {
    font-size: 34px !important;
    font-weight: 800 !important;
    color: #0F172A !important;
}

h2, h3 {
    font-weight: 700 !important;
    color: #1E293B !important;
}

/* ---------- TABS (NEW BOOKING / SCHEDULE GRID) ---------- */

button[data-baseweb="tab"] {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #334155 !important;
    padding: 10px 18px !important;
}

/* active tab */

button[data-baseweb="tab"][aria-selected="true"] {
    color: #0F172A !important;
    border-bottom: 3px solid #FACC15 !important;
}

/* hover */

button[data-baseweb="tab"]:hover {
    color: #000000 !important;
}

/* ---------- LABELS ---------- */

[data-testid="stWidgetLabel"] {
    background: none !important;
    border: none !important;
    padding: 0 !important;
    margin-bottom: 6px !important;
}

[data-testid="stWidgetLabel"] p {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #334155 !important;
}


/* ---------- INPUT BOX SYSTEM ---------- */

div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="select"] > div,
.stDateInput > div,
.stTimeInput > div,
.stNumberInput > div {

    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    min-height: 42px;
    transition: 0.2s border ease;
}

/* Focus state */

div[data-baseweb="input"]:focus-within,
div[data-baseweb="base-input"]:focus-within,
div[data-baseweb="select"] > div:focus-within,
.stDateInput > div:focus-within,
.stTimeInput > div:focus-within {
    border: 1px solid #FACC15 !important;
    box-shadow: 0 0 0 1px #FACC15;
}


/* ---------- INPUT TEXT COLOR FIX ---------- */

/* All text inputs */

input,
textarea {
    color: #000000 !important;
    font-size: 15px !important;
    font-weight: 500 !important;
}

/* Selectbox + Multiselect */

div[data-baseweb="select"] * {
    color: #000000 !important;
}

/* Dropdown list */

div[role="listbox"] * {
    color: #000000 !important;
}

/* Number input */

.stNumberInput input {
    color: #000000 !important;
}

/* Date / time input */

.stDateInput input,
.stTimeInput input {
    color: #000000 !important;
}

/* Placeholder text */

input::placeholder {
    color: #64748B !important;
}


/* ---------- MULTISELECT TAGS ---------- */

span[data-baseweb="tag"] {
    background-color: #FEF08A !important;
    color: #1E293B !important;
    border-radius: 6px !important;
}


/* ---------- BUTTON ---------- */

.stButton > button {

    background-color: #FACC15 !important;
    color: #000 !important;
    font-weight: 700;
    border-radius: 8px;
    border: none;
    height: 44px;
    transition: 0.2s;
}

.stButton > button:hover {

    background-color: #EAB308 !important;
    transform: translateY(-1px);

}


/* ---------- METRICS ---------- */

[data-testid="stMetricValue"] {

    color: #16A34A;
    font-weight: 800;
    font-size: 28px;

}

[data-testid="stMetricLabel"] {

    font-weight: 600;
    color: #475569;

}


/* ---------- DATA EDITOR ---------- */

[data-testid="stDataEditor"] {

    border-radius: 10px;
    border: 1px solid #E2E8F0;

}


/* ---------- DIVIDERS ---------- */

hr {
    border-color: #E2E8F0;
}

</style>
""", unsafe_allow_html=True)

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
        return df
    except: return pd.DataFrame()

def add_reservation(payload):
    client = get_connection()
    sheet = client.open_by_key(SHEET_ID).sheet1
    if not sheet.row_values(1):
        sheet.append_row(["Table", "Customer Name", "Phone Number", "Start", "End", "Status", "ID", "Notes", "Pax"])

    table_str = ", ".join(payload["Table"])
    sheet.append_row([
        table_str, 
        payload["Customer Name"], 
        payload["Phone Number"],
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
    id_list = sheet.col_values(7)
    updates = []
    for row_id, new_status in changes_dict.items():
        try:
            row_num = id_list.index(row_id) + 1
            updates.append({'range': f'F{row_num}', 'values': [[new_status]]})
        except: continue
    if updates: sheet.batch_update(updates)

st.title("🍽️ Vert Reservation Manager")

tab1, tab2 = st.tabs(["📝 NEW BOOKING", "📊 SCHEDULE GRID"])

with tab1:
    with st.container():
        st.subheader("📅 Date & Time")
        c_date, c_pad = st.columns([1, 3])
        with c_date:
            res_date = st.date_input("Select Date", min_value=datetime.now())
        if res_date.weekday() == 0:
            st.error("⛔ **STOP!** Monday selected. (Venue Closed)")

    st.markdown("---")

    df_cached = load_data()
    search_options = []
    if not df_cached.empty:
        temp_df = df_cached[["Customer Name", "Phone Number"]].drop_duplicates()
        search_options = (temp_df["Customer Name"].astype(str) + " | " + temp_df["Phone Number"].astype(str)).tolist()
    
    st.subheader("👤 Guest Information")
    guest_search = st.selectbox("Search by Name or Phone (Suggests Existing)", ["+ Add New Guest"] + sorted(search_options))
    
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

with tab2:
    col_f1, _ = st.columns([1, 2])
    with col_f1:
        view_date = st.date_input("📅 View Schedule For", datetime.now(), key="grid_view_final")

    df = load_data()
    df_day = df[df['Start'].dt.date == view_date].copy() if not df.empty else pd.DataFrame()
    
    start_view = datetime.combine(view_date, time(10, 0))
    end_view = datetime.combine(view_date, time(23, 0))
    all_tables = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]

    confirmed = df_day[df_day['Status'] == 'Reserved'] if not df_day.empty else pd.DataFrame()

    total_res = len(confirmed)
    total_pax = confirmed['Pax'].sum() if not confirmed.empty else 0
    
    if not confirmed.empty:
        plot_df = confirmed.assign(Table=confirmed['Table'].str.split(', ')).explode('Table')
        active_tables = plot_df['Table'].nunique()
    else:
        plot_df = pd.DataFrame()
        active_tables = 0

    st.markdown("### 📈 Daily Summary")
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Reservations", total_res)
    m2.metric("Total Pax", int(total_pax))
    m3.metric("Tables Occupied", active_tables)
    st.markdown("---")

    skeleton_df = pd.DataFrame([{"Table": t, "Start": start_view, "End": start_view, "IsDummy": True} for t in all_tables])

    if not plot_df.empty:
        plot_df['IsDummy'] = False
        final_plot_df = pd.concat([skeleton_df, plot_df], ignore_index=True)
    else:
        final_plot_df = skeleton_df

    fig = px.timeline(
        final_plot_df, x_start="Start", x_end="End", y="Table",
        color="IsDummy", color_discrete_map={True: "rgba(0,0,0,0)", False: "#17A363"},
        hover_name="Customer Name" if "Customer Name" in final_plot_df.columns else None
    )

    fig.update_traces(
        hovertemplate="<br><b>%{hovertext}</b><br>%{base|%H:%M} - %{x|%H:%M}<extra></extra>", 
        selector=dict(name="False"),
        marker_line_color='rgb(8,48,107)',
        marker_line_width=1.5,
        opacity=0.95
    )
    fig.update_traces(hoverinfo='none', selector=dict(name="True"))

    fig.update_layout(
        xaxis_range=[start_view, end_view],
        xaxis=dict(
            tickformat="%H:%M", 
            gridcolor="#CBD5E0", 
            side="top", 
            title="", 
            tickfont=dict(color="#1A202C", size=14, weight="bold")
        ),
        yaxis=dict(
            categoryorder="array", 
            categoryarray=all_tables[::-1], 
            gridcolor="#CBD5E0", 
            title="", 
            tickfont=dict(color="#1A202C", size=14, weight="bold")
        ),
        plot_bgcolor="#FFFFFF", 
        paper_bgcolor="rgba(0,0,0,0)", 
        height=550, 
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📋 Status Management")
    
    if not df_day.empty:
        edited_df = st.data_editor(
            df_day[["Status", "Start", "Table", "Customer Name", "Pax", "ID"]].sort_values("Start"),
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status", 
                    options=["Reserved", "Cancelled"],
                    required=True
                ),
                "Start": st.column_config.DatetimeColumn("Time", format="HH:mm"),
                "ID": None
            },
            hide_index=True, 
            use_container_width=True, 
            key="status_editor_vFinal"
        )

        if st.button("💾 SAVE CHANGES"):
            changes = {}
            for i, row in edited_df.iterrows():
                orig = df_day.loc[df_day['ID'] == row['ID'], 'Status'].values[0]
                if row['Status'] != orig:
                    changes[row['ID']] = row['Status']
            
            if changes:
                update_status_batch(changes)
                st.success("Changes Saved!")
                st.cache_resource.clear()
                st.rerun()
            else:
                st.info("No changes to save.")
    else:
        st.info("No reservations for this date.")




