"""
scripts/fetch_to_gist.py — runs in GitHub Actions, fetches API-NBA → gist.

Uses API-NBA (api-sports.io), which works from GitHub's IPs (unlike stats.nba.com
which blocks automated access everywhere). Free tier = 100 req/day; we use ~31
calls (1 for teams + 30 for per-team player stats), well within budget. Caches
the result to a gist the app reads.

Env vars (from repo secrets):
  APINBA_KEY  — your API-NBA / api-sports.io key
  GIST_TOKEN  — GitHub PAT with 'gist' scope
  GIST_ID     — the gist to write to
"""
import os, json, time, datetime
from collections import defaultdict
import requests

def log(m): print(m, flush=True)

APINBA_KEY = os.environ.get("APINBA_KEY", "")

def apinba(path, params):
    """Try direct api-sports.io host, then RapidAPI host."""
    attempts = [
        (f"https://v2.nba.api-sports.io/{path}", {"x-apisports-key": APINBA_KEY}),
        (f"https://api-nba-v1.p.rapidapi.com/{path}",
         {"x-rapidapi-key": APINBA_KEY, "x-rapidapi-host": "api-nba-v1.p.rapidapi.com"}),
    ]
    for url, headers in attempts:
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                d = r.json()
                if isinstance(d, dict) and "response" in d:
                    return d["response"]
            else:
                log(f"  {path} HTTP {r.status_code} @ {url.split('/')[2]}: {r.text[:80]}")
        except Exception as e:
            log(f"  {path} error @ {url.split('/')[2]}: {e}")
    return None

def num(v):
    try: return float(v) if v is not None else 0.0
    except: return 0.0

def min_f(m):
    try:
        if m is None: return 0.0
        if ":" in str(m):
            mm, ss = str(m).split(":")[:2]; return round(float(mm)+float(ss)/60,1)
        return float(m)
    except: return 0.0

def fetch():
    now = datetime.date.today()
    ys = now.year - 1 if now.month >= 10 else now.year - 2
    season = ys
    log(f"Fetching season {season} from API-NBA…")
    out = {"season": f"{ys}-{str(ys+1)[-2:]}", "season_year": ys,
           "fetched_at": datetime.datetime.utcnow().isoformat()}

    teams = apinba("teams", {"league": "standard"}) or []
    team_ids = [t.get("id") for t in teams if t.get("nbaFranchise") and not t.get("allStar")]
    log(f"  {len(team_ids)} NBA teams")

    agg = defaultdict(lambda: {"n":0,"PTS":0.,"REB":0.,"AST":0.,"FG3M":0.,
                               "STL":0.,"BLK":0.,"TOV":0.,"MIN":0.,"NAME":None,"TEAM_ID":None})
    for i, tid in enumerate(team_ids):
        rows = apinba("players/statistics", {"team": tid, "season": season})
        if rows:
            for d in rows:
                p = d.get("player") or {}
                pid = p.get("id")
                if pid is None: continue
                a = agg[pid]; a["n"]+=1
                a["PTS"]+=num(d.get("points")); a["REB"]+=num(d.get("totReb"))
                a["AST"]+=num(d.get("assists")); a["FG3M"]+=num(d.get("tpm"))
                a["STL"]+=num(d.get("steals")); a["BLK"]+=num(d.get("blocks"))
                a["TOV"]+=num(d.get("turnovers")); a["MIN"]+=min_f(d.get("min"))
                if a["NAME"] is None:
                    a["NAME"]=f"{p.get('firstname','')} {p.get('lastname','')}".strip()
                if a["TEAM_ID"] is None:
                    a["TEAM_ID"]=(d.get("team") or {}).get("id")
        time.sleep(0.3)  # be gentle on rate limit
        if (i+1) % 10 == 0: log(f"  …{i+1}/{len(team_ids)} teams")

    offense = []
    for pid, a in agg.items():
        n = max(1, a["n"])
        offense.append({"PLAYER_ID":pid,"PLAYER_NAME":a["NAME"],"TEAM_ID":a["TEAM_ID"],
            "GP":a["n"],"MIN":round(a["MIN"]/n,1),"PTS":round(a["PTS"]/n,1),
            "REB":round(a["REB"]/n,1),"AST":round(a["AST"]/n,1),"FG3M":round(a["FG3M"]/n,1),
            "STL":round(a["STL"]/n,1),"BLK":round(a["BLK"]/n,1),"TOV":round(a["TOV"]/n,1)})
    out["offense"] = offense
    out["team_opponent"] = []  # add later; offense is the core
    log(f"  aggregated {len(offense)} players ✓")
    return out

def write_gist(data):
    token = os.environ["GIST_TOKEN"]; gid = os.environ["GIST_ID"]
    payload = {"files": {"nba_data.json": {"content": json.dumps(data)}}}
    r = requests.patch(f"https://api.github.com/gists/{gid}",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        json=payload, timeout=30)
    r.raise_for_status()
    log(f"Wrote {len(json.dumps(data))} bytes to gist ✓")

if __name__ == "__main__":
    if not APINBA_KEY:
        log("ERROR: APINBA_KEY secret not set."); raise SystemExit(1)
    data = fetch()
    if not data.get("offense"):
        log("WARNING: no player data — check API-NBA key / quota.")
    write_gist(data)
    log("Done.")
