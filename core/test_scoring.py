"""Tests for NBA core scoring — locks in the two-sided matchup + shrinkage logic."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import scoring as s


def test_shrinkage_pulls_small_samples():
    # 3 games at 35ppg should shrink well below 35 toward league avg
    hot = s.shrink(35.0, 3, "pts")
    assert hot < 25, f"small sample not shrunk enough: {hot}"
    # 60 games should stay close to observed
    full = s.shrink(35.0, 60, "pts")
    assert full > 30, f"full season over-shrunk: {full}"

def test_shrinkage_zero_games_returns_league_avg():
    assert s.shrink(99.0, 0, "pts") == s.LEAGUE_AVG["pts"]

def test_defense_multiplier_clamped():
    # extreme favorable matchup still clamped at 1.25
    assert s.defense_multiplier(100, 20) == 1.25
    # extreme tough matchup clamped at 0.80
    assert s.defense_multiplier(1, 20) == 0.80
    # neutral matchup ~1.0
    assert abs(s.defense_multiplier(23, 23) - 1.0) < 0.01

def test_minutes_factor_scales_and_clamps():
    # double minutes clamped at 1.6
    assert s.minutes_factor(72, 30) == 1.6
    # normal minutes ~1.0
    assert abs(s.minutes_factor(34, 34) - 1.0) < 0.01

def test_two_sided_projection_swings_with_matchup():
    good = s.project_stat(28, 40, "pts", opp_allowed=26, league_allowed=23)
    bad = s.project_stat(28, 40, "pts", opp_allowed=19, league_allowed=23)
    assert good > bad, "favorable matchup should project higher"

def test_rare_stats_shrink_harder():
    # blocks have a bigger prior → shrink more than points for same sample
    blk = s.shrink(3.0, 5, "blk")
    pts_equiv = s.shrink(3.0, 5, "pts")  # same numbers, less shrinkage
    # blk is pulled closer to its (low) league avg
    assert blk < 2.0

def test_prob_over_bounded():
    p = s.prob_over(30, 27.5, "pts")
    assert 0.0 <= p <= 1.0
