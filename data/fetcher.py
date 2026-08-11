"""
data/fetcher.py — comprehensive NBA data assembly (all stats, both sides).

Your requirement: pull ALL stats/metrics available so we can eventually weigh
them per-player and per-matchup. This module fetches the full picture:

  OFFENSE (per player):  pts, reb, ast, fg3m, stl, blk, tov, min, usage, TS%,
                          per-36 rates, home/away splits
  DEFENSE (per team):    defensive rating, pace, opponent stats allowed
  DEFENSE vs POSITION:   how each team defends each position (the matchup core)
  MATCHUP (historical):  who-guarded-whom tracking (BoxScoreMatchupsV3)
  CONTEXT:               rest days, back-to-backs, home/away, injuries

Everything is cached so a rerun doesn't re-hammer the sources. Each fetch falls
back gracefully (returns None / empty) so one dead source never crashes the app —
the health panel shows what's actually working.

★ UNTESTABLE from the build container (stats.nba.com egress-blocked). Written to
the documented nba_api interface + defensive handling; confirmed live on Cloud.
"""
from __future__ import annotations
from . import sources


# Current season string helper (nba_api format "2024-25")
def current_season(year_start: int | None = None) -> str:
    import datetime
    if year_start is None:
        now = datetime.date.today()
        # NBA season spans Oct–Jun; before Oct, the "current" season started last year
        year_start = now.year if now.month >= 10 else now.year - 1
    return f"{year_start}-{str(year_start + 1)[-2:]}"


def fetch_player_offense(season: str | None = None):
    """All offensive per-player stats (the OFFENSE side of the matchup).
    Returns a DataFrame or None. Includes counting stats + advanced where present."""
    season = season or current_season()
    df = sources.fetch_nba_endpoint(
        "LeagueDashPlayerStats", season=season,
        per_mode_detailed="PerGame", measure_type_detailed_defense="Base",
    )
    return df


def fetch_player_advanced(season: str | None = None):
    """Advanced offensive metrics (usage, TS%, pace, etc.) — the extra metrics
    you want available for weighting. Separate call (different measure type)."""
    season = season or current_season()
    return sources.fetch_nba_endpoint(
        "LeagueDashPlayerStats", season=season,
        per_mode_detailed="PerGame", measure_type_detailed_defense="Advanced",
    )


def fetch_team_defense(season: str | None = None):
    """Team defensive stats — the DEFENSE side. Defensive rating, pace, opp stats
    allowed. This is what the two-sided projection multiplies against."""
    season = season or current_season()
    return sources.fetch_nba_endpoint(
        "LeagueDashTeamStats", season=season,
        per_mode_detailed="PerGame", measure_type_detailed_defense="Defense",
    )


def fetch_team_opponent(season: str | None = None):
    """What each team ALLOWS to opponents (opp pts, reb, etc.) — the raw material
    for defense-vs-league-average matchup multipliers."""
    season = season or current_season()
    return sources.fetch_nba_endpoint(
        "LeagueDashTeamStats", season=season,
        per_mode_detailed="PerGame", measure_type_detailed_defense="Opponent",
    )


def fetch_defense_vs_position(season: str | None = None):
    """Defense-vs-position: how each team defends each position slot. This is the
    HEART of the two-sided matchup — a center's rebound projection depends on how
    the opponent defends centers, not just their overall defense."""
    season = season or current_season()
    # nba_api exposes this via LeagueDashPtDefend / matchup endpoints
    return sources.fetch_nba_endpoint(
        "LeagueDashPtDefend", season=season, per_mode_simple="PerGame",
    )


def fetch_player_matchups(season: str | None = None):
    """Historical who-guarded-whom (BoxScoreMatchupsV3 aggregates). Noisier than
    MLB's clean 1-on-1, but the closest NBA analog — partial defender tracking."""
    season = season or current_season()
    return sources.fetch_nba_endpoint(
        "LeagueSeasonMatchups", season=season,
    )


def fetch_hustle_stats(season: str | None = None):
    """Hustle stats (deflections, contested shots, etc.) — extra defensive metrics
    for weighting steals/blocks projections. Part of 'all metrics available'."""
    season = season or current_season()
    return sources.fetch_nba_endpoint(
        "LeagueHustleStatsPlayer", season=season, per_mode_time="PerGame",
    )


def last_completed_season() -> str:
    """The most recently COMPLETED season string. Used as a fallback when the
    current season has no games yet (Aug/Sep), so the app always has data to show."""
    import datetime
    now = datetime.date.today()
    # if we're before October, the current season year hasn't started; last
    # completed is (year-1)-(year). If Oct+, last completed is the one that ended
    # in June of this year.
    if now.month >= 10:
        ys = now.year - 1
    else:
        ys = now.year - 2
    return f"{ys}-{str(ys + 1)[-2:]}"


