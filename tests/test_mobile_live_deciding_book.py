"""An in-play pick is shown at the book that DECIDED it, never DraftKings by
default (CLAUDE.md section 6: the row records which book).

Since 2026-09-10 the MLB and NCAAF in-play models decide at the best bettable
in-play price, and the NBA in-play models (2026-11-04) bet the best offer among
eight books, writing decision_book / decision_odds on the pick. Measured
2026-11-04 on production: 56 of the 98 live BETs since 2026-09-10 were decided
away from DraftKings (NCAAF 48 of 85, MLB 8 of 13). The app labelled every one
of them a DraftKings bet: the card's book, its "Now" price (DraftKings' in-play
row beside a FanDuel lock), its hand-off and the board's "DraftKings only"
note. The pre-game cards had read `storedQuoteBook` since 2026-09-09; the live
branches kept `is_live ? MODEL_BOOK : ...`.

What is pinned here, each against the real modules under node:

  * the hero, the hand-off, the record chip and the member's-books view all
    use the deciding book on a live pick;
  * a live price the app does not hold is said so ("not tracked"), not drawn
    as "Now --" for the whole game: the NBA loop reads the books once an hour,
    and the NCAAF loop stores only DraftKings' in-play rows;
  * fetchLivePicks reads the deciding book's in-play row, not DraftKings only;
  * the NBA lock row says "Q", the NBA names say when the bet is placed (they
    settle on the full game), the NBA Live-board window is 3.5h, and the
    model page and the empty board say when the NBA models check.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.test_mobile_team_total import MARKETS_FILES, META_FILES, _run, node

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile" / "src"

LIVE = """
const FD_LIVE = { ...PICK, game_id: 'NCAAF_2026-10-31_kansas_tcu', model_id: 'ncaaf_live_win_prob',
  sport: 'NCAAF', is_live: true, pick_side: 'away', pick_label: 'Kansas ML (live)', scored_line: null,
  dk_odds: 239, decision_odds: 250, decision_book: 'fanduel', best_book: 'fanduel',
  best_bet_link: 'fd://lock', dk_bet_link: 'dk://lock', created_at: '2026-10-31T20:55:21+00:00' };
const DK_ROW = { game_id: FD_LIVE.game_id, game_date: '2026-10-31', market: 'h2h', home_price: -300,
  away_price: 230, spread_home: null, total_line: null, over_price: null, under_price: null,
  snapshot_at: '2026-10-31T21:10:00+00:00' };
const DK_BOOKROW = { bookmaker: 'draftkings', home_price: -300, away_price: 230, snapshot_at: DK_ROW.snapshot_at };
const FD_BOOKROW = { bookmaker: 'fanduel', home_price: -320, away_price: 260, away_link: 'fd://now',
  snapshot_at: '2026-10-31T21:10:00+00:00' };
"""


@node
def test_a_live_pick_decided_at_fanduel_shows_fanduels_price_and_hands_off_there(tmp_path):
    _run(tmp_path, MARKETS_FILES, LIVE + """
import { heroAmericanForPick, bestHandoffForPick, pickLineQuotes, currentLineQuotes } from './markets.ts';
const h = heroAmericanForPick(FD_LIVE, DK_ROW, [DK_BOOKROW, FD_BOOKROW]);
eq([h.kind, h.book, h.price, h.lockedPrice, h.link], ['now', 'fanduel', 260, 250, 'fd://now'],
   'Now is FanDuel\\'s in-play price, never DraftKings\\' +230 beside a FanDuel lock');
const ho = bestHandoffForPick(FD_LIVE, [DK_BOOKROW, FD_BOOKROW], h);
eq([ho.bookmaker, ho.price, ho.verb, ho.link], ['fanduel', 260, 'Bet', 'fd://now'], 'hand-off at FanDuel');
eq(bestHandoffForPick(FD_LIVE, [], h, undefined, ['draftkings']), null,
   'a member without FanDuel gets no hand-off, as on a pre-game card');
eq(bestHandoffForPick(FD_LIVE, [], h, undefined, ['fanduel']).bookmaker, 'fanduel', 'a FanDuel member does');
const chips = pickLineQuotes(FD_LIVE, [DK_BOOKROW, FD_BOOKROW]);
eq(chips.map((q) => [q.bookmaker, q.price, q.isRecord]), [['fanduel', 250, true]], 'one record chip, at FanDuel');
eq(currentLineQuotes(FD_LIVE, [DK_BOOKROW, FD_BOOKROW], h).map((q) => q.bookmaker), ['fanduel'], 'card quotes');
// A DraftKings-decided live pick is unchanged.
const dkLive = { ...FD_LIVE, decision_book: 'draftkings', decision_odds: 239 };
const dh = heroAmericanForPick(dkLive, DK_ROW, [DK_BOOKROW]);
eq([dh.book, dh.price, dh.untracked ?? false], ['draftkings', 230, false], 'DraftKings live pick');
eq(bestHandoffForPick(dkLive, [DK_BOOKROW], dh).bookmaker, 'draftkings', 'DraftKings hand-off');
""")


@node
def test_a_live_price_the_app_does_not_hold_is_said_so(tmp_path):
    _run(tmp_path, MARKETS_FILES + ["heroPriceText.ts"], LIVE + """
