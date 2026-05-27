"""
Streamlit dashboard — Discover Walks (Freetour) & Charing Cross (GuruWalk)
ranking tracker in Paris.

Data source: rankings.csv from the GitHub repo (configured below).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import timedelta

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/LR033/freetour-tracker/main/rankings.csv"
)

# ---------------------------------------------------------------------------
# Per-platform config
# ---------------------------------------------------------------------------

PLATFORMS = {
    "freetour": {
        "label": "Freetour.com",
        "site_label": "freetour.com/paris",
        "provider": "Discover Walks",
        "tours": [
            "Le Marais Free Tour: Where Parisians Go",
            "Paris Icons Express Tour - Notre-Dame to Louvre. Small group",
            "Montmartre Paris Free Tour: Moulin Rouge to Sacre Coeur",
            "Paris Left Bank: Writers, Revolution & Black Coffee",
        ],
        "short_names": {
            "Le Marais Free Tour: Where Parisians Go": "Le Marais",
            "Paris Icons Express Tour - Notre-Dame to Louvre. Small group": "Paris Icons",
            "Montmartre Paris Free Tour: Moulin Rouge to Sacre Coeur": "Montmartre",
            "Paris Left Bank: Writers, Revolution & Black Coffee": "Left Bank",
        },
        "colors": ["#E63946", "#457B9D", "#2A9D8F", "#E9C46A",
                   "#9B5DE5", "#F15BB5", "#00BBF9"],
    },
    "guruwalk": {
        "label": "GuruWalk",
        "site_label": "guruwalk.com/paris",
        "provider": "Charing Cross",
        "tours": [
            "Paris Old Town - small group - Notre Dame and Latin Quarter",
            "Le Marais without the crowds, the beating heart of Paris",
            "Paris starts here - the tour for first timers. Small Group",
            "The village of Montmartre without the crowds",
            "Seeing Paris - the most visual tour of Paris. Small group",
            "Small-Group free tour: Secret Paris - the hidden gems tourists never see",
            "Saint Germain and Latin Quarter in a small group",
        ],
        "short_names": {
            "Paris Old Town - small group - Notre Dame and Latin Quarter": "Old Town",
            "Le Marais without the crowds, the beating heart of Paris": "Le Marais",
            "Paris starts here - the tour for first timers. Small Group": "First Timers",
            "The village of Montmartre without the crowds": "Montmartre",
            "Seeing Paris - the most visual tour of Paris. Small group": "Seeing Paris",
            "Small-Group free tour: Secret Paris - the hidden gems tourists never see": "Secret Paris",
            "Saint Germain and Latin Quarter in a small group": "Saint Germain",
        },
        "colors": ["#E63946", "#457B9D", "#2A9D8F", "#E9C46A",
                   "#9B5DE5", "#F15BB5", "#00BBF9"],
    },
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    try:
        df = pd.read_csv(GITHUB_RAW_URL, parse_dates=["date"])
    except Exception as e:
        st.error(
            f"Could not load data from GitHub.\n\n`{e}`"
        )
        st.stop()

    df = df.dropna(subset=["position"])
    df["position"] = df["position"].astype(int)

    # Back-fill source column for rows written before the migration
    if "source" not in df.columns:
        df["source"] = "freetour"
    else:
        df["source"] = df["source"].fillna("freetour")

    return df

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Tour Rankings Dashboard",
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
        min-height: 100px;
    }
    .metric-card .tour-name { font-size: 12px; color: #666; margin-bottom: 4px; }
    .metric-card .position  { font-size: 30px; font-weight: 700; line-height: 1; }
    .metric-card .delta     { font-size: 12px; margin-top: 6px; }
    .up   { color: #2A9D8F; }
    .down { color: #E63946; }
    .flat { color: #888; }
    .na   { color: #aaa; font-style: italic; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data & sidebar
# ---------------------------------------------------------------------------

df = load_data()

st.sidebar.header("Settings")

platform_key = st.sidebar.selectbox(
    "Platform",
    options=list(PLATFORMS.keys()),
    format_func=lambda k: PLATFORMS[k]["label"],
)

cfg = PLATFORMS[platform_key]

st.title(f"{cfg['label']} — {cfg['provider']} Rankings")
st.caption(
    f"Daily listing position of **{cfg['provider']}** tours on "
    f"**{cfg['site_label']}** · Lower position = better ranking."
)

platform_df = df[df["source"] == platform_key].copy()

if platform_df.empty:
    st.info(f"No data yet for {cfg['label']}. Check back after the next scrape.")
    st.stop()

# Filter to only the configured tours
platform_df = platform_df[platform_df["tour"].isin(cfg["tours"])]

min_date = platform_df["date"].min().date()
max_date = platform_df["date"].max().date()
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

mask = (
    (platform_df["date"].dt.date >= start_date)
    & (platform_df["date"].dt.date <= end_date)
)
filtered = platform_df[mask].copy()

if filtered.empty:
    st.warning("No data for the selected date range.")
    st.stop()

# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------

st.subheader("Current positions")

latest_date = filtered["date"].max()
prev_dates = filtered[filtered["date"] < latest_date]["date"]
prev_date = prev_dates.max() if not prev_dates.empty else None

tours = cfg["tours"]
colors = cfg["colors"]
short_names = cfg["short_names"]

# Lay out cards 4 per row
for row_start in range(0, len(tours), 4):
    row_tours = tours[row_start: row_start + 4]
    cols = st.columns(len(row_tours))

    for i, tour in enumerate(row_tours):
        color = colors[(row_start + i) % len(colors)]
        short = short_names.get(tour, tour)
        tour_df = filtered[filtered["tour"] == tour].sort_values("date")

        today_rows = tour_df[tour_df["date"] == latest_date]
        today_pos = int(today_rows["position"].iloc[0]) if not today_rows.empty else None

        if today_pos is None:
            pos_display = "N/A"
            delta_html = '<span class="na">not listed today</span>'
        else:
            pos_display = f"#{today_pos}"
            delta_html = ""
            if prev_date is not None:
                prev_rows = tour_df[tour_df["date"] == prev_date]
                if not prev_rows.empty:
                    prev_pos = int(prev_rows["position"].iloc[0])
                    diff = prev_pos - today_pos
                    if diff > 0:
                        delta_html = f'<span class="up">▲ {diff} vs yesterday</span>'
                    elif diff < 0:
                        delta_html = f'<span class="down">▼ {abs(diff)} vs yesterday</span>'
                    else:
                        delta_html = '<span class="flat">— no change</span>'

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

for i, tour in enumerate(tours):
    tour_df = filtered[filtered["tour"] == tour].sort_values("date")
    if tour_df.empty:
        continue

    color = colors[i % len(colors)]
    fig.add_trace(
        go.Scatter(
            x=tour_df["date"],
            y=tour_df["position"],
            mode="lines+markers",
            name=short_names.get(tour, tour),
            line=dict(color=color, width=2.5),
            marker=dict(size=7),
            hovertemplate=(
                f"<b>{short_names.get(tour, tour)}</b><br>"
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
    height=440,
)
fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Raw data table
# ---------------------------------------------------------------------------

with st.expander("Raw data"):
    pivot = (
        filtered.pivot_table(
            index="date", columns="tour", values="position", aggfunc="first"
        )
        .rename(columns=short_names)
        .sort_index(ascending=False)
    )
    pivot.index = pivot.index.strftime("%Y-%m-%d")
    st.dataframe(pivot, use_container_width=True)

st.caption(
    f"Last updated: {latest_date.strftime('%Y-%m-%d')} · "
    "Refreshed daily at 10:00 AM Paris time."
)
