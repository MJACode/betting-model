/**
 * Betslip link templates — pure, so verify scripts can run it without
 * react-native. The opener lives in sportsbookLinks.ts.
 */

//
// Three books' betslip links arrive from the odds feed as TEMPLATES, measured
// against today's rows (2026-09-04):
//
//   betmgm          https://sports.{state}.betmgm.com/en/sports?options=…&type=Single
//   betrivers       https://{state}.betrivers.com/?page=sportsbook#event/…?coupon={pickType}|…|{wagerAmount}
//   williamhill_us  https://sportsbook.caesars.com/us/{state}/bet/betslip?selectionIds=…
//
// while DraftKings, FanDuel, ESPN BET and Hard Rock carry complete URLs. The
// app opened the templates verbatim: `{state}` is not a host, the open failed,
// and the fallback sent the member to the book's web root with no bet on the
// slip — "it didn't open my mgm app like it does for DK" (Matt). Filled, each
// is the book's own universal link, which iOS routes to the installed app the
// same way it routes DraftKings'.
//
// The state comes from the member (hooks/useBettingState.ts) — it cannot be
// inferred: a New Jersey account opened from a Pennsylvania IP is still a New
// Jersey account. BetRivers' two other placeholders take the values its
// coupon format documents for a single selection: `single` and an empty
// stake, which the book's slip then asks for. NOT yet exercised on a device —
// the sandbox cannot open an app — so verify_book_links.ts pins the shapes
// and the device pass is listed in the session log.

const STATE_PLACEHOLDER = '{state}';

/** Does this link need the member's state before it can be opened? */
export function linkNeedsState(link: string | null | undefined): boolean {
  return !!link && link.includes(STATE_PLACEHOLDER);
}

/**
 * Fill a betslip link's placeholders. Returns null when a placeholder cannot
 * be filled (no state set), so the caller never opens a template.
 */
export function fillBetslipLink(link: string, state: string | null): string | null {
  let out = link.trim();
  if (out.includes(STATE_PLACEHOLDER)) {
    if (!state) return null;
    out = out.split(STATE_PLACEHOLDER).join(state.toLowerCase());
  }
  out = out.split('{pickType}').join('single').split('{wagerAmount}').join('');
  // Anything still templated is a shape we have not seen; do not open it.
  return /\{[a-zA-Z]+\}/.test(out) ? null : out;
}

/**
 * Join several single-selection betslip links into ONE URL that puts every
 * linked pick on the book's slip.
 *
 * The hand-off sheet used to open only the first leg (`firstLink`) because
 * the Odds API stores one URL per outcome. That is the bug Matt reported:
 * a 3-pick slip opened the book with one pick. Books that publish a
 * multi-selection form of the SAME stored URL get combined here. A book
 * whose stored shape has no measured multi-selection form (Hard Rock,
 * BetRivers, Fanatics, …) returns null so the sheet keeps the per-leg
 * "Add to slip" buttons instead of inventing a URL.
 *
 * Evidence for each combiner, not a guess:
 *   draftkings  public DK URL uses `+` between outcome ids
 *               (sportsbook.draftkings.com/?outcomes=id1+id2+id3)
 *   fanduel     FanDuel share URLs index marketId[n]/selectionId[n]
 *   betmgm      official BetMGM docs: comma-separate `options`, type=combo
 *               (sportsapi.*.betmgm.com/restapi/generatedeeplink.html)
 *   caesars     stored `selectionIds` is plural; comma-join the UUIDs
 *   espnbet     stored links already index market_selection_id[0]
 *
 * Placeholders (`{state}`) stay in the string. `fillBetslipLink` still
 * runs at open time. `new URL()` cannot parse a `{state}` host, so every
 * parse here is string-level.
 */
export type BetslipCombineKind =
  | 'draftkings'
  | 'fanduel'
  | 'betmgm'
  | 'caesars'
  | 'espnbet';

export function betslipCombineKind(link: string): BetslipCombineKind | null {
  const u = link.trim();
  if (!u) return null;
  if (u.includes('draftkings.com') && /[?&]outcomes=/.test(u)) return 'draftkings';
  if (u.includes('fanduel.com') && /[?&](?:marketId|selectionId)/.test(u)) return 'fanduel';
  if (u.includes('betmgm.com') && /[?&]options=/.test(u)) return 'betmgm';
  if (u.includes('caesars.com') && /[?&]selectionIds=/.test(u)) return 'caesars';
  if (u.includes('thescore.bet') && /[?&]market_selection_id/.test(u)) return 'espnbet';
  return null;
}

export function combineBetslipLinks(
  links: readonly (string | null | undefined)[],
): string | null {
  const seen = new Set<string>();
  const cleaned: string[] = [];
  for (const raw of links) {
    const link = raw?.trim();
    if (!link || seen.has(link)) continue;
    seen.add(link);
    cleaned.push(link);
  }
  if (cleaned.length === 0) return null;
  if (cleaned.length === 1) return cleaned[0] ?? null;

  const kind = betslipCombineKind(cleaned[0] ?? '');
  if (!kind) return null;
  if (cleaned.some((l) => betslipCombineKind(l) !== kind)) return null;

  switch (kind) {
    case 'draftkings':
      return combineDraftKings(cleaned);
    case 'fanduel':
      return combineFanDuel(cleaned);
    case 'betmgm':
      return combineBetMgm(cleaned);
    case 'caesars':
      return combineCaesars(cleaned);
    case 'espnbet':
      return combineEspnBet(cleaned);
  }
}

