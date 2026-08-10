# LaunchCast NBA — Build Roadmap

A two-sided (offense × defense) NBA prop deep-dive, applying everything learned
from the MLB + NFL apps. Season starts October — this is the foundation.

## Core design (carried from MLB/NFL)
- **Two-sided matchup**: every projection blends the player's rate with the
  DEFENSE faced (team def rating + defense-vs-position + defender tracking) —
  the hitter-vs-pitcher insight, translated. ✓ built + tested (11.9-pt swing
  between a weak and elite matchup for the same star).
- **Bayesian shrinkage** (from NFL, verified): small samples pulled to league
  avg. ✓ built + tested.
- **Minutes factor**: the biggest NBA-specific lever — counting stats scale with
  projected minutes (rest/blowout/injury swings). ✓ built.
- **Pace + context**: more possessions = more counting stats. ✓ built.

## Data source
- **nba_api** (free, the stats.nba.com library). Rich endpoints confirmed available:
  LeagueDashPlayerStats (offense), LeagueDashPtDefend (defense), BoxScoreMatchupsV3
  (who guarded whom), defense-vs-position, pace/rest/injury context.
- ⚠️ Rate-limits aggressively + may block cloud IPs (like MLB Statcast). The data
  layer MUST throttle + cache. This is the #1 build risk.

## Phased plan (deliberately NOT all 7 stats at once)
- **Phase 1 (DONE):** modular skeleton (core/data/ui) + core scoring + POINTS
  model + tests. Points first = highest volume, most predictable, most bet.
- **Phase 2 (NEXT):** the data layer — fetch offense/defense/matchup with proper
  throttling + caching. This is the hard, risky part. Prove we can pull data on
  Streamlit Cloud without getting blocked.
- **Phase 3:** wire points end-to-end (fetch → project → display) + a minimal UI.
- **Phase 4:** add rebounds + assists (next-most-predictable), same framework.
- **Phase 5:** threes, then steals/blocks/turnovers (rarer, noisier — need the
  heavy shrinkage + more data to be meaningful).
- **Phase 6:** backtesting by TIER (reuse the MLB tier-scoreboard idea — which
  matchup/situation tiers actually beat their prop lines).
- **Phase 7 (in-season):** calibrate probabilities against real results; only
  then are the displayed % trustworthy (ranking works before calibration).

## Honest status
Nothing is validated — the season hasn't started. These are PRINCIPLED STARTING
PRIORS (league averages, sensible clamps), not tuned numbers with a proven edge.
The model becomes real once October games grade it. Same discipline as MLB/NFL:
prove it with data before trusting it.

## The hard problems (named honestly, not hidden)
1. No clean 1-on-1 matchup (fluid defense, switches) — matchup data is noisier
   than pitcher/hitter. We approximate with defense-vs-position + tracking.
2. Correlated stats (pace inflates everything; usage ties pts/ast/tov) — handle
   with per-stat models, not one blob.
3. Minutes volatility (rest/blowout/injury) — the biggest prop factor; needs
   live injury/rotation news, which is late-breaking (like MLB lineups).
4. Rate limiting — the data layer's central engineering challenge.
