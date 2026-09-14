# nfl_prop_market, 2026: no cut change, no ceiling change

*Measured 2026-09-14, after the ESPN Out/Doubtful veto (#722) landed.
The veto is not in this sample — production `injuries` had 0 NFL rows
when these picks were written; 463 NFL rows exist now.*

**Conclusion.** Leave `NFL_PROP_MARKET_SIDE_EDGE` at over 6pp / under 5pp
and leave `NFL_PROP_MAX_LEAD_HOURS` at 24. The 2026 settled window is two
weeks and 15 priced BETs. That is not a plateau, not a time split, and
not a neighbourhood. The 2023-25 record those numbers were fitted on
still governs.

Kalshi stays a **reference** (`models.nfl_prop_market.KALSHI_BOOK`).
`kalshi_prop_ladders` has snapshots, not settlements (278,568 rungs, 4
dates, no `resolved_at`). The historical grader does not read it.

Distributional `nfl_prop_*` / sacks stay paused. No paid news. No
opener/wind unit change.

Reproduce the October look with a populated 2026 cache:

```bash
python -m scripts.nfl_prop_two_sharps --season 2026 --snapshot open \
       --min-edge 0.05 --over-edge 0.06 --by-side --by-lead-hourly
```

---

## 1. Production settled picks (`picks`, model_id = nfl_prop_market)

Queried 2026-09-14. VOID is not in the record (CLAUDE.md §1c). Units =
`profit_flat / 100`, gated on a non-NULL price (every row here is priced).

| set | n | W-L | units | ROI | notes |
|---|---|---|---|---|---|
| all settled BETs | 15 | 8-7 | **+1.36u** | **+9.1%** | 1 VOID excluded, 3 DEN@KC still open |
| **inside 24h** | **11** | **6-5** | **+1.14u** | **+10.3%** | the operating ceiling |
| over, all 15 | 7 | 5-2 | +1.96u | +28.0% | includes two pre-ceiling overs |
| under, all 15 | 8 | 3-5 | −2.60u | −32.5% | includes two pre-ceiling unders |
| over, inside 24h | 5 | 3-2 | +0.74u | +14.7% | |
| under, inside 24h | 6 | 3-3 | +0.40u | +6.7% | |

CLV (same-line `clv_pct`, `clv_beat_close`): 11 of 15 settled BETs beat
the close, 4 did not. Mean `clv_pct` on the 14 rows that have one:
**+3.30pp**. `Sam Darnold Under 19.5 Comp (MGM)` has no price CLV
(`line_clv_pts = −1`).

Four Week-1 BETs were written **past** the 24h ceiling (Williams 130.9h,
Cousins 120.0h, Higbee 56.1h, Price 34.9h). They stay in the record —
line movement / a later ceiling is not a VOID. The inside-24h row is the
one that describes what the card will write next.

Every inside-24h Sunday 1pm ET pick locked at **18–24h** lead. That is
the first-signal lock meeting the ceiling, not the last four hours.

## 2. Full 2026 board, latest pre-game quote (15 settled games)

Same rule as `scripts/nfl_prop_two_sharps.py` (`either` sharp reference,
one bet per (player, market, side), best edge, equal lines, de-vig
proportional). Graded in SQL against `nfl_player_game_log` for the 15
games that have actuals. **Latest quote per key**, so on hourly 2026
polls this is the last tick before kickoff — not the production lock.

| side | 3pp | 4pp | 5pp | 6pp |
|---|---|---|---|---|
| over n / ROI | 74 / +12.8% | 35 / +14.4% | **12 / −18.6%** | **4 / +1.7%** |
| under n / ROI | 65 / +2.6% | 32 / +3.8% | **18 / −26.3%** | 10 / −46.2% |

Shipped pairing (over 6pp, under 5pp): **22 bets, −4.66u, −21.2%**.
Single 5pp floor: 30 bets, −6.96u, −23.2%.

The over curve is **not monotone** (4pp +14.4% → 5pp −18.6% → 6pp +1.7%
on 4 bets). The under side is **not** the stronger one at the shipped
cut. Both facts are the opposite of 2023-25, and both cells are under
the 25-bet / plateau / time-split bar in `.claude/rules/analysis-and-thresholds.md`.
A two-week sample does not overrule three seasons.

## 3. Hourly-band curve inside 24h

Latest quote **inside each band**, not overall latest. 5pp, either
reference. Four games fully graded this way (ARI@LAC, ATL@PIT, NE@SEA,
BAL@IND); 3-game scans timed out on `player_prop_odds`.

| band | n | units | ROI |
|---|---|---|---|
| 0-4 h | 9 | −2.99 | −33.3% |
| 4-8 h | 1 | +0.61 | thin |
| 8-12 h | 3 | +2.46 | thin |
| 12-24 h | 4 | −0.14 | −3.6% |
| 24-36 h | 2 | −0.39 | thin |
| 36+ h | 4 | −2.18 | −54.5% |

Direction matches the 2023-25 correction: **the last four hours are the
weakest populated band**. 36+ is worse, not the Saturday-morning +17% of
the `open` backfill. Tightening the ceiling to 12h would keep 0-4h and
drop 12-24h. Widening to 36h would add a band that is negative here.
Neither move is licensed.

1-hour cells on this window are 0–3 bets. `--by-lead-hourly` exists so
October can print them; it is not a 2026-09-14 finding.

## 4. What was deliberately not done

- No change to `min_edge` / `min_edge_by_side`.
- No change to `NFL_PROP_MAX_LEAD_HOURS`.
- Kalshi not added to `SHARP_BOOKS` or to this grader.
- Distributional props / sacks not unpaused.
- No paid news provider.
- Opener / wind units untouched.
