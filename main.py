import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from data_loader import load_competitions, load_matches, load_team_events_from_api, load_player_season_stats
import datetime
from visuals import plot_combined_network

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Teammate Connection",
    page_icon="⚽",
    layout="wide",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1724 0%, #1a2540 100%);
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown label {
    color: #e2e8f0;
}

/* Accent button */
div.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.55rem 2.2rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    transition: transform 0.15s, box-shadow 0.2s;
    width: 100%;
}
div.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(99,102,241,0.45);
}

/* Dataframe header */
.main .block-container h2 {
    background: linear-gradient(90deg, #6366f1, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Card-like container for dataframe */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 12px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar controls ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ Teammate Connection")
    st.markdown("---")

    # 1. Load competitions
    df_comps = load_competitions()

    # Build a display label: "competition_name"
    df_comps["display"] = df_comps["competition_name"]
    comp_options = df_comps["display"].drop_duplicates().sort_values().tolist()

    selected_comp = st.selectbox("🏆 Competition", comp_options, index=0)

    # 2. Seasons for selected competition
    comp_rows = df_comps[df_comps["display"] == selected_comp]
    season_options = comp_rows["season_name"].drop_duplicates().sort_values().tolist()
    selected_season = st.selectbox("📅 Season", season_options, index=0)

    # Resolve IDs
    id_row = comp_rows[comp_rows["season_name"] == selected_season].iloc[0]
    competition_id = int(id_row["competition_id"])
    season_id = int(id_row["season_id"])

    # 3. Teams for that competition/season
    df_matches = load_matches(competition_id, season_id)
    home_teams = df_matches["home_team_name"].unique().tolist() if "home_team_name" in df_matches.columns else []
    away_teams = df_matches["away_team_name"].unique().tolist() if "away_team_name" in df_matches.columns else []
    all_teams = sorted(set(home_teams + away_teams))

    selected_team = st.selectbox("🏟️ Team", all_teams, index=0)

    # 4. Date range filter (opt-in)
    st.markdown("---")
    use_date_filter = st.checkbox("📆 Filter by match date", value=False)
    if use_date_filter and "match_date" in df_matches.columns and not df_matches.empty:
        min_date = df_matches["match_date"].min().date()
        max_date = df_matches["match_date"].max().date()
        date_range = st.date_input(
            "Select date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="date_range",
        )
        # Ensure we have both start and end (user might have only picked one so far)
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date

        # Filter matches by the selected date range
        mask = (
            (df_matches["match_date"].dt.date >= start_date)
            & (df_matches["match_date"].dt.date <= end_date)
        )
        df_matches_filtered = df_matches[mask]
        st.caption(f"{len(df_matches_filtered)} of {len(df_matches)} matches in range")
    else:
        df_matches_filtered = df_matches

    # Resolve filtered match IDs for the selected team
    team_mask = (
        (df_matches_filtered["home_team_name"] == selected_team)
        | (df_matches_filtered["away_team_name"] == selected_team)
    )
    filtered_match_ids = df_matches_filtered.loc[team_mask, "match_id"].tolist()

    st.markdown("---")
    load_btn = st.button("🚀 Load Data", use_container_width=True)

# ── Main area ────────────────────────────────────────────────────────────────
st.markdown("# 🔗 Teammate Connection Explorer")
st.caption("Select a competition, season, and team from the sidebar, then click **Load Data**.")

if load_btn:
    progress_bar = st.progress(0)
    status_text = st.empty()

    # ── Load event data ──────────────────────────────────────────────────
    status_text.text("Fetching events…")
    df_events = load_team_events_from_api(
        competition_id,
        season_id,
        selected_team,
        match_ids=filtered_match_ids,
        _progress_bar=progress_bar,
        _status_text=status_text,
    )

    if df_events is not None and not df_events.empty:
        st.session_state["df_events"] = df_events
        st.session_state["loaded_team"] = selected_team
        st.session_state["loaded_comp"] = selected_comp
        st.session_state["loaded_season"] = selected_season
        st.success(f"✅ Loaded **{len(df_events):,}** events for **{selected_team}**")
    else:
        st.warning("No event data found for this selection.")

    # ── Load player season stats ─────────────────────────────────────────
    status_text.text("Fetching player season stats…")
    df_player_season = load_player_season_stats(competition_id, season_id)
    if df_player_season is not None and not df_player_season.empty:
        if 'team_name' in df_player_season.columns:
            df_player_season = df_player_season[df_player_season['team_name'] == selected_team]
        st.session_state["df_player_season"] = df_player_season
        st.success(f"✅ Loaded player season stats for **{selected_team}** ({len(df_player_season)} players)")
    else:
        st.warning("No player season data found for this selection.")

    progress_bar.empty()
    status_text.empty()

# Show data if already loaded
meta = (
    f"**{st.session_state.get('loaded_comp', '')}** · "
    f"**{st.session_state.get('loaded_season', '')}** · "
    f"**{st.session_state.get('loaded_team', '')}**"
)

# ── Pass Network Visualization ───────────────────────────────────────────────
if "df_events" in st.session_state:
    st.markdown("---")
    st.markdown(f"### 🕸️ Pass Network Visualization — {meta}")

    df_ev = st.session_state["df_events"]
    player_list = sorted(df_ev["player_name"].dropna().unique().tolist())

    selected_player = st.selectbox("🎯 Select Player", player_list, index=0, key="player_select")

    # Build name_map and resolve passer known_name from player_season data
    known_name = None
    name_map = {}
    if "df_player_season" in st.session_state:
        df_ps_lookup = st.session_state["df_player_season"]
        if "player_known_name" in df_ps_lookup.columns and "player_name" in df_ps_lookup.columns:
            # Full mapping for all players on the team
            name_map = dict(zip(df_ps_lookup["player_name"], df_ps_lookup["player_known_name"]))
            known_name = name_map.get(selected_player)

    display_name = known_name or selected_player
    st.markdown(f"### 🔗 {display_name} Teammate Connection")

    fig = plot_combined_network(
        df_ev,
        selected_player,
        player_known_name=known_name,
        name_map=name_map,
        team_name=st.session_state.get("loaded_team", ""),
        comp_name=st.session_state.get("loaded_comp", ""),
        season_label=st.session_state.get("loaded_season", ""),
    )
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
