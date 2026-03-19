import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, time
import plotly.graph_objects as go
import uuid

st.set_page_config(
    page_title="Vert — Reservations",
    layout="wide",
    page_icon="🍃",
    initial_sidebar_state="collapsed"
)

# ── DESIGN SYSTEM ───────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── BASE ── */
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #0D1117; color: #E2E8F0; }
.block-container { padding: 2rem 3rem 4rem; max-width: 1280px; }

/* ── HEADER ── */
.vert-header {
    display: flex; align-items: baseline; gap: 14px;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #1E2D3D;
    margin-bottom: 2rem;
}
.vert-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 2.4rem; font-style: italic;
    color: #4ADE80; letter-spacing: -0.5px; line-height: 1;
}
.vert-sub {
    font-size: 0.8rem; font-weight: 300;
    color: #64748B; text-transform: uppercase;
    letter-spacing: 3px;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: #161B22;
    border: 1px solid #1E2D3D; border-radius: 12px; padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    font-size: 13px !important; font-weight: 500 !important;
    color: #64748B !important; background: transparent !important;
    border-radius: 8px !important; padding: 8px 20px !important;
    border: none !important; letter-spacing: 0.3px;
}
.stTabs [aria-selected="true"] {
    background: #1E3A2F !important;
    color: #4ADE80 !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── SECTION CARD ── */
.section-card {
    background: #161B22;
    border: 1px solid #1E2D3D;
    border-radius: 16px;
    padding: 1.6rem 2rem;
    margin-bottom: 1.2rem;
}
.section-label {
    font-size: 0.7rem; font-weight: 600; letter-spacing: 2.5px;
    text-transform: uppercase; color: #4ADE80;
    margin-bottom: 1rem;
}

/* ── INPUTS ── */
.stTextInput > div > div,
.stNumberInput > div > div,
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background: #0D1117 !important;
    border: 1px solid #1E2D3D !important;
    border-radius: 10px !important;
    color: #E2E8F0 !important;
}
.stTextInput > div > div:focus-within,
.stSelectbox > div > div:focus-within,
.stMultiSelect > div > div:focus-within {
    border-color: #4ADE80 !important;
    box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.12) !important;
}
.stDateInput > div,
.stTimeInput > div { border-radius: 10px !important; }
label { color: #94A3B8 !important; font-size: 0.8rem !important; font-weight: 500 !important; letter-spacing: 0.5px; }

/* ── SUBMIT BUTTON ── */
.stForm .stButton > button, 
[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%) !important;
    color: #0D1117 !important; font-weight: 700 !important;
    font-size: 0.85rem !important; letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    border: none !important; border-radius: 10px !important;
    padding: 0.6rem 2rem !important;
    transition: all 0.2s ease !important;
}
.stForm .stButton > button:hover { box-shadow: 0 0 20px rgba(74,222,128,0.3) !important; }
.stForm .stButton > button:disabled {
    background: #1E2D3D !important; color: #475569 !important;
    cursor: not-allowed !important; box-shadow: none !important;
}

/* ── SECONDARY BUTTONS ── */
.stButton > button:not([disabled]) {
    background: #1E2D3D !important;
    color: #94A3B8 !important; border: 1px solid #263347 !important;
    border-radius: 10px !important;
}
.stButton > button:not([disabled]):hover {
    border-color: #4ADE80 !important; color: #4ADE80 !important;
}

