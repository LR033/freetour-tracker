"""
Streamlit dashboard -- Discover Walks (Freetour) & Charing Cross (GuruWalk)
ranking tracker in Paris.

Data source: rankings.csv + notes.csv from the GitHub repo (configured below).
Notes are written back to GitHub via the Contents API so they persist on
Streamlit Cloud without a local filesystem.
"""

import base64
import csv
import io
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GITHUB_REPO     = "LR033/freetour-tracker"
GITHUB_BRANCH   = "main"
RANKINGS_RAW    = "https://raw.githubusercontent.com/LR033/freetour-tracker/main/rankings.csv"
NOTES_RAW       = "https://raw.githubusercontent.com/LR033/freetour-tracker/main/notes.csv"
GITHUB_API_BASE = "https://api.github.com"

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

NOTE_PLATFORM_OPTIONS = {
    "Freetour.com":    "freetour",
    "GuruWalk":        "guruwalk",
    "Both platforms":  "both",
}

PLATFORM_DISPLAY = {
    "freetour": "Freetour.com",
    "guruwalk": "GuruWalk",
    "both":     "Both",
}

# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _github_headers() -> dict:
    token = st.secrets.get("github_token", "")
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get_file(path: str):
    """Return (decoded_content_str, sha) or (None, None) on 404."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers=_github_headers(), timeout=10)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def _put_file(path: str, content: str, sha, message: str) -> bool:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, json=payload, headers=_github_headers(), timeout=10)
    return r.status_code in (200, 201)


def _require_token():
    token = st.secrets.get("github_token", "")
    if not token:
        return None, "github_token not set. Add it to Streamlit secrets (see DEPLOY.md)."
    return token, None


def _parse_notes(content: str) -> list:
    """Return list of dicts from notes CSV string."""
    return list(csv.DictReader(io.StringIO(content)))


def _serialize_notes(rows: list) -> str:
    """Serialize list of dicts back to CSV string."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["date", "platform", "note"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def save_note(note_date: str, platform: str, note_text: str):
    """Append one row to notes.csv via the GitHub Contents API."""
    token, err = _require_token()
    if err:
        return False, err

    current, sha = _get_file("notes.csv")
    if current is None:
        current = "date,platform,note\n"

    buf = io.StringIO()
    csv.writer(buf).writerow([note_date, platform, note_text])
    new_content = current.rstrip("\n") + "\n" + buf.getvalue()

    ok = _put_file("notes.csv", new_content, sha, f"note: {note_date} [{platform}]")
    if ok:
        return True, "Note saved and pushed to GitHub."
    return False, "GitHub API returned an error. Check your token permissions."



# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_rankings() -> pd.DataFrame:
    try:
        df = pd.read_csv(RANKINGS_RAW, parse_dates=["date"])
    except Exception as e:
        st.error(f"Could not load rankings from GitHub.\n\n`{e}`")
        st.stop()
    df = df.dropna(subset=["position"])
    df["position"] = df["position"].astype(int)
    if "source" not in df.columns:
        df["source"] = "freetour"
    else:
        df["source"] = df["source"].fillna("freetour")
    return df


