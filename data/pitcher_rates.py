"""Pitcher rate arithmetic, shared by the daily ingest and the table rebuild.

WHY THIS IS ONE MODULE. `data/ingestors/mlb_stats_ingestor.py` writes tomorrow's
pitcher rows and `data/pitcher_stats_rebuild.py` writes history's. If they
compute a feature differently, the model trains on one definition and is served
another, and nothing anywhere fails — the numbers just quietly stop meaning the
same thing. That already happened here: the ingest computed `era_last3` as
`AVG(era)` over the last three STORED rows (a mean of three season-to-date
rates, so a smoothed near-duplicate of `era`) while the history it trained on
carried a season-final constant. §1b's rule about preferring a shared helper
over a per-caller implementation is exactly this case.

INNINGS ARE IN BASEBALL NOTATION. `innings_pitched` 5.2 means five and TWO
THIRDS. Only .0/.1/.2 fractions occur, across all 135,010 rows of
`player_game_log`. Summing the column directly is wrong arithmetic and inflates
every ERA built on it — a mean bias of +0.025 that falls to +0.002 once
converted. Work in OUTS; convert exactly once, here.
"""
from __future__ import annotations

LAST_N = 3

# 27 outs = 9 innings, so a per-nine rate is 27 * total / outs.
OUTS_PER_NINE = 27.0
OUTS_PER_INNING = 3.0


def outs_from_ip(ip: float) -> int:
    """Convert baseball innings notation to outs. 5.2 -> 17, not 15.6.

    The fractional part counts THIRDS of an inning and is only ever .0, .1 or
    .2. Anything else means the column's meaning has changed and every rate
    built on it would be quietly wrong, so this raises rather than rounds.
    """
    whole = int(ip)
    thirds = round((ip - whole) * 10)
    if thirds not in (0, 1, 2):
        raise ValueError(
            f"innings_pitched {ip!r} has fractional part .{thirds} — baseball "
            f"notation only ever carries .0, .1 or .2 thirds of an inning")
    return whole * 3 + thirds


def per_nine(total: float, outs: int) -> float | None:
    """A per-nine-innings rate (ERA, K/9, BB/9, HR/9) from a total and outs."""
    if not outs:
        return None
    return round(OUTS_PER_NINE * total / outs, 4)


def whip(walks: float, hits: float, outs: int) -> float | None:
    """Walks plus hits per inning pitched."""
    if not outs:
        return None
    return round(OUTS_PER_INNING * (walks + hits) / outs, 4)


def last3_rates(starts: list[tuple]) -> tuple:
    """TRUE rolling ERA and K/9 over a pitcher's last three starts.

    `starts` is `(innings_pitched, earned_runs, strikeouts)` per start, in any
    order, already restricted to starts BEFORE the one being described. Only
    the final `LAST_N` are used, so callers may pass the whole season.

    This is a real rolling window over the raw lines — 27 * ER / outs across the
    three starts — NOT the mean of three season-to-date ERAs. The distinction is
    the whole point: the old definition was a smoothed restatement of `era` and
    carried almost no independent information, which is why `d_starter_era` and
    `d_starter_era_last3` behaved as one feature worth 40% of
    `mlb_f5_moneyline`'s importance. Approved by mike, 2026-09-03 ("yes on
    era_last3").

    Returns `(None, None)` when there is nothing to average, so a season's first
    start carries no fabricated rate.
    """
    window = starts[-LAST_N:]
    if not window:
        return None, None

    outs = sum(outs_from_ip(ip) for ip, _, _ in window)
    if not outs:
        return None, None

    return (per_nine(sum(er or 0 for _, er, _ in window), outs),
            per_nine(sum(k or 0 for _, _, k in window), outs))