import { heroAmericanForPick, bestHandoffForPick } from './markets.ts';
import { lockedCaptionText } from './heroPriceText.ts';
// NCAAF stores only DraftKings' in-play rows: a FanDuel bet has no FanDuel row.
const h = heroAmericanForPick(FD_LIVE, DK_ROW, [DK_BOOKROW]);
eq([h.book, h.price, h.untracked, h.lockedPrice, h.link], ['fanduel', null, true, 250, 'fd://lock'],
   'no FanDuel row while DraftKings has one: not tracked, at FanDuel, with the lock link');
eq(lockedCaptionText(h), 'Locked +250 · live price not tracked after the bet', 'caption');
const ho = bestHandoffForPick(FD_LIVE, [DK_BOOKROW], h);
eq([ho.bookmaker, ho.price, ho.verb], ['fanduel', null, 'Open'], 'Open FanDuel, no number');
// No in-play rows at all: the read may have failed, so it stays "Now --".
const none = heroAmericanForPick(FD_LIVE, null, []);
eq([none.book, none.price, none.untracked ?? false], ['fanduel', null, false], 'nothing held');
// The NBA loop reads the books once an hour: never a live price, even a newer row.
const nba = { ...FD_LIVE, game_id: 'NBA_2026-11-04_BOS_MIL', model_id: 'nba_live_spread_q12', sport: 'NBA',
  pick_side: 'home', pick_label: 'BOS @ MIL MIL -4.5 (live)', scored_line: -4.5, decision_book: 'betmgm',
  decision_odds: -108, best_book: 'betmgm', best_bet_link: null };
const later = { bookmaker: 'betmgm', home_price: -125, spread_home: -4.5, snapshot_at: '2026-10-31T22:00:00+00:00' };
const nh = heroAmericanForPick(nba, null, [later]);
eq([nh.book, nh.price, nh.untracked], ['betmgm', null, true], 'NBA: not tracked, at BetMGM');
eq(bestHandoffForPick(nba, [later], nh).verb, 'Open', 'NBA: Open BetMGM');
""")


@node
def test_the_nba_deciding_books_hourly_row_never_reaches_the_slip(tmp_path):
    # fetchLivePicks hands each live pick liveBookRowsForPick's rows, and
    # parlay.legFromPick turns every non-DraftKings row there into an "Open
    # with" price. The NBA loop's row is up to an hour old: DraftKings' only.
    _run(tmp_path, MARKETS_FILES + ["myBooks.ts"], LIVE + """
import { liveBookRowsForPick } from './markets.ts';
import { liveNotAtMyBooksText, NOT_AT_MY_BOOKS } from './myBooks.ts';
const MGM = { bookmaker: 'betmgm', home_price: -125, spread_home: -4.5, snapshot_at: '2026-11-04T01:00:00+00:00' };
const nba = { ...FD_LIVE, model_id: 'nba_live_spread_q12', sport: 'NBA', decision_book: 'betmgm' };
eq(liveBookRowsForPick(nba, [DK_BOOKROW, MGM, FD_BOOKROW]).map((r) => r.bookmaker), ['draftkings'], 'NBA');
// Every other in-play pick keeps its own two books, never a third.
eq(liveBookRowsForPick(FD_LIVE, [DK_BOOKROW, MGM, FD_BOOKROW]).map((r) => r.bookmaker),
   ['draftkings', 'fanduel'], 'NCAAF at FanDuel');
// Off the member's books, an in-play card says where it was found: true even
// when DraftKings had the same number, which "not offered" was not.
eq(liveNotAtMyBooksText('MGM', '-108'), 'Found at MGM -108 · not one of your books', 'live none');
eq(NOT_AT_MY_BOOKS, 'Not offered at your books', 'pre-game none unchanged');
""")


@node
def test_the_lock_row_names_the_period_by_sport(tmp_path):
    _run(tmp_path, MARKETS_FILES, LIVE + """