def _normalise_notes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the date column is always datetime64 regardless of how the df was built."""
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def load_notes() -> pd.DataFrame:
    """Fetch notes from GitHub raw URL. Called only on fresh page load."""
    try:
        df = pd.read_csv(NOTES_RAW, parse_dates=["date"])
        return _normalise_notes(df[["date", "platform", "note"]].dropna(subset=["note"]))
    except Exception:
        return pd.DataFrame(columns=["date", "platform", "note"])


# ---------------------------------------------------------------------------
# Page config + CSS
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
# Load data
# ---------------------------------------------------------------------------

df = load_rankings()

# Session state is the single source of truth for notes.
# On fresh page load (notes_df absent) we fetch from GitHub.
# After any mutation we update session state directly -- no cache involved.
if "notes_df" not in st.session_state:
    st.session_state.notes_df = load_notes()

notes = st.session_state.notes_df

# ---------------------------------------------------------------------------
# Sidebar -- settings
# ---------------------------------------------------------------------------

st.sidebar.header("Settings")

platform_key = st.sidebar.selectbox(
    "Platform",
    options=list(PLATFORMS.keys()),
    format_func=lambda k: PLATFORMS[k]["label"],
)

cfg = PLATFORMS[platform_key]

platform_df = df[df["source"] == platform_key].copy()
platform_df = platform_df[platform_df["tour"].isin(cfg["tours"])]

if platform_df.empty:
    st.info(f"No data yet for {cfg['label']}. Check back after the next scrape.")
    st.stop()

min_date     = platform_df["date"].min().date()
max_date     = platform_df["date"].max().date()
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

# ---------------------------------------------------------------------------
# Sidebar -- add note form
# ---------------------------------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("Add a note")

has_token = bool(st.secrets.get("github_token", ""))
if not has_token:
    st.sidebar.caption(
        "Set `github_token` in Streamlit secrets to enable note saving. "
        "Notes will still appear on the chart once saved via git."
    )

with st.sidebar.form("add_note_form", clear_on_submit=True):
    note_date_input = st.date_input(
        "Date",
        value=date.today(),
        min_value=date(2026, 1, 1),
        max_value=date.today(),
    )
    note_platform_label = st.selectbox(
        "Platform",
        options=list(NOTE_PLATFORM_OPTIONS.keys()),
    )
    note_text_input = st.text_input(
        "Note",
        placeholder="e.g. Changed tour title on GuruWalk",
        max_chars=120,
    )
    submitted = st.form_submit_button(
        "Add note",
        disabled=not has_token,
        use_container_width=True,
    )

if submitted:
    if not note_text_input.strip():
        st.sidebar.warning("Note text cannot be empty.")
    else:
        platform_val = NOTE_PLATFORM_OPTIONS[note_platform_label]
        ok, msg = save_note(
            str(note_date_input),
            platform_val,
            note_text_input.strip(),
        )
        if ok:
            st.sidebar.success(msg)
            # Append to session state immediately so the note shows without a round-trip
            new_row = pd.DataFrame([{
                "date": pd.to_datetime(str(note_date_input)),
                "platform": platform_val,
                "note": note_text_input.strip(),
            }])
            st.session_state.notes_df = _normalise_notes(pd.concat(
                [st.session_state.notes_df, new_row], ignore_index=True
            ))
            st.rerun()
        else:
            st.sidebar.error(msg)

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title(f"{cfg['label']} -- {cfg['provider']} Rankings")
st.caption(
    f"Daily listing position of **{cfg['provider']}** tours on "
    f"**{cfg['site_label']}** · Lower position = better ranking."
)

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
prev_dates  = filtered[filtered["date"] < latest_date]["date"]
prev_date   = prev_dates.max() if not prev_dates.empty else None

tours       = cfg["tours"]
colors      = cfg["colors"]
short_names = cfg["short_names"]

for row_start in range(0, len(tours), 4):
    row_tours = tours[row_start: row_start + 4]
    cols = st.columns(len(row_tours))

    for i, tour in enumerate(row_tours):
        color   = colors[(row_start + i) % len(colors)]
        short   = short_names.get(tour, tour)
        tour_df = filtered[filtered["tour"] == tour].sort_values("date")

        today_rows = tour_df[tour_df["date"] == latest_date]
        today_pos  = int(today_rows["position"].iloc[0]) if not today_rows.empty else None

        if today_pos is None:
            pos_display = "N/A"
            delta_html  = '<span class="na">not listed today</span>'
        else:
            pos_display = f"#{today_pos}"
            delta_html  = ""
            if prev_date is not None:
                prev_rows = tour_df[tour_df["date"] == prev_date]
                if not prev_rows.empty:
                    prev_pos = int(prev_rows["position"].iloc[0])
                    diff = prev_pos - today_pos
                    if diff > 0:
                        delta_html = f'<span class="up">&#9650; {diff} vs yesterday</span>'
                    elif diff < 0:
                        delta_html = f'<span class="down">&#9660; {abs(diff)} vs yesterday</span>'
                    else:
                        delta_html = '<span class="flat">&#8212; no change</span>'

        with cols[i]:
            st.markdown(
                f'<div class="metric-card" style="border-color:{color}">'
                f'<div class="tour-name">{short}</div>'
                f'<div class="position" style="color:{color}">{pos_display}</div>'
                f'<div class="delta">{delta_html}</div>'
                f'</div>',
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

# --- Note annotations ---
relevant_notes = notes[
    notes["platform"].isin([platform_key, "both"])
].copy()
if not relevant_notes.empty:
    relevant_notes = relevant_notes[
        (relevant_notes["date"].dt.date >= start_date)
        & (relevant_notes["date"].dt.date <= end_date)
    ]

if not relevant_notes.empty:
    for note_date, group in relevant_notes.groupby("date"):
        label = " | ".join(group["note"].tolist())
        if len(label) > 50:
            label = label[:47] + "..."
        x_val = note_date.isoformat()
        fig.add_shape(
            type="line",
            xref="x", yref="paper",
            x0=x_val, x1=x_val,
            y0=0, y1=1,
            line=dict(color="#aaa", width=1.5, dash="dash"),
        )
        fig.add_annotation(
            xref="x", yref="paper",
            x=x_val, y=1,
            text=label,
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=10, color="#666"),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc",
            borderwidth=1,
            borderpad=3,
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
    margin=dict(l=0, r=0, t=60, b=0),
    hovermode="x unified",
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    height=460,
)
fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Notes log (read-only)
# ---------------------------------------------------------------------------

if not notes.empty:
    visible_notes = (
        notes[notes["platform"].isin([platform_key, "both"])]
        .copy()
        .sort_values("date", ascending=False)
    )
    if not visible_notes.empty:
        with st.expander(f"Notes ({len(visible_notes)})"):
            display = visible_notes.copy()
            display["date"] = display["date"].dt.strftime("%Y-%m-%d")
            display["platform"] = display["platform"].map(
                lambda p: PLATFORM_DISPLAY.get(p, p)
            )
            st.dataframe(
                display.reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )

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
