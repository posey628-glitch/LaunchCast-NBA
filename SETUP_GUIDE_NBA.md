# LaunchCast NBA — Setup Guide (step by step)

Phase 2 is done: the data layer (all stats, both sides, multi-source with
fallback) + two-sided projections + a minimal working app. Here's exactly what
to do with these files.

════════════════════════════════════════════════════════════
## STEP 1 — Create the GitHub repo
════════════════════════════════════════════════════════════
1. Go to https://github.com/new
2. Repository name: `LaunchCast-NBA`
3. Set it to Private (or Public — no personal info either way)
4. Click "Create repository"

════════════════════════════════════════════════════════════
## STEP 2 — Add the files (KEEP THE FOLDER STRUCTURE)
════════════════════════════════════════════════════════════
This app uses FOLDERS (like the NFL app), so structure matters. Upload so the
repo looks EXACTLY like this:

    LaunchCast-NBA/
    ├── app.py
    ├── requirements.txt
    ├── runtime.txt
    ├── .streamlit/
    │   └── config.toml
    ├── core/
    │   ├── __init__.py
    │   ├── scoring.py
    │   └── test_scoring.py
    ├── data/
    │   ├── __init__.py
    │   ├── sources.py
    │   ├── fetcher.py
    │   ├── matchup.py
    │   └── test_data.py
    └── ui/
        └── __init__.py

★ The `__init__.py` files (even though empty) are REQUIRED — they make Python
treat core/, data/, ui/ as importable packages. Don't skip them.

Easiest upload method: on the repo page click "Add file" → "Upload files", then
drag the whole folder structure in. GitHub preserves folders when you drag a
folder. If uploading one at a time, type the path in the filename box (e.g.
`core/scoring.py`) and GitHub creates the folder.

════════════════════════════════════════════════════════════
## STEP 3 — Deploy on Streamlit Cloud
════════════════════════════════════════════════════════════
1. Go to https://share.streamlit.io → "New app"
2. Repo: LaunchCast-NBA, branch: main, main file: app.py
3. ★ Click "Advanced settings" → set Python version to 3.11
   (REQUIRED — the dashboard overrides runtime.txt; this prevents the MLB crash.)
4. Click Deploy.

════════════════════════════════════════════════════════════
## STEP 4 — Add the owner secret
════════════════════════════════════════════════════════════
1. In the deployed app: Manage app → Settings → Secrets
2. Add one line:
      owner_key = "Posey628628!"
3. Save.

════════════════════════════════════════════════════════════
## STEP 5 — Test it
════════════════════════════════════════════════════════════
1. Open the app. It should load with the 🏀 LaunchCast NBA title.
2. Click "Check sources" under Data source health — on Cloud, nba_com_reachable
   should be true. (In a blocked network it'd be false — that's why we test on Cloud.)
3. Click "Fetch league data" — it pulls offense + defense (throttled). It'll show
   what fetched OK and what didn't.
4. Pick a player + opponent → see two-sided projections for all 7 stats.

Owner login: bookmark  https://YOUR-NBA-URL/?owner=Posey628628!

════════════════════════════════════════════════════════════
## WHAT WORKS NOW vs WHAT'S NEXT
════════════════════════════════════════════════════════════
WORKS NOW (Phase 2):
  - Multi-source data layer (nba_api primary + balldontlie fallback + health panel)
  - Comprehensive fetch: offense, advanced, team defense, opponent-allowed,
    defense-vs-position, matchups, hustle — ALL stat categories
  - Two-sided projections (offense rate × defense faced × pace × minutes) for
    pts/reb/ast/fg3m/stl/blk/tov, each transparent with its matchup multiplier

NOT YET (honest):
  - Projections are PRINCIPLED STARTING POINTS, not validated — season starts Oct
  - No metric WEIGHTING yet (that's learned from real results, like MLB)
  - No prop-line integration / tiers / backtesting yet (later phases)
  - Live fetching only verified once you deploy (stats.nba.com is blocked from the
    build environment, works on Cloud)

════════════════════════════════════════════════════════════
## IMPORTANT HONESTY
════════════════════════════════════════════════════════════
I could NOT live-test the NBA data fetches — stats.nba.com is blocked from the
build container (same as MLB Statcast/NFL nflverse). The code is written to the
documented nba_api interface with defensive error handling and passes all logic
tests, but the FIRST real fetch happens when YOU deploy. If a fetch errors, send
me the message and I'll fix it — the structure is sound; any issue will be a
specific fixable detail, not a fundamental problem.
