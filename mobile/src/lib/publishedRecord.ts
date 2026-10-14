/**
 * Which picks count toward CLV on the model detail screen.
 *
 * v_public_track_record counts a pick in its CLV columns when clv_pct is
 * present and clv_method is no_vig or zero_vig. Beat is clv_pct > 0 on that
 * set. is_live is not a second exclusion. A raw_one_sided close, a legacy
 * method, and a missing method do not count.
 *
 * The list itself is #942's rule: publishedRecordKeeps drops unpublished,
 * and an omitted stamp or unknown stays when the ledger did not finish.
 */
export const VIEW_CLV_METHODS = ['no_vig', 'zero_vig'] as const;

export function countsTowardViewClv(p: {
  clv_pct: number | null | undefined;
  clv_method?: string | null;
}): boolean {
  if (p.clv_pct == null || !Number.isFinite(Number(p.clv_pct))) return false;
  return (VIEW_CLV_METHODS as readonly string[]).includes(p.clv_method ?? '');
}
