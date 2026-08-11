"""
LaunchCast NBA — two-sided NBA prop deep-dive.
Phase 2 skeleton: data layer + two-sided projections wired to a minimal UI.
Points is the validated anchor; other stats project too but aren't tuned yet.
"""
import streamlit as st
import pandas as pd
from data import fetcher, matchup
from data import sources

st.set_page_config(page_title="LaunchCast NBA", page_icon="🏀", layout="wide")
st.title("🏀 LaunchCast NBA")
st.caption("Two-sided (offense × defense) NBA prop analysis. Phase 2 — data layer live. "
           "Projections are principled starting points; not yet validated (season starts Oct).")

# Owner mode (same pattern as MLB/NFL)
OWNER_KEY = ""
try:
    OWNER_KEY = st.secrets.get("owner_key", "")
except Exception:
    pass
owner_mode = False
try:
    if st.query_params.get("owner", "") == OWNER_KEY and OWNER_KEY:
        owner_mode = True
except Exception:
    pass

with st.expander("🔌 Data source health", expanded=False):
    st.caption("Which sources are reachable. On Streamlit Cloud these should be green; "
               "in restricted networks they may show unreachable.")
    if st.button("Check sources"):
        h = sources.source_health()
        st.json(h)

st.markdown("### Slate projections")
season = fetcher.current_season()
st.write(f"Season: **{season}**")

if st.button("Fetch league data (offense + defense)"):
    with st.spinner("Pulling comprehensive data (throttled)…"):
        picture = fetcher.assemble_full_picture(season)
    st.session_state["_picture"] = picture
    ok = picture.get("fetched_ok", {})
    got = [k for k, v in ok.items() if v]
    missing = [k for k, v in ok.items() if not v]
    if got:
        st.success(f"Fetched: {', '.join(got)}")
    if missing:
        st.warning(f"Unavailable: {', '.join(missing)}")
    # show the REAL reason each missing fetch failed (no more silent 'unavailable')
    ferr = picture.get("fetch_errors") or {}
    if ferr:
        with st.expander("Why did some fetches fail? (real errors)", expanded=True):
            for ep, msg in ferr.items():
                st.text(f"{ep}: {msg}")
    if picture.get("season_note"):
        st.info(picture["season_note"])

picture = st.session_state.get("_picture")
if picture and picture.get("offense") is not None:
    off = picture["offense"]
    st.write(f"{len(off)} players loaded. Pick a player to see two-sided projections.")
    if "PLAYER_NAME" in off.columns:
        name = st.selectbox("Player", sorted(off["PLAYER_NAME"].dropna().unique()))
        team_opp = picture.get("team_opponent")
        opp_options = {}
        if team_opp is not None and "TEAM_ID" in team_opp.columns:
            tname = "TEAM_NAME" if "TEAM_NAME" in team_opp.columns else "TEAM_ID"
            opp_options = {str(r[tname]): r["TEAM_ID"] for _, r in team_opp.iterrows()}
        opp_label = st.selectbox("Opponent defense", list(opp_options.keys()) or ["(no team data)"])
        opp_id = opp_options.get(opp_label, 0)
        prow = off[off["PLAYER_NAME"] == name].iloc[0]
        proj = matchup.project_player(prow, opp_id, picture)
        rows = [{"Stat": s.upper(), "Projection": d["projection"],
                 "Player rate": d["player_rate"], "Matchup ×": d["matchup_mult"]}
                for s, d in proj["projections"].items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Click 'Fetch league data' to load the slate. (Requires open network — works on Streamlit Cloud.)")

if owner_mode:
    st.divider()
    st.markdown("#### 🔧 Owner tools")
    st.caption("Owner-only diagnostics will go here as the app grows.")
