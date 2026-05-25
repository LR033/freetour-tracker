"""
Streamlit dashboard — Discover Walks ranking tracker on Freetour.com/paris.

Data source: rankings.csv from the GitHub repo (configured below).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# CONFIG — update GITHUB_RAW_URL after you create your repo (see DEPLOY.md)
# ---------------------------------------------------------------------------

GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/YOUR_USERNAME/freetour-tracker/main/rankings.csv"
)

TARGET_TOURS = [
    "Le Marais Free Tour: Where Parisians Go",
    "Paris Icons Express Tour - Notre-Dame to Louvre. Small group",
    "Montmartre Paris Free Tour: Moulin Rouge to Sacre Coeur",
    "Paris Left Bank: Writers, Revolution & Black Coffee",
]

SHORT_NAMES = {
    "Le Marais Free Tour: Where Parisians Go": "Le Marais",
    "Paris Icons Express Tour - Notre-Dame to Louvre. Small group": "Paris Icons",
    "Montmartre Paris Free Tour: Moulin Rouge to Sacre Coeur": "Montmartre",
    "Paris Left Bank: Writers, Revolution & Black Coffee": "Left Bank",
}

COLORS = {
    "Le Marais Free Tour: Where Parisians Go": "#E63946",
    "Paris Icons Express Tour - Notre-Dame to Louvre. Small group": "#457B9D",
    "Montmartre Paris Free Tour: Moulin Rouge to Sacre Coeur": "#2A9D8F",
    "Paris Left Bank: Writers, Revolution & Black Coffee": "#E9A84C",
}

TREND_EMOJI = {True: "▲", False: "▼", None: "—"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    try:
        df = pd.read_csv(GITHUB_RAW_URL, parse_dates=["date"])
    except Exception as e:
        st.error(
            f"Could not load data from GitHub. Have you updated `GITHUB_RAW_URL` in dashboard.py?\n\n`{e}`"
        )
        st.stop()

    df = df.dropna(subset=["position"])
    df["position"] = df["position"].astype(int)
    df = df[df["tour"].isin(TARGET_TOURS)]
    return df


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Discover Walks — Freetour Rankings",
    page_icon="🗼",
    layout="wide",
)

st.markdown(
    """
    <style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 18px 22px;
        border-left: 5px solid;
        margin-bottom: 8px;
    }
    .metric-card .tour-name { font-size: 13px; color: #666; margin-bottom: 4px; }
    .metric-card .position  { font-size: 32px; font-weight: 700; line-height: 1; }
    .metric-card .delta     { font-size: 13px; margin-top: 4px; }
    .up   { color: #2A9D8F; }
    .down { color: #E63946; }
    .flat { color: #888; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load & sidebar filters
# ---------------------------------------------------------------------------

df = load_data()

st.title("Discover Walks — Freetour.com/paris Rankings")
st.caption(
    "Tracks the daily listing position of Discover Walks tours on freetour.com/paris "
    "(English · Walking Tour filter applied). Lower position = better ranking."
)

st.sidebar.header("Filters")

min_date = df["date"].min().date()
max_date = df["date"].max().date()
default_start = max(min_date, max_date - timedelta(days=29))

date_range = st.sidebar.date_input(
    "Date range",
    value=(default_start, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, max_date

mask = (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
filtered = df[mask].copy()

if filtered.empty:
    st.warning("No data for the selected date range.")
    st.stop()

# ---------------------------------------------------------------------------
# Summary cards (today's / most-recent position + delta)
# ---------------------------------------------------------------------------

st.subheader("Current positions")

latest_date = filtered["date"].max()
prev_dates = filtered[filtered["date"] < latest_date]["date"]
prev_date = prev_dates.max() if not prev_dates.empty else None

cols = st.columns(4)

for i, tour in enumerate(TARGET_TOURS):
    tour_df = filtered[filtered["tour"] == tour].sort_values("date")
    short = SHORT_NAMES[tour]
    color = COLORS[tour]

    today_rows = tour_df[tour_df["date"] == latest_date]
    today_pos = int(today_rows["position"].iloc[0]) if not today_rows.empty else None

    delta_html = ""
    if prev_date is not None and today_pos is not None:
        prev_rows = tour_df[tour_df["date"] == prev_date]
        if not prev_rows.empty:
            prev_pos = int(prev_rows["position"].iloc[0])
            diff = prev_pos - today_pos  # positive = moved up (improved)
            if diff > 0:
                delta_html = f'<span class="up">▲ {diff} vs yesterday</span>'
            elif diff < 0:
                delta_html = f'<span class="down">▼ {abs(diff)} vs yesterday</span>'
            else:
                delta_html = '<span class="flat">— no change</span>'

    pos_display = f"#{today_pos}" if today_pos is not None else "N/A"

    with cols[i]:
        st.markdown(
            f"""
            <div class="metric-card" style="border-color:{color}">
                <div class="tour-name">{short}</div>
                <div class="position" style="color:{color}">{pos_display}</div>
                <div class="delta">{delta_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Line chart
# ---------------------------------------------------------------------------

st.subheader("Ranking over time")

fig = go.Figure()

for tour in TARGET_TOURS:
    tour_df = filtered[filtered["tour"] == tour].sort_values("date")
    if tour_df.empty:
        continue

    fig.add_trace(
        go.Scatter(
            x=tour_df["date"],
            y=tour_df["position"],
            mode="lines+markers",
            name=SHORT_NAMES[tour],
            line=dict(color=COLORS[tour], width=2.5),
            marker=dict(size=7),
            hovertemplate=(
                f"<b>{SHORT_NAMES[tour]}</b><br>"
                "Date: %{x|%Y-%m-%d}<br>"
                "Position: #%{y}<extra></extra>"
            ),
        )
    )

fig.update_layout(
    yaxis=dict(
        autorange="reversed",
        title="Position (lower = better)",
        tickformat="d",
        dtick=1,
    ),
    xaxis=dict(title="Date"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=0, r=0, t=40, b=0),
    hovermode="x unified",
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    height=420,
)
fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Raw data table
# ---------------------------------------------------------------------------

with st.expander("Raw data"):
    pivot = (
        filtered.pivot_table(index="date", columns="tour", values="position", aggfunc="first")
        .rename(columns=SHORT_NAMES)
        .sort_index(ascending=False)
    )
    pivot.index = pivot.index.strftime("%Y-%m-%d")
    st.dataframe(pivot, use_container_width=True)

st.caption(
    f"Last updated: {latest_date.strftime('%Y-%m-%d')} · "
    "Data refreshes automatically every day at 9:00 AM Paris time."
)