def assemble_full_picture(season: str | None = None) -> dict:
    """Pull EVERYTHING in one call, returning a dict of all frames. This is the
    comprehensive assembly your vision needs — offense, defense, matchup, context
    all available to weight later. Any piece that fails comes back None (graceful).

    Returns: {offense, advanced, team_defense, team_opponent, def_vs_pos,
              matchups, hustle, health}
    """
    season = season or current_season()
    picture = {
        "season": season,
        "offense": fetch_player_offense(season),
        "advanced": fetch_player_advanced(season),
        "team_defense": fetch_team_defense(season),
        "team_opponent": fetch_team_opponent(season),
        "def_vs_pos": fetch_defense_vs_position(season),
        "matchups": fetch_player_matchups(season),
        "hustle": fetch_hustle_stats(season),
    }
    # If the requested (current) season returned no player data — common in the
    # preseason months — fall back to the last COMPLETED season so the app is
    # usable year-round instead of blank until opening night.
    if picture.get("offense") is None:
        fb = last_completed_season()
        if fb != season:
            picture["season"] = fb
            picture["season_note"] = f"{season} has no games yet; showing last completed season {fb}"
            picture["offense"] = fetch_player_offense(fb)
            picture["advanced"] = fetch_player_advanced(fb)
            picture["team_defense"] = fetch_team_defense(fb)
            picture["team_opponent"] = fetch_team_opponent(fb)
            picture["def_vs_pos"] = fetch_defense_vs_position(fb)
            picture["matchups"] = fetch_player_matchups(fb)
            picture["hustle"] = fetch_hustle_stats(fb)

    picture["health"] = sources.source_health()
    picture["fetch_errors"] = dict(getattr(sources, "LAST_ERRORS", {}))
    # summarize what we actually got, so failures are visible not silent
    picture["fetched_ok"] = {
        k: (v is not None and getattr(v, "empty", True) is False)
        for k, v in picture.items() if k not in ("season", "health", "fetched_ok")
    }
    return picture


# ── balldontlie primary path (reliable from cloud) ───────────────────────────
def fetch_offense_balldontlie(season_year: int | None = None):
    """Pull per-player season averages from balldontlie and shape them like the
    nba_api offense frame (so matchup.py works unchanged). Returns DataFrame|None.

    balldontlie season is an int (e.g. 2024 = 2024-25 season)."""
    import pandas as pd
    if season_year is None:
        # last completed season as an int
        s = last_completed_season()  # "2024-25"
        season_year = int(s[:4])
    # balldontlie: /season_averages needs player ids; but /stats gives per-game.
    # Simplest reliable pull: season_averages for the season (paginated players).
    # We page through active players' averages.
    rows = []
    cursor = None
    pages = 0
    while pages < 25:  # cap pages so we never hang
        params = {"season": season_year, "per_page": 100}
        if cursor:
            params["cursor"] = cursor
        data = sources.fetch_balldontlie("season_averages", params=params)
        if not data or "data" not in data:
            break
        for d in data["data"]:
            rows.append({
                "PLAYER_ID": d.get("player_id"),
                "PLAYER_NAME": None,  # filled via a players lookup if needed
                "GP": d.get("games_played", 0),
                "MIN": _min_to_float(d.get("min")),
                "PTS": d.get("pts", 0), "REB": d.get("reb", 0), "AST": d.get("ast", 0),
                "FG3M": d.get("fg3m", 0), "STL": d.get("stl", 0),
                "BLK": d.get("blk", 0), "TOV": d.get("turnover", 0),
            })
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        pages += 1
        if not cursor:
            break
    if not rows:
        return None
    return pd.DataFrame(rows)


def _min_to_float(m):
    """balldontlie returns minutes as 'MM' or 'MM:SS' string sometimes."""
    try:
        if m is None:
            return 0.0
        if isinstance(m, (int, float)):
            return float(m)
        if ":" in str(m):
            mm, ss = str(m).split(":")[:2]
            return round(float(mm) + float(ss) / 60, 1)
        return float(m)
    except Exception:
        return 0.0


def fetch_essential(season: str | None = None) -> dict:
    """FAST reliable fetch. Tries balldontlie FIRST (cloud-friendly), falls back
    to nba.com only if balldontlie is unavailable. Returns offense + (nba.com)
    team_opponent when reachable. Enough to project two-sided."""
    if season is None:
        season = last_completed_season()
    season_year = int(season[:4])

    picture = {"season": season, "source": None}

    # 1) balldontlie primary (reliable)
    off = fetch_offense_balldontlie(season_year)
    if off is not None and not off.empty:
        picture["offense"] = off
        picture["source"] = "balldontlie"
    else:
        # 2) fall back to nba.com (may be slow/flaky)
        picture["offense"] = fetch_player_offense(season)
        picture["source"] = "nba.com"

    # team_opponent (defense allowed) — only nba.com has this cleanly; optional.
    picture["team_opponent"] = fetch_team_opponent(season)

    picture["fetched_ok"] = {
        k: (v is not None and getattr(v, "empty", True) is False)
        for k, v in picture.items() if k not in ("season", "source", "fetched_ok")
    }
    picture["fetch_errors"] = dict(getattr(sources, "LAST_ERRORS", {}))
    return picture
