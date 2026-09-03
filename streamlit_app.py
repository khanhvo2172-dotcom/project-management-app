"""
SEO Project Management — a simple visual tracker.

Data source (in order of preference):
  1. A Google Sheet, when service-account credentials are set in st.secrets.
  2. data/sample_tasks.csv bundled in the repo (so the app always renders).

UI: white background, black text, light icons. English labels.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------- #
# Page + styling
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="SEO Project Management",
    page_icon="📌",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp { background-color: #ffffff; color: #111111; }
      section[data-testid="stSidebar"] { background-color: #fafafa; border-right: 1px solid #eaeaea; }
      h1, h2, h3, h4, h5, h6, p, span, label, div { color: #111111; }
      /* KPI cards */
      div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #ececec;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
      }
      div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
      .stTabs [data-baseweb="tab"] { font-weight: 600; }
      .block-container { padding-top: 2rem; }
      /* Legible filter chips: force a light background + dark text on the
         selected multiselect tags (default theme paints them primaryColor
         black -> black-on-black). Streamlit >=1.59 renders them inside
         stMultiSelectTagsContainer; the [data-baseweb="tag"] rule covers
         older versions. */
      [data-testid="stMultiSelectTagsContainer"] span[role="group"] > span,
      [data-baseweb="tag"] {
        background-color: #e9e9e9 !important;
        border: 1px solid #d5d5d5 !important;
      }
      [data-testid="stMultiSelectTagsContainer"] span[role="group"] > span,
      [data-testid="stMultiSelectTagsContainer"] span[role="group"] > span *,
      [data-baseweb="tag"],
      [data-baseweb="tag"] * { color: #111111 !important; }
      [data-testid="stMultiSelectTagsContainer"] svg,
      [data-baseweb="tag"] svg { fill: #111111 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Icons for each SEO category (purely cosmetic).
CATEGORY_ICONS = {
    "Traffic (Organic Clicks)": "📈",
    "CMS Setup": "🔑",
    "Content Audit": "🔍",
    "Content Production": "✍️",
    "On-page SEO": "🧩",
    "SEO Audit": "🩺",
    "Technical SEO": "⚙️",
    "Backlink Management": "🔗",
}
STATUS_ICONS = {
    "Not started": "⚪",
    "In progress": "🔵",
    "Done": "✅",
    "At risk": "🔴",
}
EXPECTED_COLS = [
    "Task", "Category", "Detail", "Duration", "PIC", "Start Date", "End Date",
    "Result Number", "Result Unit", "Actual Number", "Frequency", "Status",
]

DATA_FILE = Path(__file__).parent / "data" / "sample_tasks.csv"


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _build_credentials():
    """Build Google credentials from secrets.

    Prefers OAuth user credentials ([google_oauth], auto-refreshing via the
    refresh token); falls back to a service account ([gcp_service_account]).
    """
    if "google_oauth" in st.secrets:
        from google.oauth2.credentials import Credentials as UserCredentials

        o = st.secrets["google_oauth"]
        # Use the exact scopes the token was granted; passing a different set
        # (e.g. spreadsheets.readonly when 'spreadsheets' was granted) makes the
        # refresh fail with invalid_scope. None => refresh keeps granted scopes.
        scopes = list(o["scopes"]) if "scopes" in o else None
        return UserCredentials(
            token=o.get("token"),
            refresh_token=o["refresh_token"],
            token_uri=o.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=o["client_id"],
            client_secret=o["client_secret"],
            scopes=scopes,
        )
    if "gcp_service_account" in st.secrets:
        from google.oauth2.service_account import Credentials as ServiceCredentials

        return ServiceCredentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=DEFAULT_SCOPES
        )
    return None


@st.cache_data(ttl=300, show_spinner=False)
def load_from_sheet() -> pd.DataFrame | None:
    """Read tasks from a Google Sheet if secrets are configured, else None."""
    if "sheet" not in st.secrets:
        return None
    creds = _build_credentials()
    if creds is None:
        return None
    import gspread

    gc = gspread.authorize(creds)
    cfg = st.secrets["sheet"]
    sh = gc.open_by_url(cfg["url"]) if "url" in cfg else gc.open_by_key(cfg["key"])
    ws = sh.worksheet(cfg.get("worksheet", "Tasks"))
    records = ws.get_all_records()
    return pd.DataFrame(records)


@st.cache_data(show_spinner=False)
def load_from_csv() -> pd.DataFrame:
    return pd.read_csv(DATA_FILE, dtype=str).fillna("")


def get_data() -> tuple[pd.DataFrame, str]:
    try:
        df = load_from_sheet()
        if df is not None and not df.empty:
            return df, "google_sheet"
    except Exception as exc:  # noqa: BLE001 - surface, but fall back gracefully
        st.warning(f"Could not read the Google Sheet, showing sample data instead. ({exc})")
    return load_from_csv(), "sample_csv"


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #
def duration_to_offset(text: str) -> pd.DateOffset | None:
    """'6 months' / '2 weeks' / '5 days' -> a pandas offset."""
    if not isinstance(text, str) or not text.strip():
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    try:
        n = int(float(parts[0]))
    except ValueError:
        return None
    unit = parts[1].lower()
    if unit.startswith("month"):
        return pd.DateOffset(months=n)
    if unit.startswith("week"):
        return pd.DateOffset(weeks=n)
    if unit.startswith("day"):
        return pd.DateOffset(days=n)
    return None


def to_num(val) -> float | None:
    if val is None or (isinstance(val, str) and not val.strip()):
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return None


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Make sure every expected column exists.
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = ""
    df = df[[c for c in EXPECTED_COLS if c in df.columns]]

    df["Start"] = pd.to_datetime(df["Start Date"], errors="coerce")
    manual_end = pd.to_datetime(df["End Date"], errors="coerce")

    # End Date = Start + Duration; fall back to the manual End Date column.
    computed_end = []
    for start, dur in zip(df["Start"], df["Duration"]):
        off = duration_to_offset(dur)
        computed_end.append(start + off if (pd.notna(start) and off is not None) else pd.NaT)
    df["End"] = pd.Series(computed_end)
    df["End"] = df["End"].fillna(manual_end)

    df["Committed"] = df["Result Number"].map(to_num)
    df["Actual"] = df["Actual Number"].map(to_num)

    def pct(row):
        c, a, status = row["Committed"], row["Actual"], row.get("Status", "")
        if pd.notna(c) and c > 0 and pd.notna(a):
            return round(min(a / c * 100, 100), 1)
        if str(status).strip().lower() == "done":
            return 100.0
        return None  # no measurable progress → empty bar

    df["Progress"] = df.apply(pct, axis=1)
    df["Status"] = df["Status"].replace("", "In progress")
    return df


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
raw, source = get_data()
df = prepare(raw)

# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("📌 SEO Project Management")
badge = (
    "🟢 Live from Google Sheet" if source == "google_sheet"
    else "🟡 Sample data — connect a Google Sheet in app secrets to go live"
)
st.caption(badge)

# --------------------------------------------------------------------------- #
# Sidebar filters
# --------------------------------------------------------------------------- #
st.sidebar.header("🔎 Filters")
search = st.sidebar.text_input("Search task / detail", "")
cats = sorted(df["Category"].dropna().unique().tolist())
pics = sorted([p for p in df["PIC"].dropna().unique().tolist() if p])
stats = sorted(df["Status"].dropna().unique().tolist())

sel_cats = st.sidebar.multiselect("Category", cats, default=cats)
sel_pics = st.sidebar.multiselect("Owner (PIC)", pics, default=pics)
sel_stats = st.sidebar.multiselect("Status", stats, default=stats)

mask = (
    df["Category"].isin(sel_cats)
    & df["PIC"].isin(sel_pics + [""])  # keep blank-PIC rows visible
    & df["Status"].isin(sel_stats)
)
if search.strip():
    s = search.strip().lower()
    mask &= (df["Task"].str.lower().str.contains(s, na=False)
             | df["Detail"].str.lower().str.contains(s, na=False))
fdf = df[mask].reset_index(drop=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

# --------------------------------------------------------------------------- #
# KPI cards
# --------------------------------------------------------------------------- #
measurable = fdf[fdf["Committed"].notna() & (fdf["Committed"] > 0)]
avg_prog = measurable["Progress"].dropna().mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📋 Tasks", len(fdf))
c2.metric("🔵 In progress", int((fdf["Status"] == "In progress").sum()))
c3.metric("✅ Done", int((fdf["Status"] == "Done").sum()))
c4.metric("🎯 Measurable KPIs", len(measurable))
c5.metric("📊 Avg progress", f"{avg_prog:.0f}%" if pd.notna(avg_prog) else "—")

st.markdown("")

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_tasks, tab_timeline, tab_overview = st.tabs(["📋 Tasks", "🗓️ Timeline", "📈 Overview"])

# ---- Tasks table --------------------------------------------------------- #
with tab_tasks:
    show = fdf.copy()
    show["Category"] = show["Category"].map(lambda c: f"{CATEGORY_ICONS.get(c, '•')} {c}")
    show["Status"] = show["Status"].map(lambda s: f"{STATUS_ICONS.get(s, '•')} {s}")

    def result_text(row):
        c, u = row["Committed"], row["Result Unit"]
        if pd.isna(c):
            return "—"
        a = row["Actual"]
        if pd.notna(a):
            return f"{int(a):,} / {int(c):,} {u}".strip()
        return f"{int(c):,} {u}".strip()

    show["Result (actual / committed)"] = fdf.apply(result_text, axis=1)
    show["Start"] = fdf["Start"].dt.strftime("%d %b %Y")
    show["End"] = fdf["End"].dt.strftime("%d %b %Y")

    display_cols = [
        "Task", "Category", "PIC", "Duration", "Start", "End",
        "Result (actual / committed)", "Progress", "Status", "Detail",
    ]
    st.dataframe(
        show[display_cols],
        width="stretch",
        hide_index=True,
        column_config={
            "Task": st.column_config.TextColumn("Task", width="large"),
            "Detail": st.column_config.TextColumn("Notes", width="medium"),
            "Progress": st.column_config.ProgressColumn(
                "Progress", min_value=0, max_value=100, format="%d%%"
            ),
        },
    )
    st.caption(f"{len(fdf)} of {len(df)} tasks shown.")

# ---- Timeline (Gantt) ---------------------------------------------------- #
with tab_timeline:
    tdf = fdf[fdf["Start"].notna() & fdf["End"].notna()].copy()
    if tdf.empty:
        st.info("No tasks have both a Start Date and an End/Duration yet.")
    else:
        tdf = tdf.sort_values("Start").reset_index(drop=True)

        # Unique display label per row (zero-width spaces disambiguate tasks
        # whose first 60 chars collide, without changing what you see).
        labels, seen = [], set()
        for task in tdf["Task"]:
            lbl = str(task)[:60]
            while lbl in seen:
                lbl += "​"
            seen.add(lbl)
            labels.append(lbl)
        tdf["Label"] = labels

        GREEN, YELLOW, RED = "#2ca02c", "#f5a623", "#e5484d"

        # Each task becomes 1-2 horizontal segments: a green "Completed" part
        # sized to its % progress plus a yellow "In progress" remainder.
        # Not-started tasks are a single red bar; done tasks a single green bar.
        segs = []
        for _, r in tdf.iterrows():
            start, end, label = r["Start"], r["End"], r["Label"]
            span = end - start
            p, committed = r["Progress"], r["Committed"]
            done = str(r["Status"]).strip().lower() == "done" or (pd.notna(p) and p >= 100)
            base = dict(Label=label, Task=str(r["Task"])[:80], PIC=r["PIC"], Duration=r["Duration"])
            if done:
                segs.append({**base, "Start": start, "End": end, "Seg": "Completed", "Progress": "100%"})
            elif pd.notna(p) and p > 0:
                split = start + span * (min(p, 100) / 100.0)
                segs.append({**base, "Start": start, "End": split, "Seg": "Completed", "Progress": f"{p:.0f}%"})
                segs.append({**base, "Start": split, "End": end, "Seg": "In progress", "Progress": f"{p:.0f}%"})
            elif pd.notna(committed) and committed > 0:
                segs.append({**base, "Start": start, "End": end, "Seg": "Not started", "Progress": "0%"})
            else:
                segs.append({**base, "Start": start, "End": end, "Seg": "In progress", "Progress": "—"})
        sdf = pd.DataFrame(segs)

        color_map = {"Completed": GREEN, "In progress": YELLOW, "Not started": RED}
        fig = px.timeline(
            sdf, x_start="Start", x_end="End", y="Label", color="Seg",
            color_discrete_map=color_map,
            category_orders={
                "Seg": ["Completed", "In progress", "Not started"],
                "Label": tdf["Label"].tolist()[::-1],  # first task on top
            },
            hover_data={"Task": True, "PIC": True, "Duration": True,
                        "Progress": True, "Seg": True, "Label": False},
        )
        fig.update_yaxes(autorange="reversed", title="")

        min_start, max_end = tdf["Start"].min(), tdf["End"].max()

        # Alternating month background bands + a month-name row beneath the axis.
        month = pd.Timestamp(year=min_start.year, month=min_start.month, day=1)
        i = 0
        while month <= max_end:
            nxt = month + pd.DateOffset(months=1)
            b0, b1 = max(month, min_start), min(nxt, max_end)
            if b0 < b1:
                if i % 2 == 1:
                    fig.add_vrect(x0=b0, x1=b1, fillcolor="#f4f4f4", opacity=1,
                                  line_width=0, layer="below")
                fig.add_annotation(x=b0 + (b1 - b0) / 2, y=0, xref="x", yref="paper",
                                   yshift=-42,  # fixed px below the axis, independent of height
                                   text=month.strftime("%b %Y") if month.month in (1, 7) else month.strftime("%b"),
                                   showarrow=False, font=dict(size=13, color="#111111"), yanchor="top")
            month, i = nxt, i + 1

        fig.update_layout(
            height=max(420, 28 * len(tdf)),
            plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            font_color="#111111", legend_title_text="Progress",
            margin=dict(l=10, r=10, t=30, b=76),
            bargap=0.3,
        )
        # Weekly day-number ticks, anchored at the first Start Date.
        fig.update_xaxes(
            range=[min_start, max_end + pd.Timedelta(days=1)],
            gridcolor="#eeeeee", dtick=7 * 24 * 60 * 60 * 1000,
            tick0=min_start.strftime("%Y-%m-%d"),
            tickformat="%d", tickangle=0, ticks="outside",
            tickfont=dict(size=10),
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "Each bar fills green by % completed, yellow for the remainder; "
            "red = not started, full green = done. Shaded bands mark months; "
            "tick numbers are day-of-month (weekly, from the first start date)."
        )

# ---- Overview charts ----------------------------------------------------- #
with tab_overview:
    o1, o2 = st.columns(2)
    with o1:
        st.subheader("Tasks by category")
        by_cat = fdf["Category"].value_counts().reset_index()
        by_cat.columns = ["Category", "Tasks"]
        fig1 = px.bar(by_cat, x="Tasks", y="Category", orientation="h", text="Tasks")
        fig1.update_traces(marker_color="#111111", textposition="outside")
        fig1.update_layout(
            height=380, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            font_color="#111111", yaxis_title="", xaxis_title="",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        fig1.update_yaxes(autorange="reversed")
        st.plotly_chart(fig1, width="stretch")
    with o2:
        st.subheader("Tasks by owner (PIC)")
        by_pic = fdf[fdf["PIC"] != ""]["PIC"].value_counts().reset_index()
        by_pic.columns = ["PIC", "Tasks"]
        fig2 = px.pie(by_pic, names="PIC", values="Tasks", hole=0.5)
        fig2.update_layout(
            height=380, paper_bgcolor="#ffffff", font_color="#111111",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig2, width="stretch")

    st.subheader("Progress on measurable KPIs")
    if measurable.empty:
        st.info("No measurable KPIs (tasks with a committed number) in the current filter.")
    else:
        mv = measurable.copy()
        mv["Progress"] = mv["Progress"].fillna(0)
        mv = mv.sort_values("Progress")
        fig3 = px.bar(mv, x="Progress", y="Task", orientation="h",
                      range_x=[0, 100], text=mv["Progress"].map(lambda v: f"{v:.0f}%"))
        fig3.update_traces(marker_color="#111111", textposition="outside")
        fig3.update_layout(
            height=max(320, 30 * len(mv)), plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff", font_color="#111111",
            yaxis_title="", xaxis_title="% complete",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig3, width="stretch")

st.markdown("---")
st.caption("Built for SEO project tracking · edit the connected Google Sheet and hit Refresh to update.")
