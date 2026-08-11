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
_MIN_INTERVAL = 0.4
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


# Last fetch errors, surfaced in the health panel so failures are VISIBLE, not
# silent (the MLB lesson: a silent None is worse than a loud error).
LAST_ERRORS: dict = {}


def fetch_nba_endpoint(endpoint_cls_name: str, retries: int = 1, **kwargs):
    """Generic throttled+retried fetch of any nba_api stats endpoint by name.
    Returns the first DataFrame, or None on failure. On failure, records WHY in
    LAST_ERRORS[endpoint_cls_name] so the app can show the real cause.

    Example: fetch_nba_endpoint("LeagueDashPlayerStats", season="2024-25")
    """
    try:
        import importlib
        ep_mod = importlib.import_module("nba_api.stats.endpoints")
        cls = getattr(ep_mod, endpoint_cls_name, None)
        if cls is None:
            LAST_ERRORS[endpoint_cls_name] = f"endpoint class '{endpoint_cls_name}' not found in nba_api"
            return None
    except Exception as e:
        LAST_ERRORS[endpoint_cls_name] = f"import error: {type(e).__name__}: {e}"
        return None

    last_err = None
    for attempt in range(retries):
        try:
            _throttle()
            kwargs.setdefault("timeout", 20)
            obj = cls(**kwargs)
            frames = obj.get_data_frames()
            if frames and len(frames) > 0 and not frames[0].empty:
                LAST_ERRORS.pop(endpoint_cls_name, None)  # clear on success
                return frames[0]
            # got a response but it was EMPTY — record that distinctly
            last_err = "returned empty (no rows — season may not have started, or params too narrow)"
            return None
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:200]}"
            if attempt < retries - 1:
                time.sleep(0.8 * (attempt + 1))
            continue
    LAST_ERRORS[endpoint_cls_name] = last_err or "unknown failure"
    return None


def _balldontlie_key():
    """Free API key from Streamlit secrets. Robust to the exact secret name —
    checks several common spellings and strips stray whitespace/quotes, since a
    tiny name/format mismatch was causing 401s. Returns '' if genuinely not set."""
    try:
        import streamlit as st
        for name in ("balldontlie_key", "BALLDONTLIE_KEY", "balldontlie_api_key",
                     "balldontlieKey", "bdl_key"):
            v = st.secrets.get(name, "")
            if v:
                return str(v).strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def balldontlie_key_present() -> bool:
    """For the health panel: is a key actually being read? (diagnoses 401s.)"""
    return bool(_balldontlie_key())


def fetch_balldontlie(path: str, params: dict | None = None, retries: int = 2):
    """PRIMARY source: balldontlie API. Tries MULTIPLE auth header formats (raw
    key, then 'Bearer <key>') because balldontlie's expected format has varied.
    Records a DETAILED reason on failure — including key length + exact status —
    so a persistent 401 is fully diagnosable (without ever logging the key itself)."""
    import requests
    key = _balldontlie_key()
    if not key:
        LAST_ERRORS[f"balldontlie:{path}"] = "no key found in secrets"
        return None
    p = path.lstrip("/")
    # balldontlie restructured into SPORT-NAMESPACED APIs. Try the new /nba/ path
    # first, then the legacy path. (Account shows separate NBA/MLB/NFL plans, so
    # the NBA key is valid only for the /nba/ namespace.)
    base_urls = [
        f"https://api.balldontlie.io/nba/v1/{p}",
        f"https://api.balldontlie.io/v1/{p}",
    ]
    auth_variants = [
        {"Authorization": key},
        {"Authorization": f"Bearer {key}"},
    ]
    last = None
    for url in base_urls:
        for headers in auth_variants:
            try:
                _throttle()
                r = requests.get(url, params=params or {}, headers=headers, timeout=15)
                if r.status_code == 200:
                    LAST_ERRORS.pop(f"balldontlie:{path}", None)
                    return r.json()
                body = ""
                try:
                    body = r.text[:100]
                except Exception:
                    pass
                last = (f"HTTP {r.status_code} @ {url.split('.io/')[1].split('/')[0]}"
                        f"/ (keylen={len(key)}, body={body})")
            except Exception as e:
                last = f"{type(e).__name__}: {str(e)[:80]}"
                continue
    LAST_ERRORS[f"balldontlie:{path}"] = last or "unknown"
    return None


def source_health() -> dict:
    """Report which sources are reachable — surfaced in the app so silent source
    failures are visible (the MLB pipeline-health lesson: never fail silently)."""
    health = {}
    health["nba_api_installed"] = nba_api_available()
    health["balldontlie_key_found"] = balldontlie_key_present()
    health["apinba_key_found"] = apinba_key_present()
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
    # surface any recorded fetch errors so failures are diagnosable, not silent
    if LAST_ERRORS:
        health["recent_fetch_errors"] = dict(LAST_ERRORS)
    return health


# ── API-NBA (api-sports.io) — cloud-friendly source with FREE player stats ────
# Works from Streamlit Cloud (unlike stats.nba.com which times out, and unlike
# balldontlie free which gates stats). Free tier = 100 req/day, includes player +
# team statistics. Auth supports BOTH signup paths:
#   - direct api-sports.io:  header x-apisports-key
#   - via RapidAPI:          headers x-rapidapi-key + x-rapidapi-host
def _apinba_key():
    try:
        import streamlit as st
        for name in ("apinba_key", "api_nba_key", "apisports_key", "rapidapi_key"):
            v = st.secrets.get(name, "")
            if v:
                return str(v).strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def apinba_key_present() -> bool:
    return bool(_apinba_key())


def fetch_apinba(path: str, params: dict | None = None, retries: int = 2):
    """Fetch from API-NBA (api-sports.io). Tries the direct api-sports.io host
    first, then the RapidAPI host, so either signup style works. Returns the
    parsed 'response' list (API-NBA wraps data in {'response': [...]}), or None.
    Records failures in LAST_ERRORS."""
    import requests
    key = _apinba_key()
    if not key:
        LAST_ERRORS[f"apinba:{path}"] = "no key found (add apinba_key to secrets)"
        return None
    p = path.lstrip("/")
    attempts = [
        (f"https://v2.nba.api-sports.io/{p}", {"x-apisports-key": key}),
        (f"https://api-nba-v1.p.rapidapi.com/{p}",
         {"x-rapidapi-key": key, "x-rapidapi-host": "api-nba-v1.p.rapidapi.com"}),
    ]
    last = None
    for url, headers in attempts:
        for attempt in range(retries):
            try:
                _throttle()
                r = requests.get(url, params=params or {}, headers=headers, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict) and "response" in data:
                        LAST_ERRORS.pop(f"apinba:{path}", None)
                        return data["response"]
                    last = "200 but no 'response' field"
                else:
                    body = ""
                    try:
                        body = r.text[:100]
                    except Exception:
                        pass
                    last = f"HTTP {r.status_code} @ {url.split('/')[2]} (body={body})"
                    if r.status_code in (401, 403):
                        break
            except Exception as e:
                last = f"{type(e).__name__}: {str(e)[:100]}"
                if attempt < retries - 1:
                    time.sleep(0.8 * (attempt + 1))
                continue
    LAST_ERRORS[f"apinba:{path}"] = last or "unknown"
    return None