/** Origin + path, stopping at `?` or a fragment `#`. `{state}` hosts stay intact. */
function originPath(url: string): string {
  const cut = url.search(/[?#]/);
  return (cut >= 0 ? url.slice(0, cut) : url).replace(/\/$/, '') || url;
}

/**
 * Raw (still-encoded) query value for `key`. Stops at a fragment `#` so
 * BetRivers' `#event/…` is not treated as part of `page=sportsbook`.
 */
function rawQueryValue(url: string, key: string): string | null {
  const q = url.indexOf('?');
  if (q < 0) return null;
  let qs = url.slice(q + 1);
  const hash = qs.indexOf('#');
  if (hash >= 0) qs = qs.slice(0, hash);
  for (const part of qs.split('&')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    if (part.slice(0, eq) === key) return part.slice(eq + 1);
  }
  return null;
}

function combineDraftKings(links: string[]): string | null {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const link of links) {
    const raw = rawQueryValue(link, 'outcomes');
    if (!raw) return null;
    for (const id of raw.split(/[+,]/)) {
      if (!id || seen.has(id)) continue;
      seen.add(id);
      ids.push(id);
    }
  }
  if (ids.length === 0) return null;
  // Literal `+`, matching DraftKings' own multi-outcome URLs. Encoding it
  // as %2B is a different string than the ones they publish.
  return `${originPath(links[0]!)}/?outcomes=${ids.join('+')}`;
}

function combineFanDuel(links: string[]): string | null {
  const pairs: { marketId: string; selectionId: string }[] = [];
  for (const link of links) {
    const found = fanDuelPairs(link);
    if (found.length === 0) return null;
    pairs.push(...found);
  }
  if (pairs.length === 0) return null;
  const q = pairs
    .map((p, i) => `marketId[${i}]=${p.marketId}&selectionId[${i}]=${p.selectionId}`)
    .join('&');
  const base = links[0]!.includes('/addToBetslip')
    ? links[0]!.replace(/\?[\s\S]*$/, '')
    : `${originPath(links[0]!)}/addToBetslip`;
  return `${base}?${q}`;
}

function fanDuelPairs(link: string): { marketId: string; selectionId: string }[] {
  const markets = indexedOrRepeated(link, 'marketId');
  const selections = indexedOrRepeated(link, 'selectionId');
  const n = Math.min(markets.length, selections.length);
  const out: { marketId: string; selectionId: string }[] = [];
  for (let i = 0; i < n; i++) {
    const marketId = markets[i];
    const selectionId = selections[i];
    if (marketId && selectionId) out.push({ marketId, selectionId });
  }
  return out;
}

/** `name`, `name[0]`, `name[1]`, … in URL order. */
function indexedOrRepeated(url: string, name: string): string[] {
  const q = url.indexOf('?');
  if (q < 0) return [];
  let qs = url.slice(q + 1);
  const hash = qs.indexOf('#');
  if (hash >= 0) qs = qs.slice(0, hash);
  const indexed: { i: number; v: string }[] = [];
  const plain: string[] = [];
  for (const part of qs.split('&')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    const key = part.slice(0, eq);
    const v = part.slice(eq + 1);
    if (key === name) {
      plain.push(v);
      continue;
    }
    const m = key.match(new RegExp(`^${name}\\[(\\d+)\\]$`));
    if (m) indexed.push({ i: Number(m[1]), v });
  }
  if (indexed.length > 0) {
    indexed.sort((a, b) => a.i - b.i);
    return indexed.map((x) => x.v);
  }
  return plain;
}

function combineBetMgm(links: string[]): string | null {
  const options: string[] = [];
  const seen = new Set<string>();
  for (const link of links) {
    const raw = rawQueryValue(link, 'options');
    if (!raw) return null;
    for (const id of raw.split(',')) {
      if (!id || seen.has(id)) continue;
      seen.add(id);
      options.push(id);
    }
  }
  if (options.length === 0) return null;
  // Official docs: chain selections with `,` and set type=combo for a parlay.
  return `${originPath(links[0]!)}?options=${options.join(',')}&type=combo`;
}

function combineCaesars(links: string[]): string | null {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const link of links) {
    const raw = rawQueryValue(link, 'selectionIds');
    if (!raw) return null;
    for (const id of raw.split(',')) {
      if (!id || seen.has(id)) continue;
      seen.add(id);
      ids.push(id);
    }
  }
  if (ids.length === 0) return null;
  return `${originPath(links[0]!)}?selectionIds=${ids.join(',')}`;
}

function combineEspnBet(links: string[]): string | null {
  const legs: { id: string; num: string; den: string }[] = [];
  for (const link of links) {
    const ids = indexedOrRepeated(link, 'market_selection_id');
    const nums = indexedOrRepeated(link, 'odds_numerator');
    const dens = indexedOrRepeated(link, 'odds_denominator');
    if (ids.length === 0) return null;
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i];
      if (!id) return null;
      // Stored ESPN BET rows always carry numerator/denominator beside the
      // id. A link that has the id and not the odds still combines — the
      // book's own single-id URLs work that way too.
      legs.push({
        id,
        num: nums[i] ?? '',
        den: dens[i] ?? '',
      });
    }
  }
  if (legs.length === 0) return null;
  const q = legs
    .map((l, i) => {
      let part = `market_selection_id[${i}]=${l.id}`;
      if (l.num) part += `&odds_numerator[${i}]=${l.num}`;
      if (l.den) part += `&odds_denominator[${i}]=${l.den}`;
      return part;
    })
    .join('&');
  return `${originPath(links[0]!)}/?${q}`;
}
