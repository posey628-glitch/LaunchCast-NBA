"""Tests for the NBA data layer — matchup assembly + source fallback logic."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from data import matchup, fetcher, sources


def test_current_season_format():
    s = fetcher.current_season(2025)
    assert s == "2025-26"

def test_matchup_projects_all_stats():
    player = pd.Series({"GP": 40, "MIN": 34.0, "PTS": 27.0, "REB": 6.0,
                        "AST": 7.0, "FG3M": 3.2, "STL": 1.3, "BLK": 0.6, "TOV": 3.1})
    team_opp = pd.DataFrame({"TEAM_ID": [1], "OPP_PTS": [118], "OPP_REB": [46],
                             "OPP_AST": [27], "OPP_FG3M": [14], "OPP_STL": [8],
                             "OPP_BLK": [5], "OPP_TOV": [14]})
    res = matchup.project_player(player, 1, {"team_opponent": team_opp})
    # all 7 stats projected
    assert set(res["projections"].keys()) == set(matchup.STAT_CATEGORIES)
    # each has a projection + matchup multiplier
    for stat, d in res["projections"].items():
        assert "projection" in d and "matchup_mult" in d

def test_weak_defense_boosts_projection():
    player = pd.Series({"GP": 40, "MIN": 34.0, "PTS": 27.0, "REB": 6.0, "AST": 7.0,
                        "FG3M": 3.2, "STL": 1.3, "BLK": 0.6, "TOV": 3.1})
    # team 1 weak (allows lots), team 2 tough (allows little)
    team_opp = pd.DataFrame({"TEAM_ID": [1, 2],
                             "OPP_PTS": [120, 100], "OPP_REB": [46, 40],
                             "OPP_AST": [27, 22], "OPP_FG3M": [15, 10],
                             "OPP_STL": [8, 7], "OPP_BLK": [5, 4], "OPP_TOV": [14, 13]})
    picture = {"team_opponent": team_opp}
    weak = matchup.project_player(player, 1, picture)["projections"]["pts"]["projection"]
    tough = matchup.project_player(player, 2, picture)["projections"]["pts"]["projection"]
    assert weak > tough

def test_missing_data_falls_back_to_league_avg():
    # no team_opponent data → uses league-avg fallback, still projects
    player = pd.Series({"GP": 40, "MIN": 34.0, "PTS": 27.0, "REB": 6.0, "AST": 7.0,
                        "FG3M": 3.2, "STL": 1.3, "BLK": 0.6, "TOV": 3.1})
    res = matchup.project_player(player, 999, {"team_opponent": None})
    assert res["projections"]["pts"]["projection"] > 0

def test_source_health_returns_dict():
    h = sources.source_health()
    assert isinstance(h, dict)
    assert "nba_api_installed" in h
