import streamlit as st
import pandas as pd
from mplsoccer import Sbapi
import concurrent.futures

@st.cache_resource
def get_api():
    try:
        username = st.secrets["statsbomb"]["username"]
        password = st.secrets["statsbomb"]["password"]
        return Sbapi(username=username, password=password, dataframe=True)
    except Exception:
        return Sbapi(dataframe=True)

@st.cache_data
def load_competitions():
    api = get_api()
    df_comps = api.competition()
    return df_comps

@st.cache_data
def load_matches(competition_id, season_id):
    api = get_api()
    matches = api.match(competition_id, season_id)
    return matches

@st.cache_data(show_spinner="Downloading Player Stats from API...")
def load_player_season_stats(competition_id, season_id):
    import requests
    from requests.auth import HTTPBasicAuth
    
    url = f"https://data.statsbombservices.com/api/v4/competitions/{competition_id}/seasons/{season_id}/player-stats"
    try:
        username = st.secrets["statsbomb"]["username"]
        password = st.secrets["statsbomb"]["password"]
        resp = requests.get(url, auth=HTTPBasicAuth(username, password))
        if resp.status_code == 200:
            df = pd.DataFrame(resp.json())
            df['player_known_name'] = df['player_known_name'].fillna(df['player_name'])
            
            # Ensure columns exist before filtering, in case endpoint format shifts
            # keep_cols = ['player_name', 'team_name', 'player_known_name', 'player_season_minutes', 'primary_position']
            # existing_cols = [c for c in keep_cols if c in df.columns]
            # df = df[existing_cols]
            
            return df
        else:
            st.error(f"Failed to load player stats: HTTP {resp.status_code}")
    except Exception as e:
        st.error(f"API Error fetching player stats: {e}")
        
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def _fetch_team_events(competition_id, season_id, team_name, match_ids=None):
    """Pure data fetch — no Streamlit UI elements so it can be safely cached."""
    if match_ids is not None and len(match_ids) > 0:
        # Use the pre-filtered match IDs directly
        final_match_ids = list(match_ids)
    else:
        # Fall back to loading all matches for the team
        df_matches = load_matches(competition_id, season_id)
        if df_matches is None or df_matches.empty:
            return pd.DataFrame()
        
        # Filter matches involving the team
        team_matches = df_matches[(df_matches['home_team_name'] == team_name) | (df_matches['away_team_name'] == team_name)]
        if team_matches.empty:
            return pd.DataFrame()
        
        if 'match_status' in team_matches.columns:
            final_match_ids = team_matches[team_matches['match_status'] == 'available']['match_id'].tolist()
        else:
            final_match_ids = team_matches['match_id'].tolist()
    
    api = get_api()
        
    def fetch_event(match_id):
        try:
            res = api.event(match_id)
            if res is not None:
                df = res[0]
                
                # Filter to ONLY the specified team's events
                if 'team_name' in df.columns:
                    df = df[(df['team_name'] == team_name) & (df['type_name'] == 'Pass')]
                
                # Filter columns to only those requested
                target_cols = ['type_name', 'sub_type_name', 'outcome_name', 'player_name', 'team_name', 'x', 'y', 'end_x', 'end_y', 'pass_recipient_name', 'obv_for_net', 'play_pattern_name', 'match_id', 'id', 'index']
                existing_cols = [c for c in target_cols if c in df.columns]
                df = df[existing_cols]

                df = df[df['pass_recipient_name'].notna()]
                df = df[~df['sub_type_name'].isin(['Throw-in', 'Corner', 'Free Kick'])]

                return df
        except Exception as e:
            return None

    events_list = []
    total = len(final_match_ids)
    
    if total == 0:
        return pd.DataFrame()
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(fetch_event, mid) for mid in final_match_ids]
        for future in concurrent.futures.as_completed(futures):
            df_ep = future.result()
            if df_ep is not None and not df_ep.empty:
                events_list.append(df_ep)
                
    if events_list:
        return pd.concat(events_list, ignore_index=True)
    return pd.DataFrame()


def load_team_events_from_api(competition_id, season_id, team_name,
                              match_ids=None,
                              _progress_bar=None, _status_text=None):
    """Wrapper that shows progress UI, then delegates to the cached fetch."""
    if _status_text is not None:
        _status_text.text("Downloading events…")
    if _progress_bar is not None:
        _progress_bar.progress(0.0)

    # Convert to tuple for caching compatibility
    match_ids_tuple = tuple(match_ids) if match_ids else None
    df = _fetch_team_events(competition_id, season_id, team_name, match_ids=match_ids_tuple)

    if _progress_bar is not None:
        _progress_bar.progress(1.0)
    if _status_text is not None:
        _status_text.text("Done!")

    return df

# @st.cache_data(show_spinner=False)
# def load_competition_events_from_api(competition_id, season_id, _progress_bar=None, _status_text=None):
#     df_matches = load_matches(competition_id, season_id)
#     if df_matches is None or df_matches.empty:
#         return pd.DataFrame()
        
#     api = get_api()
#     if 'match_status' in df_matches.columns:
#         match_ids = df_matches[df_matches['match_status'] == 'available']['match_id'].tolist()
#     else:
#         match_ids = df_matches['match_id'].tolist()
        
#     def fetch_event(match_id):
#         try:
#             res = api.event(match_id)
#             if res is not None:
#                 df = res[0]
                
#                 # Filter rows where under_pressure == True
#                 if 'under_pressure' in df.columns:
#                     df = df[df['under_pressure'] == True]
#                     df = df[df['sub_type_name'] != 'Aerial Lost']
#                     df = df[df['type_name'].isin(['Carry', 'Pass', 'Dribble', 'Foul Won', 'Dispossessed', 'Miscontrol', 'Shield', 'Error'])]
#                     # Only keep Carries that travelled more than 5 units
#                     if 'type_name' in df.columns:
#                         is_carry = df['type_name'] == 'Carry'
#                         valid_carry = is_carry & (((df['x'] - df['end_x'])**2 + (df['y'] - df['end_y'])**2) > 25)
#                         df = df[~is_carry | valid_carry]
#                 else:
#                     return None
                
#                 # Filter columns to only those requested
#                 target_cols = ['type_name', 'sub_type_name', 'outcome_name', 'player_name', 'team_name', 'under_pressure', 'x', 'y', 'end_x', 'end_y', 'match_id', 'id', 'index']
#                 existing_cols = [c for c in target_cols if c in df.columns]
                
#                 return df[existing_cols]
#         except Exception as e:
#             return None

#     events_list = []
#     total = len(match_ids)
    
#     if total == 0:
#         return pd.DataFrame()
        
#     completed = 0
#     with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
#         futures = [executor.submit(fetch_event, mid) for mid in match_ids]
#         for future in concurrent.futures.as_completed(futures):
#             df_ep = future.result()
#             if df_ep is not None and not df_ep.empty:
#                 events_list.append(df_ep)
                
#             completed += 1
#             if _progress_bar is not None:
#                 _progress_bar.progress(completed / total)
#             if _status_text is not None:
#                 _status_text.text(f"Downloading events: {completed}/{total} matches completed...")
                
#     if events_list:
#         return pd.concat(events_list, ignore_index=True)
#     return pd.DataFrame()