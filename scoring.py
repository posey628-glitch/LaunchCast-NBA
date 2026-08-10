"""
core/scoring.py — LaunchCast NBA scoring.

Design philosophy carried over from the MLB + NFL apps:
  - TWO-SIDED matchup analysis: every projection blends the OFFENSIVE player's
    rate with the DEFENSE they face (team defensive rating + defense-vs-position
    + individual defender tracking), exactly like hitter-vs-pitcher in MLB.
  - BAYESIAN SHRINKAGE (from the NFL app): small samples get pulled toward the
    league/positional average so early-season or low-minute players don't produce
    garbage projections. Textbook-correct, hand-verified in NFL.
  - CONTEXT adjustment (like park factors + weather in MLB): pace, rest, home/away,
    and — the biggest NBA-specific factor — projected MINUTES.

HONEST SCOPE: this starts with POINTS as the anchor stat (highest volume, most
predictable, most bet). The framework generalizes to reb/ast/threes/stl/blk/tov,
which get added ONE AT A TIME once points is validated — because each stat has
different drivers and building all seven at once means seven half-built models.

Nothing here is validated yet — NBA season starts in October. These are principled
STARTING priors to refine against real results, NOT tuned numbers with a proven edge.
"""
from __future__ import annotations

LEAGUE_AVG = {
    "pts": 11.5, "reb": 4.3, "ast": 2.7, "fg3m": 1.4,
    "stl": 0.8, "blk": 0.5, "tov": 1.4, "min": 24.0,
}

SHRINK_PRIOR = {
    "pts": 8, "reb": 8, "ast": 8, "fg3m": 10,
    "stl": 15, "blk": 15, "tov": 10,
}


def shrink(observed_rate: float, games: float, stat: str) -> float:
    """Bayesian shrinkage toward league average (from NFL app, verified).
    f = games/(games+prior); result = f*observed + (1-f)*league_avg."""
    try:
        g = float(games)
        if g <= 0:
            return float(LEAGUE_AVG.get(stat, 0.0))
        prior = SHRINK_PRIOR.get(stat, 10)
        league = float(LEAGUE_AVG.get(stat, 0.0))
        f = g / (g + prior)
        return float(f * float(observed_rate) + (1 - f) * league)
    except Exception:
        return float(LEAGUE_AVG.get(stat, 0.0))


def defense_multiplier(def_allowed: float, league_allowed: float) -> float:
    """Two-sided core: matchup help/hurt as a multiplier around 1.0, clamped to
    [0.80, 1.25] so no single matchup swings a projection more than ±25%."""
    try:
        if league_allowed <= 0:
            return 1.0
        return max(0.80, min(1.25, float(def_allowed) / float(league_allowed)))
    except Exception:
        return 1.0


def minutes_factor(proj_minutes: float, season_avg_minutes: float) -> float:
    """The biggest NBA lever: counting stats scale with MINUTES. Clamped [0.5,1.6]."""
    try:
        if season_avg_minutes <= 0:
            return 1.0
        return max(0.5, min(1.6, float(proj_minutes) / float(season_avg_minutes)))
    except Exception:
        return 1.0


def project_stat(player_rate: float, games_played: float, stat: str,
                 opp_allowed: float, league_allowed: float,
                 proj_minutes=None, season_avg_minutes=None,
                 pace_factor: float = 1.0) -> float:
    """Full two-sided projection: shrink → defense matchup → pace → minutes."""
    base = shrink(player_rate, games_played, stat)
    base *= defense_multiplier(opp_allowed, league_allowed)
    base *= max(0.90, min(1.12, float(pace_factor)))
    if proj_minutes is not None and season_avg_minutes:
        base *= minutes_factor(proj_minutes, season_avg_minutes)
    return round(base, 2)


def prob_over(projection: float, line: float, stat: str) -> float:
    """Rough P(over line). Poisson tail for low-count stats, normal for points.
    Placeholder calibration — refine variance from data (like NFL yardage note).
    Ranking is trustworthy before the probabilities are."""
    import math
    try:
        lam = max(0.01, float(projection))
        L = float(line)
        if stat in ("fg3m", "stl", "blk", "tov", "ast", "reb"):
            k = int(math.floor(L)) + 1
            cdf = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(0, k))
            return round(max(0.0, min(1.0, 1 - cdf)), 4)
        sd = max(4.0, min(12.0, lam * 0.45))
        from statistics import NormalDist
        return round(1 - NormalDist(lam, sd).cdf(L), 4)
    except Exception:
        return 0.5
