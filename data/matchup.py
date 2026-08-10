"""
data/matchup.py — assemble two-sided per-player-per-game projections.

This is where OFFENSE meets DEFENSE: it takes the comprehensive data picture and,
for each player in a given slate, produces projections for ALL stat categories by
combining the player's shrunk rates with the specific defense they face — the
hitter-vs-pitcher analysis, translated to NBA.

★ The "weigh metrics per player + matchup" goal starts here: every stat gets a
two-sided projection. Later phases add the LEARNED weighting (which metrics
actually predict, via tier-backtesting) — but only once real games validate it.
"""
from __future__ import annotations
from core import scoring

# All stat categories we project (your full list).
STAT_CATEGORIES = ["pts", "reb", "ast", "fg3m", "stl", "blk", "tov"]

# Map our stat keys → the column names nba_api uses (per-game Base).
NBA_COLS = {
    "pts": "PTS", "reb": "REB", "ast": "AST", "fg3m": "FG3M",
    "stl": "STL", "blk": "BLK", "tov": "TOV", "min": "MIN", "gp": "GP",
}


def _safe(row, col, default=0.0):
    try:
        import pandas as pd
        v = row.get(col, default)
        return float(v) if v is not None and not pd.isna(v) else default
    except Exception:
        return default


def league_avg_allowed(team_opponent_df, stat: str) -> float:
    """League-average amount of `stat` allowed (denominator for the matchup
    multiplier). Falls back to the scoring module's prior if data absent."""
    try:
        col = "OPP_" + NBA_COLS[stat]
        if team_opponent_df is not None and col in team_opponent_df.columns:
            import pandas as pd
            vals = pd.to_numeric(team_opponent_df[col], errors="coerce").dropna()
            if len(vals):
                return float(vals.mean())
    except Exception:
        pass
    return float(scoring.LEAGUE_AVG.get(stat, 1.0))


def team_allowed(team_opponent_df, team_id, stat: str, league_fallback: float) -> float:
    """How much `stat` a specific opponent team allows. Falls back to league avg."""
    try:
        col = "OPP_" + NBA_COLS[stat]
        if team_opponent_df is not None and "TEAM_ID" in team_opponent_df.columns:
            row = team_opponent_df[team_opponent_df["TEAM_ID"] == team_id]
            if not row.empty and col in row.columns:
                import pandas as pd
                v = pd.to_numeric(row.iloc[0][col], errors="coerce")
                if not pd.isna(v):
                    return float(v)
    except Exception:
        pass
    return league_fallback


def project_player(player_row, opp_team_id, picture,
                   proj_minutes=None, pace_factor=1.0) -> dict:
    """Two-sided projection for ONE player facing ONE opponent, across ALL stats.
    Returns {stat: {projection, ...}} plus the inputs used (for transparency)."""
    team_opp = picture.get("team_opponent")
    gp = _safe(player_row, NBA_COLS["gp"], 1)
    season_min = _safe(player_row, NBA_COLS["min"], scoring.LEAGUE_AVG["min"])
    out = {"projections": {}, "inputs": {"gp": gp, "season_min": season_min}}

    for stat in STAT_CATEGORIES:
        col = NBA_COLS[stat]
        player_rate = _safe(player_row, col, scoring.LEAGUE_AVG.get(stat, 0.0))
        lg_allowed = league_avg_allowed(team_opp, stat)
        opp_allowed = team_allowed(team_opp, opp_team_id, stat, lg_allowed)
        proj = scoring.project_stat(
            player_rate=player_rate, games_played=gp, stat=stat,
            opp_allowed=opp_allowed, league_allowed=lg_allowed,
            proj_minutes=proj_minutes, season_avg_minutes=season_min,
            pace_factor=pace_factor,
        )
        out["projections"][stat] = {
            "projection": proj,
            "player_rate": round(player_rate, 2),
            "opp_allowed": round(opp_allowed, 2),
            "league_allowed": round(lg_allowed, 2),
            "matchup_mult": round(scoring.defense_multiplier(opp_allowed, lg_allowed), 3),
        }
    return out
