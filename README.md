# LaunchCast NBA 🏀

A two-sided (offense × defense) NBA player-prop deep-dive, applying everything
learned from the LaunchCast MLB and NFL apps.

## What it does
For each player facing a specific opponent, it projects all major prop stats —
points, rebounds, assists, threes, steals, blocks, turnovers — by combining:
- the player's own rate (with **Bayesian shrinkage** so small samples don't lie),
- **how the specific defense they face performs** against that stat (the two-sided
  matchup core — the hitter-vs-pitcher insight, translated to NBA),
- **pace** (more possessions = more counting stats), and
- **projected minutes** (the biggest NBA-specific lever — a great matchup is
  worthless if the player sits).

## Architecture
Clean, modular (mirrors the NFL app):
- `core/scoring.py` — the two-sided projection math + Bayesian shrinkage
- `data/sources.py` — multi-source adapters (nba_api primary, balldontlie fallback)
- `data/fetcher.py` — comprehensive fetch: offense, defense, defense-vs-position,
  matchups, hustle — all stats, both sides
- `data/matchup.py` — assembles per-player-per-opponent projections
- `app.py` — the Streamlit UI

## Data
Primary source: **nba_api** (stats.nba.com). Backup: **balldontlie**. The data
layer throttles, caches, retries, and falls back so a single flaky source never
breaks the app. A health panel shows which sources are live.

## Status — honest
**Not yet validated.** The NBA season starts in October; until real games grade
it, the projections are *principled starting points* (league averages + sensible
matchup adjustments), not tuned numbers with a proven edge. Metric weighting and
prop-line tiers come later, evidence-first — the same discipline as MLB/NFL.

## Setup
See `SETUP_GUIDE_NBA.md` for step-by-step deployment. In short: deploy on
Streamlit Cloud with **Python 3.11** (Advanced settings), add an `owner_key`
secret, and open it.

## Owner login
Bookmark `https://YOUR-APP-URL/?owner=YOUR_KEY` to open straight into owner mode
(avoids the load-then-reload).
