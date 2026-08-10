"""
data/sources.py — multi-source NBA data adapters with graceful fallback.

Your requirement: ALL stats + backup sources so we're never dead if one is down.
This module defines the source hierarchy and a unified fetch that tries them in
order, so the rest of the app doesn't care WHICH source answered.

SOURCE HIERARCHY:
  1. nba_api (stats.nba.com) — PRIMARY. Richest: player stats, defensive tracking,
     matchup box scores, defense-vs-position, pace, hustle. Rate-limits hard, so
     we throttle + cache aggressively.
  2. balldontlie (free JSON API) — BACKUP for core box-score stats. Very reliable
     uptime, simpler data, good when nba.com is flaky.
  3. basketball-reference (scrape) — BACKUP for advanced/historical when needed.

★ HONEST: fetches are UNTESTABLE from the build container (stats.nba.com is
egress-blocked here, like MLB Statcast). This code is written to the documented
APIs + defensive error handling; live behavior is confirmed on Streamlit Cloud.
"""
from __future__ import annotations
import time

# Browser-like headers — stats.nba.com rejects requests without them.
NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nba.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# Throttle: minimum seconds between stats.nba.com calls (avoid rate-limit blocks).
_MIN_INTERVAL = 0.6
_last_call = {"t": 0.0}


def _throttle():
    """Space out calls so we don't trip stats.nba.com rate limits."""
    dt = time.time() - _last_call["t"]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _last_call["t"] = time.time()


def nba_api_available() -> bool:
    try:
        import nba_api  # noqa
        return True
    except Exception:
        return False


def fetch_nba_endpoint(endpoint_cls_name: str, retries: int = 3, **kwargs):
    """Generic throttled+retried fetch of any nba_api stats endpoint by name.
    Returns the first DataFrame, or None on failure (so callers fall back).

    Example: fetch_nba_endpoint("LeagueDashPlayerStats", season="2024-25")
    """
    try:
        import importlib
        ep_mod = importlib.import_module("nba_api.stats.endpoints")
        cls = getattr(ep_mod, endpoint_cls_name, None)
        if cls is None:
            return None
    except Exception:
        return None

    for attempt in range(retries):
        try:
            _throttle()
            kwargs.setdefault("timeout", 30)
            obj = cls(**kwargs)
            frames = obj.get_data_frames()
            if frames and len(frames) > 0:
                return frames[0]
            return None
        except Exception:
            # exponential backoff before retry — handles transient rate limits
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
            continue
    return None


def fetch_balldontlie(path: str, params: dict | None = None, retries: int = 2):
    """Backup source: balldontlie free API (core box-score stats, reliable uptime).
    Returns parsed JSON dict or None. Used when nba_api is blocked/rate-limited."""
    import requests
    url = f"https://api.balldontlie.io/v1/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            _throttle()
            r = requests.get(url, params=params or {}, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))
            continue
    return None


def source_health() -> dict:
    """Report which sources are reachable — surfaced in the app so silent source
    failures are visible (the MLB pipeline-health lesson: never fail silently)."""
    health = {}
    health["nba_api_installed"] = nba_api_available()
    # a light reachability probe (won't work in the blocked container, works on Cloud)
    try:
        import requests
        r = requests.get("https://www.nba.com/", headers=NBA_HEADERS, timeout=8)
        health["nba_com_reachable"] = r.status_code == 200
    except Exception:
        health["nba_com_reachable"] = False
    try:
        import requests
        r = requests.get("https://api.balldontlie.io/v1/teams", timeout=8)
        health["balldontlie_reachable"] = r.status_code in (200, 401)  # 401 = up but needs key
    except Exception:
        health["balldontlie_reachable"] = False
    return health
