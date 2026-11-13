"""Round 4, experiment 1: coverage of fresh halftime quotes, the data notes, and
what a live loop would need (the window, the re-hang delay, the reads)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import r4_lib as L


def run() -> str:
    g = L.games()
    q = L.ht_quotes()
    out = []

    # data notes
    p = pd.read_parquet(L.CACHE / "periods.parquet")
    ps = p.groupby("game_id")[["home_points", "away_points"]].sum()
    gg = g.set_index("game_id").join(ps)
    ot = gg[gg.went_to_ot == 1]
    notes = [
        f"- Played games with a halftime row: {len(g):,}; break 10-25 minutes: {int(g.break_ok.sum()):,}; "
        f"with a pre-game total and spread as well (qualifying): {int(g.qual.sum()):,}.",
        f"- Qualifying games by season: {g[g.qual].groupby('season').size().to_dict()}.",
        f"- Final scores include overtime: in {len(ot)} overtime games the final equals the sum of all periods in "
        f"{int(((ot.home_score == ot.home_points) & (ot.away_score == ot.away_points)).sum())}.",
        f"- In-play rows: {L._C['n_inplay_rows']:,}; dropped because last_update was after snapshot_ts: "
        f"{L._C['dropped_future_stamp']}.",
        f"- In-play rows whose read falls inside a qualifying break: {len(q):,} on {q.game_id.nunique():,} games.",
        "- The shot feed's clock: free throws at the end of the second quarter are sometimes logged with a "
        "placeholder clock of 01:00 after a 00:10 shot (EUROLEAGUE_E2025_100). The running maximum of game "
        "seconds keeps the state in order, and the decision uses the half-time score at f = 0.5 directly. "
        "Training states near 1,150-1,200 game seconds can carry a slightly wrong f; this was left as ported.",
        "- Decidable books in play: only DraftKings in 2021-22 to 2024-25; FanDuel, BetMGM, BetRivers and "
        "Fanatics from 2025-26 (r4_inspect2.py). In those four seasons the rule that a quote needs two other books "
        "is met only through the reference books.",
        "- 2021-22 was snapshotted every 10 minutes (87.8% of gaps); 5 minutes from 2022-23 (96%).",
    ]
    out.append("### Data notes\n\n" + "\n".join(notes))

    # coverage: games with >= 1 fresh halftime quote per book, market and season
    fr = q[q.fresh & q.priced]
    cov = fr.groupby(["market", "season", "bookmaker"]).game_id.nunique().unstack(fill_value=0)
    cov = cov.reindex(columns=[b for b in L.BOOKS if b in cov.columns])
    tot = q.groupby("season").game_id.nunique().rename("games with a read in the break")
    blocks = []
    for mkt in ["totals", "spreads", "h2h"]:
        c = cov.loc[mkt].join(tot).reset_index()
        c["any decidable"] = fr[(fr.market == mkt) & fr.decidable].groupby("season").game_id.nunique().reindex(c.season).fillna(0).astype(int).values
        c.insert(0, "market", mkt)
        blocks.append(c)
    covt = pd.concat(blocks, ignore_index=True)
    out.append("### Games with at least one fresh halftime quote, by book\n\n"
               "Fresh = re-hung after the last second-quarter shot; the read inside the break window.\n\n"
               + L.md(covt.to_dict("records")))

    # the same, all quotes (fresh or not) for contrast
    al = q[q.inplay & q.priced].groupby(["market", "season"]).game_id.nunique().unstack(fill_value=0)
    fr2 = fr.groupby(["market", "season"]).game_id.nunique().unstack(fill_value=0)
    out.append("### Games with an in-play quote in the break, any book: all quotes against fresh only\n\n"
               + L.md([{"market": m, "kind": k, **{str(s): int(v) for s, v in t.loc[m].items()}}
                       for m in ["totals", "spreads", "h2h"] for k, t in (("all in-play", al), ("fresh", fr2))]))

    # the window and the reads
    gq = g[g.qual]
    win = (gq.first_q3_shot - gq.last_q2_shot).dt.total_seconds() / 60 - 2
    reads = q[["game_id", "season", "snapshot_ts"]].drop_duplicates().groupby(["season", "game_id"]).size()
    rd = reads.groupby("season").describe()[["count", "mean", "50%", "min", "max"]]
    out.append("### The window a live loop gets\n\n"
               f"Break (last second-quarter shot to first third-quarter shot), qualifying games: median "
               f"{gq.break_minutes.median():.2f} minutes, 10th-90th percentile {gq.break_minutes.quantile(.1):.2f}-"
               f"{gq.break_minutes.quantile(.9):.2f}. The window used here (one-minute buffers each side): median "
               f"{win.median():.2f} minutes.\n\nReads inside the window per game (the feed's own cadence):\n\n"
               + L.md(rd.reset_index().round(2).to_dict("records")))

    # the re-hang delay: first fresh last_update after the last Q2 shot, per book and market
    f1 = fr.groupby(["game_id", "market", "bookmaker"]).agg(lu=("last_update", "min"), l2=("last_q2_shot", "first"),
                                                            q3=("first_q3_shot", "first"), season=("season", "first")).reset_index()
    f1["delay_min"] = (f1.lu - f1.l2).dt.total_seconds() / 60
    f1["left_min"] = (f1.q3 - L.BUFFER - f1.lu).dt.total_seconds() / 60
    d = f1.groupby(["market", "bookmaker"]).agg(games=("game_id", "nunique"),
                                                delay_median=("delay_min", "median"),
                                                delay_p90=("delay_min", lambda x: x.quantile(.9)),
                                                minutes_left_median=("left_min", "median")).reset_index().round(2)
    out.append("### How long after the half's last shot each book re-hangs (its first fresh stamp)\n\n"
               "`delay` = first fresh last_update minus the last second-quarter shot, minutes. "
               "`minutes_left` = from that stamp to one minute before the first third-quarter shot.\n\n"
               + L.md(d.to_dict("records")))

    # the score feed against the listed tip
    dd = ((g.first_shot - g.tip).dt.total_seconds() / 60)
    dk = f1[(f1.market == "totals") & f1.bookmaker.isin(L.DECIDABLE)].delay_min
    early = f1[(f1.market == "totals") & f1.bookmaker.isin(L.DECIDABLE)]
    out.append("### The score feed's timing\n\n"
               f"First shot minus the listed tip, minutes: median {dd.median():.2f}, 5th {dd.quantile(.05):.2f}, "
               f"95th {dd.quantile(.95):.2f} ({len(dd):,} games). The shot chart's wall clock tracks real time: "
               f"a 15-minute break reads a median {g[g.qual].break_minutes.median():.2f} minutes from the last "
               "second-quarter shot to the first third-quarter shot. The decidable books' first fresh total "
               f"is stamped a median {dk.median():.2f} minutes after the last shot (share within 1 minute: "
               f"{100 * (dk <= 1).mean():.1f}%, within 2: {100 * (dk <= 2).mean():.1f}%; {len(early):,} game-books). "
               "That is an upper bound on the re-hang delay: the feed holds only a book's latest stamp at each read, "
               "so an earlier re-hang overwritten before the first read is not seen. A quote stamped after the "
               "last shot cannot predate the half's final score unless the shot feed runs early, and the "
               "one-minute buffer at the start of the window covers a feed that runs up to a minute early. "
               "No live EuroLeague in-play feed exists yet, so the lag between a live score source and the "
               "books cannot be measured here.")
    return "\n\n".join(out)


if __name__ == "__main__":
    print(run())
