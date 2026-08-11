"""
scripts/fetch_to_gist.py — runs in GitHub Actions (NOT in the app).

WHY THIS EXISTS: stats.nba.com times out from Streamlit Cloud's datacenter IPs,
but GitHub Actions runs on GitHub's IPs, which nba.com serves normally. So this
script fetches the full free NBA data from nba.com HERE, and caches it to a gist.
The app then reads the gist (fast, reliable) instead of hitting nba.com directly.

This is the SAME proven pattern as the MLB app's snapshot system.

Env vars (set by the workflow from repo secrets):
  GIST_TOKEN  — GitHub PAT with 'gist' scope
  GIST_ID     — the gist to write to
"""
import os, json, time, sys

def log(m): print(m, flush=True)

def fetch_nba():
    """Fetch player offense + team opponent from nba.com. Returns a dict of records."""
    from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats
    import datetime
    now = datetime.date.today()
    # last completed season (works year-round)
    ys = now.year - 1 if now.month >= 10 else now.year - 2
    season = f"{ys}-{str(ys+1)[-2:]}"
    log(f"Fetching season {season} from nba.com…")

    out = {"season": season, "fetched_at": datetime.datetime.utcnow().isoformat()}

    # generous timeout is FINE here — GitHub Actions has no app-restart limit
    for attempt in range(4):
        try:
            off = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season, per_mode_detailed="PerGame",
                measure_type_detailed_defense="Base", timeout=60,
            ).get_data_frames()[0]
            out["offense"] = off.to_dict(orient="records")
            log(f"  offense: {len(off)} players ✓")
            break
        except Exception as e:
            log(f"  offense attempt {attempt+1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    else:
        out["offense"] = []

    for attempt in range(4):
        try:
            opp = leaguedashteamstats.LeagueDashTeamStats(
                season=season, per_mode_detailed="PerGame",
                measure_type_detailed_defense="Opponent", timeout=60,
            ).get_data_frames()[0]
            out["team_opponent"] = opp.to_dict(orient="records")
            log(f"  team_opponent: {len(opp)} teams ✓")
            break
        except Exception as e:
            log(f"  team_opponent attempt {attempt+1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    else:
        out["team_opponent"] = []

    return out

def write_gist(data):
    import requests
    token = os.environ["GIST_TOKEN"]
    gist_id = os.environ["GIST_ID"]
    payload = {"files": {"nba_data.json": {"content": json.dumps(data)}}}
    r = requests.patch(
        f"https://api.github.com/gists/{gist_id}",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json"},
        json=payload, timeout=30,
    )
    r.raise_for_status()
    log(f"Wrote {len(json.dumps(data))} bytes to gist {gist_id} ✓")

if __name__ == "__main__":
    data = fetch_nba()
    n_off = len(data.get("offense", []))
    if n_off == 0:
        log("WARNING: no offense data fetched — nba.com may have blocked even GitHub.")
    write_gist(data)
    log("Done.")