import { pickTimingInfo } from './markets.ts';
const nba = pickTimingInfo({ ...FD_LIVE, sport: 'NBA', model_id: 'nba_live_spread_q12', inning_at_pick: 2 });
eq([nba.label.includes('· Q2'), nba.label.includes('inning')], [true, false], nba.label);
const mlb = pickTimingInfo({ ...FD_LIVE, sport: 'MLB', model_id: 'mlb_live_over_under', inning_at_pick: 7 });
eq(mlb.label.includes('· inning 7'), true, mlb.label);
const ncaaf = pickTimingInfo({ ...FD_LIVE, inning_at_pick: 2 });
eq(ncaaf.label.includes('· Q2'), true, ncaaf.label);
""")


@node
def test_the_nba_names_say_when_the_bet_is_placed_and_the_page_says_when_it_checks(tmp_path):
    _run(tmp_path, META_FILES + ["liveSports.ts"], """
import { MODEL_META, modelPageTiming } from './modelMeta.ts';
import { liveEmptySubtitle } from './liveSports.ts';
const names = ['nba_live_spread_q12']
  .map((id) => [MODEL_META[id].longLabel, MODEL_META[id].shortLabel]);
eq(names, [['NBA Early Live Spreads', 'Early Spread']], 'names');
// The quarter-3 moneyline and spread are held out of the live list
// (models/nba_live_ig2.HELD_OUT_RULES): no label until they ship.
eq([MODEL_META['nba_live_spread_q3'], MODEL_META['nba_live_ml_q3']], [undefined, undefined], 'held out');
for (const [label] of names) {
  if (/First Half|Quarter/.test(label)) throw new Error(`${label} names a period; the bet settles on the game`);
}
const q12 = modelPageTiming('nba_live_spread_q12');
for (const t of [q12]) {
  const all = [t.title, t.body, t.empty, t.note].join(' ');
  eq([t.title, all.includes('Live Signals'), all.includes('once an hour'), /pipeline|for the day|on the hour|tip off/.test(all)],
     ['Bets during the game', true, true, false], all);
}
eq([q12.body.includes('first and second quarters'), q12.body.includes('third quarter'),
    q12.body.includes('settles on the final score')], [true, false, true], 'when, and what it settles on');
const generic = modelPageTiming('ncaaf_live_win_prob');
eq([generic.title, generic.empty.includes('Live Signals'), /pipeline/.test(generic.body + generic.empty)],
   ['Bets during the game', true, false], 'other in-play models');
const empty = liveEmptySubtitle('NBA');
// One phrase for the window on both screens (the model page says the same).
eq([empty.includes('once an hour'), empty.includes('first and second quarters'), empty.includes('third quarter'),
    empty.includes('at most once'), /on the hour|tip off|tip-off/.test(empty), empty.includes('Zero of them')],
   [true, true, false, true, false, false], empty);
eq(liveEmptySubtitle('MLB').includes('DraftKings'), false, 'no DraftKings claim on the other sports');
""")


@node
def test_an_nba_game_leaves_the_live_board_after_three_and_a_half_hours(tmp_path):
    _run(tmp_path, MARKETS_FILES, """
import { gameStatus } from './format.ts';
const at = (h) => new Date(Date.now() - h * 3_600_000).toISOString();
eq(gameStatus({ sport: 'NBA', commence_time: at(3.25) }).kind, 'live', '3h15m in: still live');
eq(gameStatus({ sport: 'NBA', commence_time: at(3.75) }).kind, 'ended', '3h45m in: off the board');
eq(gameStatus({ sport: 'NHL', commence_time: at(3.75) }).kind, 'live', 'NHL unchanged');
""")


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def test_fetch_live_picks_reads_the_deciding_books_in_play_row():
    src = _read("lib/queries.ts")
    body = src[src.index("export async function fetchLivePicks("):]
    body = body[:body.index("\n}\n")]
    assert ".eq('bookmaker', 'draftkings')" not in body, (
        "the Live board reads DraftKings' in-play rows only, so a FanDuel bet's Now is DraftKings' number")
    # The deciding book's row is chosen by markets.liveBookRowsForPick, pinned
    # under node above (storedQuoteBook, and DraftKings' only for the NBA).
    assert "fetchLiveInplayAtBooks(" in body and "liveBookRowsForPick(" in body
    assert "rows.find((r) => r.bookmaker === MODEL_BOOK)" in body, "latestOdds must be DraftKings' row, not rows[0]"
    helper = src[src.index("async function fetchLiveInplayAtBooks("):]
    helper = helper[:helper.index("\n}\n")]
    assert "storedQuoteBook(p)" in helper and ".from('games')" in helper
    assert ".limit(1, { foreignTable: 'odds' })" in helper


def test_no_live_branch_defaults_to_draftkings():
    for rel in ("components/PickCard.tsx", "screens/PickDetailScreen.tsx", "lib/markets.ts"):
        src = _read(rel)
        assert not re.search(r"is_live === true \? MODEL_BOOK", src), rel
        assert not re.search(r"live \? MODEL_BOOK", src), rel
    assert "live picks are DraftKings only" not in _read("screens/PickDetailScreen.tsx")
