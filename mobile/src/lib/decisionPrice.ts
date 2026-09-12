/**
 * The price a pick was DECIDED at.
 *
 * Since 2026-09-09 (mike: "we should remove DK only - we want best lines for
 * us regardless") the scorer decides, sizes and settles a pre-game pick at the
 * best bettable price across the books at the DraftKings line, and records it
 * on the row as `decision_book` / `decision_odds` / `decision_implied_prob` /
 * `decision_edge`. `edge` and `dk_odds` keep their DraftKings meaning: the
 * reference line the model was scored at, and the basis of CLV.
 *
 * Rows from before the flip carry NULL in the decision columns. They were
 * decided at DraftKings, so falling back to `dk_odds` / `edge` is exact, not
 * an approximation -- which is why every reader of "the pick's price" or
 * "the pick's edge" goes through these two functions rather than the columns.
 *
 * No imports on purpose: markets.ts, thresholds.ts and the screens all call
 * this, and a helper that imported any of them would be a cycle.
 */

export interface DecisionPriced {
  dk_odds?: number | null;
  edge?: number | null;
  decision_odds?: number | null;
  decision_edge?: number | null;
}

/** American odds the pick was decided at; null on prob-only rows. */
export function decisionOdds(p: DecisionPriced): number | null {
  const d = p.decision_odds;
  if (d != null) return Number(d);
  return p.dk_odds == null ? null : Number(p.dk_odds);
}

/** model_probability − implied(decisionOdds): the edge the cut was applied to. */
export function decisionEdge(p: DecisionPriced): number {
  const d = p.decision_edge;
  if (d != null) return Number(d);
  return Number(p.edge ?? 0);
}

/**
 * The book the deciding price came from, or null when the row predates the
 * flip (callers fall back to the stored-book rule in markets.ts, which knows
 * about the NFL cards' soft books).
 */
export function decisionBook(p: { decision_book?: string | null }): string | null {
  const b = p.decision_book;
  return b ? String(b).toLowerCase() : null;
}

/**
 * The book whose LINE a pick was scored off, or null when it was DraftKings'.
 *
 * Since 2026-09-12 (mike: "Yes, scoring of other books lines") a player prop
 * DraftKings does not list at all is scored off the first bettable book that
 * does. On those rows `dk_odds` is NULL by design -- DraftKings never priced
 * the proposition -- so any copy that says "DraftKings" about the line, the
 * signal price or the close is wrong for them, and any read of `dk_odds`
 * renders a dash.
 */
export function lineBook(p: { line_book?: string | null }): string | null {
  const b = p.line_book;
  return b ? String(b).toLowerCase() : null;
}