/* ── CONFLICT ALERT ── */
.conflict-box {
    background: #2D1515; border: 1px solid #7F1D1D;
    border-left: 4px solid #EF4444;
    border-radius: 10px; padding: 0.9rem 1.2rem;
    color: #FCA5A5; font-size: 0.88rem;
    margin: 0.8rem 0;
}
.conflict-box strong { color: #F87171; }

/* ── AVAILABLE BADGE ── */
.avail-box {
    background: #0F2D1E; border: 1px solid #14532D;
    border-left: 4px solid #22C55E;
    border-radius: 10px; padding: 0.9rem 1.2rem;
    color: #86EFAC; font-size: 0.88rem;
    margin: 0.8rem 0;
}

/* ── METRICS ── */
div[data-testid="stMetric"] {
    background: #161B22 !important; border: 1px solid #1E2D3D !important;
    border-radius: 14px !important; padding: 1.2rem 1.5rem !important;
}
div[data-testid="stMetric"] label { font-size: 0.7rem !important; color: #4ADE80 !important; letter-spacing: 2px !important; }
div[data-testid="stMetricValue"] { font-size: 2rem !important; color: #E2E8F0 !important; font-weight: 600 !important; }

/* ── DATA EDITOR ── */
.stDataFrame { border: 1px solid #1E2D3D; border-radius: 12px; overflow: hidden; }
[data-testid="stDataEditor"] { background: #161B22; border: 1px solid #1E2D3D; border-radius: 12px; }

/* ── DIVIDER ── */
hr { border-color: #1E2D3D !important; }

/* ── TOGGLE ── */
.stToggle > label { color: #64748B !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0D1117; }
::-webkit-scrollbar-thumb { background: #1E2D3D; border-radius: 4px; }

/* ── SKELETON SECTION ── */
.time-warning {
    background: #1C1A0D; border: 1px solid #713F12;
    border-left: 4px solid #F59E0B;
    border-radius: 10px; padding: 0.9rem 1.2rem;
    color: #FCD34D; font-size: 0.88rem; margin: 0.8rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="vert-header">
    <span class="vert-logo">Vert</span>
    <span class="vert-sub">Reservation Manager</span>
</div>
""", unsafe_allow_html=True)

# ── DATA LAYER ────────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            return None
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

SHEET_ID = '1eUi8Neog9mXb5J17G3WTvCehtR0Bz3-mKkw49gG8tAE'

def load_data():
    client = get_connection()
    if not client:
        return pd.DataFrame()
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        expected_cols = ["Table", "Customer Name", "Phone Number", "Start", "End", "Status", "ID", "Notes", "Pax"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
        if not df.empty:
            df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
            df['End']   = pd.to_datetime(df['End'],   errors='coerce')
            df['Pax']   = pd.to_numeric(df['Pax'],    errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

def check_availability(new_start, new_end, requested_tables, existing_df, exclude_id=None):
    if existing_df.empty or not requested_tables:
        return True, []
    active = existing_df[existing_df['Status'] == 'Reserved'].copy()
    if exclude_id:
        active = active[active['ID'] != exclude_id]
    conflicts = []
    for _, row in active.iterrows():
        if (new_start < row['End']) and (new_end > row['Start']):
            row_tables = [t.strip() for t in str(row['Table']).split(',')]
            overlap = set(requested_tables).intersection(set(row_tables))
            if overlap:
                conflicts.append(
                    f"<strong>{row['Customer Name']}</strong> has {', '.join(overlap)} "
                    f"from {row['Start'].strftime('%H:%M')}–{row['End'].strftime('%H:%M')}"
                )
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
        except:
            continue
    if updates:
        sheet.batch_update(updates)

# ── RESET COUNTER ─────────────────────────────────────────────────────────────
# Incrementing forces all outside-form widgets to get brand-new keys,
# so Streamlit renders them fresh with their default values.
if "booking_reset_n" not in st.session_state:
    st.session_state.booking_reset_n = 0

def bump_reset():
    st.session_state.booking_reset_n += 1

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
df_all = load_data()

ALL_TABLES = [f"Table {i}" for i in range(1, 9)] + ["Outdoor", "VIP"]

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["  NEW BOOKING  ", "  SCHEDULE GRID  "])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — NEW BOOKING
# ══════════════════════════════════════════════════════════════════════════════
with tab1:

    n = st.session_state.booking_reset_n  # shorthand

    # ── Guest search (outside form for reactivity) ──
    st.markdown('<div class="section-label">Guest</div>', unsafe_allow_html=True)
    search_options = []
    if not df_all.empty:
        temp_df = df_all[["Customer Name", "Phone Number"]].drop_duplicates()
        search_options = (
            temp_df["Customer Name"].astype(str) + " | " + temp_df["Phone Number"].astype(str)
        ).tolist()

    guest_search = st.selectbox(
        "Search returning guest",
        ["＋ New guest"] + sorted(search_options),
        label_visibility="collapsed",
        key=f"rt_guest_{n}"
    )
    val_name, val_phone = (
        guest_search.split(" | ")
        if guest_search != "＋ New guest" else ("", "")
    )

    # ── Date / time / table picker OUTSIDE form (real-time conflict check) ──
    st.markdown('<div class="section-label" style="margin-top:1.4rem">When & Where</div>', unsafe_allow_html=True)
    
    dc1, dc2, dc3, dc4 = st.columns([1.1, 0.9, 0.9, 1.5])
    with dc1:
        res_date  = st.date_input("Date", min_value=datetime.now().date(), key=f"rt_date_{n}")
    with dc2:
        res_time  = st.time_input("Arrival", value=time(19, 0), key=f"rt_time_{n}")
    with dc3:
        duration  = st.selectbox("Duration", [1, 1.5, 2, 2.5, 3, 4, 5], index=2,
                                  format_func=lambda x: f"{x} hr{'s' if x != 1 else ''}",
                                  key=f"rt_dur_{n}")
    with dc4:
        tables    = st.multiselect("Table(s)", ALL_TABLES, key=f"rt_tables_{n}")

    # ── REAL-TIME CONFLICT CHECK ──────────────────────────────────────────────
    is_monday  = (res_date.weekday() == 0)
    start_dt   = datetime.combine(res_date, res_time)
    end_dt     = start_dt + timedelta(hours=float(duration))

    can_submit = True  # Gate for form submit button

    if is_monday:
        st.markdown(
            '<div class="time-warning">⚠️ <strong>Closed on Mondays</strong> — please select another date.</div>',
            unsafe_allow_html=True
        )
        can_submit = False
    elif tables:
        is_available, conflicts = check_availability(start_dt, end_dt, tables, df_all)
        if not is_available:
            conflict_lines = "<br>".join(f"• {c}" for c in conflicts)
            st.markdown(
                f'<div class="conflict-box">🚫 <strong>Table conflict detected</strong><br>'
                f'<span style="opacity:0.85">{conflict_lines}</span><br>'
                f'<span style="opacity:0.6;font-size:0.8rem">Pick a different table or time slot.</span></div>',
                unsafe_allow_html=True
            )
            can_submit = False
        else:
            st.markdown(
                f'<div class="avail-box">✓ <strong>{", ".join(tables)}</strong> '
                f'is free from {start_dt.strftime("%H:%M")} to {end_dt.strftime("%H:%M")}</div>',
                unsafe_allow_html=True
            )

    # ── BOOKING FORM (only name, phone, pax, notes — no time/table here) ──────
    st.markdown('<div class="section-label" style="margin-top:1.4rem">Guest Details</div>', unsafe_allow_html=True)

    with st.form("res_form", clear_on_submit=True):
        fc1, fc2, fc3 = st.columns([2, 2, 1])
        with fc1:
            final_cust  = st.text_input("Customer Name", value=val_name,  placeholder="e.g. John Doe")
        with fc2:
            final_phone = st.text_input("Phone Number",  value=val_phone, placeholder="e.g. 0812-XXXX")
        with fc3:
            pax         = st.number_input("Guests (pax)", min_value=1, value=2)

        notes  = st.text_input("Notes / Special Requests", placeholder="Anniversary, allergy, high chair…")

        submit = st.form_submit_button(
            "CONFIRM RESERVATION",
            use_container_width=True,
            disabled=(not can_submit)  # ← blocked when conflict or Monday
        )

        if submit:
            if not (final_cust.strip() and final_phone.strip() and tables):
                st.error("Please fill in Name, Phone, and select at least one Table.")
            else:
                # Double-check on submit (race condition guard)
                ok, c2 = check_availability(start_dt, end_dt, tables, df_all)
                if not ok:
                    st.error("A conflict appeared — please recheck your selection.")
                else:
                    with st.spinner("Saving reservation…"):
                        payload = {
                            "Table": tables,
                            "Customer Name": final_cust.strip(),
                            "Phone Number":  final_phone.strip(),
                            "Start": start_dt, "End": end_dt,
                            "Status": "Reserved",
                            "ID":    str(uuid.uuid4())[:8],
                            "Notes": notes, "Pax": pax
                        }
                        add_reservation(payload)
                    st.success(f"✓ Booked {', '.join(tables)} for {final_cust} at {start_dt.strftime('%H:%M')}")
                    st.cache_resource.clear()
                    bump_reset()
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCHEDULE GRID
# ══════════════════════════════════════════════════════════════════════════════
with tab2:

    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        view_date = st.date_input("View date", datetime.now().date(), key="grid_date")

    # ── Filter: only RESERVED, correct date ──────────────────────────────────
    if not df_all.empty:
        df_day_all  = df_all[df_all['Start'].dt.date == view_date].copy()
        df_reserved = df_day_all[df_day_all['Status'] == 'Reserved'].copy()
    else:
        df_day_all  = pd.DataFrame()
        df_reserved = pd.DataFrame()

    # ── Metrics ───────────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    total_res  = len(df_reserved)
    total_pax  = int(df_reserved['Pax'].sum()) if not df_reserved.empty else 0
    tables_occ = (
        df_reserved['Table'].str.split(', ').explode().nunique()
        if not df_reserved.empty else 0
    )
    peak_hour = ""
    if not df_reserved.empty:
        hour_counts = df_reserved['Start'].dt.hour.value_counts()
        if not hour_counts.empty:
            peak_hour = f"{hour_counts.idxmax():02d}:00"

    m1.metric("RESERVATIONS", total_res)
    m2.metric("TOTAL PAX",    total_pax)
    m3.metric("TABLES IN USE", f"{tables_occ} / {len(ALL_TABLES)}")
    m4.metric("PEAK HOUR",    peak_hour or "—")

    # ── GANTT CHART ────────────────────────────────────────────────────────────
    start_view = datetime.combine(view_date, time(10, 0))
    end_view   = datetime.combine(view_date, time(23, 30))

    fig = go.Figure()

    # One row per table — always drawn (skeleton)
    for i, tbl in enumerate(ALL_TABLES):
        # Ghost background bar (track)
        fig.add_trace(go.Bar(
            x=[(end_view - start_view).total_seconds() * 1000],
            y=[tbl],
            base=[start_view],
            orientation='h',
            marker_color='rgba(30,45,61,0.4)',
            marker_line_width=0,
            showlegend=False,
            hoverinfo='skip',
            width=0.55,
        ))

    # Actual reservations (only Reserved)
    if not df_reserved.empty:
        exploded = df_reserved.assign(
            Table=df_reserved['Table'].str.split(', ')
        ).explode('Table')

        for _, row in exploded.iterrows():
            duration_ms = (row['End'] - row['Start']).total_seconds() * 1000
            hover_txt = (
                f"<b>{row['Customer Name']}</b><br>"
                f"🕐 {row['Start'].strftime('%H:%M')} – {row['End'].strftime('%H:%M')}<br>"
                f"👥 {int(row['Pax'])} pax"
                + (f"<br>📝 {row['Notes']}" if row.get('Notes') else "")
            )
            fig.add_trace(go.Bar(
                x=[duration_ms],
                y=[row['Table']],
                base=[row['Start']],
                orientation='h',
                marker_color='#22C55E',
                marker_line_color='#0D1117',
                marker_line_width=2,
                marker_opacity=0.88,
                showlegend=False,
                text=row['Customer Name'],
                textposition='inside',
                textfont=dict(color='#0D1117', size=11, family='DM Sans'),
                hovertemplate=hover_txt + "<extra></extra>",
                width=0.55,
            ))

    # Layout
    hour_ticks = [start_view + timedelta(hours=h) for h in range(0, 14)]
    fig.update_layout(
        barmode='overlay',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=460,
        margin=dict(l=0, r=10, t=30, b=10),
        xaxis=dict(
            type='date',
            range=[start_view, end_view],
            tickvals=hour_ticks,
            ticktext=[t.strftime('%H:%M') for t in hour_ticks],
            tickfont=dict(color='#475569', size=11, family='DM Sans'),
            gridcolor='rgba(30,45,61,0.7)',
            gridwidth=1,
            zeroline=False,
            side='top',
            title='',
        ),
        yaxis=dict(
            categoryorder='array',
            categoryarray=ALL_TABLES[::-1],
            tickfont=dict(color='#94A3B8', size=12, family='DM Sans'),
            gridcolor='rgba(30,45,61,0.4)',
            title='',
            ticklabelposition='outside',
        ),
        hoverlabel=dict(
            bgcolor='#161B22',
            bordercolor='#22C55E',
            font=dict(color='#E2E8F0', size=12, family='DM Sans'),
        ),
        font=dict(family='DM Sans', color='#94A3B8'),
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # ── BOOKING MANAGEMENT TABLE ───────────────────────────────────────────────
    st.markdown('<hr style="margin: 0.5rem 0 1.2rem"/>', unsafe_allow_html=True)
    hdr1, hdr2 = st.columns([2, 1])
    with hdr1:
        st.markdown('<div class="section-label">Manage Bookings</div>', unsafe_allow_html=True)
    with hdr2:
        show_cancelled = st.toggle("Show cancelled", value=False)

    if not df_day_all.empty:
        df_display = (
            df_day_all.copy() if show_cancelled
            else df_day_all[df_day_all['Status'] == 'Reserved'].copy()
        )

        if not df_display.empty:
            edited_df = st.data_editor(
                df_display[["Status", "Start", "Table", "Customer Name", "Phone Number", "Pax", "Notes", "ID"]]
                    .sort_values("Start")
                    .reset_index(drop=True),
                column_config={
                    "Status": st.column_config.SelectboxColumn(
                        "Status", options=["Reserved", "Cancelled"], required=True, width="small"
                    ),
                    "Start": st.column_config.DatetimeColumn(
                        "Arrival", format="HH:mm", disabled=True, width="small"
                    ),
                    "Table":  st.column_config.TextColumn("Table",  disabled=True),
                    "Customer Name": st.column_config.TextColumn("Guest", disabled=True),
                    "Pax":    st.column_config.NumberColumn("Pax",   disabled=True, width="small"),
                    "Notes":  st.column_config.TextColumn("Notes",  disabled=True),
                    "ID":     None,
                },
                hide_index=True,
                use_container_width=True,
                key="editor_v4"
            )

            if st.button("APPLY CHANGES", use_container_width=True):
                changes = {}
                for _, row in edited_df.iterrows():
                    orig_rows = df_day_all.loc[df_day_all['ID'] == row['ID'], 'Status']
                    if not orig_rows.empty and row['Status'] != orig_rows.values[0]:
                        changes[row['ID']] = row['Status']
                if changes:
                    update_status_batch(changes)
                    st.toast("Updated!", icon="✅")
                    st.cache_resource.clear()
                    st.rerun()
                else:
                    st.toast("No changes detected.", icon="ℹ️")
        else:
            st.markdown(
                '<div style="color:#475569;padding:2rem;text-align:center;font-size:0.9rem">'
                'No active reservations for this date.</div>',
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            '<div style="color:#475569;padding:2rem;text-align:center;font-size:0.9rem">'
            'No reservations found for this date.</div>',
            unsafe_allow_html=True
        )
