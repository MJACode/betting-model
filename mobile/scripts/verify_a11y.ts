/**
 * Tap targets and VoiceOver — usability audit PR 4 (H9, M5, M7, M8, M9, M10,
 * M18, M19, M22, M25, M26, L13, and the ~50 unlabelled Pressables).
 *
 *   npx tsx scripts/verify_a11y.ts
 *   node --experimental-strip-types scripts/verify_a11y.ts   (what CI's pytest runs)
 *
 * Only node: imports, plus a dynamic import of the pure src/lib/a11y.ts, so it
 * runs the same under tsx and plain node.
 *
 * Static rules, over every .tsx under src/ plus App.tsx:
 *   1. Every <Pressable> has accessibilityRole AND accessibilityLabel.
 *   2. Every <Pressable>'s EFFECTIVE height — visual height + vertical
 *      hitSlop — is >= 44 (Reviewer #848). The visual height is read from its
 *      styles: height/minHeight, or 2 × vertical padding + the tallest child
 *      (icon size, or a Text line at ~1.19 × its font size); absoluteFill is a
 *      full-screen backdrop. Padding alone never counts. Values must be
 *      literals, spacing.* / font.size.*, or same-file consts; anything else
 *      is UNKNOWN and fails unless allowlisted ('geometry', with a reason).
 *      Pressables measured short when this rule landed are on SHORT_BASELINE
 *      (follow-up); new ones fail, fixed ones must come off.
 *   3. A Pressable with accessible={false} is not a VoiceOver element and is
 *      exempt from 1-2, but only as a tap-swallowing sheet (onPress={() => {}})
 *      or with a comment just above it saying why (VoiceOver).
 *   4. A Pressable hidden from VoiceOver (accessibilityElementsHidden +
 *      importantForAccessibility="no-hide-descendants") is exempt from 1 only.
 *   5. Every <TextInput> and <Switch> has accessibilityLabel.
 *   6. M7: every vertical ScrollView / FlatList / SectionList that the betslip
 *      bar can float over — not inside a <Modal>, not horizontal, not on a
 *      route in App.tsx's NO_BETSLIP_BAR_ROUTES — ends with BetslipBarSpacer
 *      (last ScrollView child, or the FlatList's ListFooterComponent).
 * Plus the H9 section (effective height of the chip rows inside their
 * horizontal ScrollViews, with the known-short cases and why), pins for the
 * tab semantics (H9/M8), the audited slop numbers, and the
 * spoken labels (M5/M8/M22/M19/M25), and behavioural checks of lib/a11y.ts.
 *
 * ALLOWLIST: entries only where the rule can't be met without a visible
 * layout change or where a label would make VoiceOver worse; each says why.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
let passes = 0;
function check(name: string, ok: boolean, detail?: unknown) {
  if (ok) {
    passes++;
    console.log(`  ✓ ${name}`);
  } else {
    failures++;
    console.log(`  ✗ FAIL ${name}${detail === undefined ? '' : ` — ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`}`);
  }
}

/** file:line-of-<Pressable> → reason. Keyed by a stable snippet, not a line number. */
const ALLOWLIST: { file: string; snippet: RegExp; rule: 'label' | 'size' | 'geometry'; reason: string }[] = [
  {
    file: 'src/screens/SettingsScreen.tsx',
    snippet: /style=\{\(\{ pressed \}\) => \[styles\.linkCard/,
    rule: 'label',
    reason:
      'LinkRow: role only, on purpose. An accessibilityLabel REPLACES what VoiceOver reads from the children, and five rows carry live status in `right` (Signed in, Active, connected books, "2 new replies"). Left to the children VoiceOver reads label, status and sub in order.',
  },
  {
    file: 'src/components/SportToggle.tsx',
    snippet: /accessibilityRole="tab"/,
    rule: 'geometry',
    reason:
      'Sport chips: the slop is TOGGLE_ROOM_ABOVE + reachAbove / 2 + reachBelow, props each screen sets — the H9 section below reads every <SportToggle> use and computes it (Picks 45, Models 45, Stats 35 listed short).',
  },
  {
    file: 'src/screens/PlayerStatsScreen.tsx',
    snippet: /hitSlop=\{\{ top: (4 \+ statReachAbove|4), bottom: (4|4 \+ rangeReachBelow),/,
    rule: 'geometry',
    reason:
      'Stat / range chips: statReachAbove and rangeReachBelow depend on the group header and the error state — the H9 section computes both (45.5pt; the stat row under the group tabs is listed short).',
  },
  {
    file: 'src/components/InfoTooltip.tsx',
    snippet: /label \? styles\.summaryBtn : styles\.iconBtn/,
    rule: 'geometry',
    reason:
      'Two shapes behind one conditional style: the bare icon is a 20pt glyph + 12 + 12 = 44pt; the summary row is 8 + 8 padding + a 13pt line + 24 slop = 55pt. The conditional isn’t statically readable.',
  },
  {
    file: 'src/components/CalendarGrid.tsx',
    snippet: /accessibilityLabel=\{spokenDate\(date\)\}/,
    rule: 'size',
    reason:
      'Calendar day: 44pt wide (6pt slop) but 36pt tall. 36pt is the row pitch (32pt circle + 2 + 2), so the 2pt vertical slop already tiles the weeks and more would steal the neighbouring week’s taps; 44pt tall needs a taller grid, a visible layout change — Designer (H9).',
  },
];

/**
 * Measured SHORT by the effective-height rule (visual + slop < 44pt) when it
 * replaced the old "any hitSlop passes / padding ≥ 12 is tall" rule for
 * Reviewer #848. Not yet fixed: each needs its neighbours checked before slop
 * grows (a stacked row can't tile past its pitch), and some are rows a parent
 * stretches, which this static estimate can't see. Listed on the PR as a
 * follow-up. [file, style refs, count] — a NEW short Pressable fails, and an
 * entry that is no longer short (or gone) fails as stale, so the list only
 * shrinks.
 */
const SHORT_BASELINE: [string, string, number][] = [
  ['src/components/AllBooksCard.tsx', 'row,rowReference', 1], // 39.8pt
  ['src/components/CalendarGrid.tsx', 'monthBtn', 2], // 42.0, 42.0pt
  ['src/components/DailyResultsModal.tsx', 'dateChip', 1], // 43.5pt
  ['src/components/DailyResultsModal.tsx', 'sportChip,sportChipActive', 1], // 41.5pt
  ['src/components/DiscordLinkModal.tsx', '', 1], // 39.5pt
  ['src/components/ManualBetModal.tsx', 'cancelBtn', 1], // 41.8pt
  ['src/components/NotificationsCard.tsx', '', 1], // 38.3pt
  ['src/components/OnboardingModal.tsx', '', 1], // 41.8pt
  ['src/components/ParlayDkHandoff.tsx', '', 1], // 40.0pt
  ['src/components/ParlayDkHandoff.tsx', 'addBtn,pressed', 1], // 43.5pt
  ['src/components/ParlayDkHandoff.tsx', 'openBtn,pressed', 1], // 43.0pt
  ['src/components/PlayerNewsSheet.tsx', 'readMore', 1], // 41.5pt
  ['src/components/SportsbookIndicator.tsx', 'row', 1], // 42.3pt
  ['src/components/TeamsBoard.tsx', '', 1], // 34.0pt
  ['src/components/TeamsBoard.tsx', 'lineWrap,pressed', 1], // 38.3pt
  ['src/components/TeamsBoard.tsx', 'noLinesRow,pressed', 1], // 42.7pt
  ['src/components/TeamsBoard.tsx', 'rowMain,pressed', 1], // 27.5pt
  ['src/components/filters/FilterBar.tsx', 'clearBtn,pressed', 1], // 34.3pt
  ['src/components/filters/FilterBar.tsx', 'pill,pressed', 1], // 38.3pt
  ['src/components/filters/FilterSheet.tsx', '', 1], // 41.8pt
  ['src/components/filters/FilterSheet.tsx', 'pressed', 1], // 31.5pt
  ['src/components/filters/FilterSheet.tsx', 'showBtn,showBtnEmpty,pressed', 1], // 43.0pt
  ['src/components/filters/GameFilterSection.tsx', '', 1], // 32.0pt
  ['src/screens/BuiltInModelDetailScreen.tsx', 'pickRow', 3], // 41.8, 41.8, 41.8pt
  ['src/screens/BuiltInModelDetailScreen.tsx', 'showMoreBtn', 4], // 39.5, 39.5, 39.5, 39.5pt
  ['src/screens/FeedbackScreen.tsx', 'chip,chipActive', 1], // 41.5pt
  ['src/screens/FeedbackScreen.tsx', 'pressed', 1], // 39.5pt
  ['src/screens/FeedbackScreen.tsx', 'sendBtn,sendBtnDisabled', 1], // 41.8pt
  ['src/screens/FeedbackScreen.tsx', 'threadCard,pressed', 1], // 42.0pt
  ['src/screens/FeedbackThreadScreen.tsx', 'errorCard', 1], // 39.5pt
  ['src/screens/FeedbackThreadScreen.tsx', 'sendBtn,sendBtnDisabled', 1], // 41.8pt
  ['src/screens/ModelDetailScreen.tsx', '', 1], // 30.0pt
  ['src/screens/ModelDetailScreen.tsx', 'pickRow', 2], // 41.8, 41.8pt
  ['src/screens/ModelEditScreen.tsx', '', 1], // 34.0pt
  ['src/screens/ModelEditScreen.tsx', 'addRuleBtn,pressed', 1], // 42.0pt
  ['src/screens/ModelEditScreen.tsx', 'chip,chipOn,pressed', 1], // 41.5pt
  ['src/screens/ModelEditScreen.tsx', 'deleteBtn', 1], // 41.8pt
  ['src/screens/ModelEditScreen.tsx', 'modalRow,pressed', 1], // 41.8pt
  ['src/screens/ParlayScreen.tsx', '', 1], // 40.0pt
  ['src/screens/ParlayScreen.tsx', 'addCustomBtn,manualBtn,pressed', 1], // 43.0pt
  ['src/screens/ParlayScreen.tsx', 'buildBtn,buildBtnDisabled,pressed', 1], // 43.0pt
  ['src/screens/ParlayScreen.tsx', 'buildBtn,manualBtn,pressed', 1], // 43.0pt
  ['src/screens/ParlayScreen.tsx', 'clearBtn,pressed', 1], // 43.0pt
  ['src/screens/ParlayScreen.tsx', 'missingNote,pressed', 1], // 39.5pt
  ['src/screens/PaywallScreen.tsx', '', 6], // 17.8, 38.3, 38.3, 38.3, 39.5, 39.5pt
  ['src/screens/PerformanceScreen.tsx', '', 3], // 39.5, 41.8, 41.8pt
  ['src/screens/PerformanceScreen.tsx', 'addManualBtn', 1], // 42.0pt
  ['src/screens/PerformanceScreen.tsx', 'reconnect,btnPressed', 1], // 40.0pt
  ['src/screens/PerformanceScreen.tsx', 'stakePill,stakePillActive', 1], // 41.5pt
  ['src/screens/PerformanceScreen.tsx', 'trackLink,btnPressed', 2], // 43.0, 43.0pt
  ['src/screens/PickDetailScreen.tsx', 'viewStatsBtn,viewStatsBtnPressed', 1], // 41.8pt
  ['src/screens/PlayerStatsScreen.tsx', 'gameRow', 1], // 34.3pt
  ['src/screens/SavedParlaysScreen.tsx', '', 1], // 43.0pt
  ['src/screens/SavedParlaysScreen.tsx', 'betBtn,pressed', 1], // 43.0pt
  ['src/screens/SavedParlaysScreen.tsx', 'clearAllBtn,pressed', 1], // 39.5pt
  ['src/screens/SavedParlaysScreen.tsx', 'deleteBtn,pressed', 1], // 40.0pt
  ['src/screens/SavedParlaysScreen.tsx', 'editBtn,pressed', 1], // 40.0pt
  ['src/screens/SavedParlaysScreen.tsx', 'newBtn,pressed', 1], // 43.0pt
  ['src/screens/SettingsScreen.tsx', 'bookPickRow', 2], // 41.8, 41.8pt
  ['src/screens/SettingsScreen.tsx', 'helplineRow', 1], // 39.5pt
  ['src/screens/SettingsScreen.tsx', 'pressed', 1], // 38.3pt
  ['src/screens/SettingsScreen.tsx', 'doneBtn,pressed', 1], // 41.8pt — #831's keyboard Done (landed on master after this rule); follow-up with the rest
  ['src/screens/SignInScreen.tsx', '', 3], // 17.8, 39.5, 39.5pt
  ['src/screens/StatsScreen.tsx', '', 2], // 32.0, 34.0pt
  ['src/screens/StatsScreen.tsx', 'clearBtn,pressed', 1], // 42.3pt
  ['src/screens/StatsScreen.tsx', 'filterBtn,pressed', 1], // 40.0pt
  ['src/screens/StatsScreen.tsx', 'noLinesRow,pressed', 1], // 40.7pt
  ['src/screens/StatsScreen.tsx', 'oddsWrap,pressed', 1], // 38.3pt
  ['src/screens/StatsScreen.tsx', 'pill,pressed', 1], // 34.3pt
  ['src/screens/StatsScreen.tsx', 'retryBtn,pressed', 1], // 39.5pt
];

function walk(d: string, out: string[] = []): string[] {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

/** The full opening tag starting at `start` (a '<'), braces and quotes aware. */
function openTag(src: string, start: number): string {
  let depth = 0;
  let q: string | null = null;
  for (let i = start + 1; i < src.length; i++) {
    const c = src[i];
    if (q) {
      if (c === q && src[i - 1] !== '\\') q = null;
      continue;
    }
    // Comments inside an expression (an apostrophe in one opened a "string").
    if (depth > 0 && c === '/' && src[i + 1] === '/') {
      const nl = src.indexOf('\n', i);
      i = nl < 0 ? src.length : nl;
      continue;
    }
    if (depth > 0 && c === '/' && src[i + 1] === '*') {
      const e = src.indexOf('*/', i + 2);
      i = e < 0 ? src.length : e + 1;
      continue;
    }
    if (depth > 0 && (c === '"' || c === "'" || c === '`')) {
      q = c;
      continue;
    }
    if (depth === 0 && c === '"') {
      q = c;
      continue;
    }
    if (c === '{') depth++;
    else if (c === '}') depth--;
    else if (c === '>' && depth === 0) return src.slice(start, i + 1);
  }
  return src.slice(start);
}

/** Body of `name: { … }` inside the file's StyleSheet.create. */
function styleBlock(src: string, name: string): string {
  const at = src.lastIndexOf('StyleSheet.create');
  if (at < 0) return '';
  const tail = src.slice(at);
  const m = new RegExp(`\\n\\s+${name}: \\{`).exec(tail);
  if (!m) return '';
  const base = at + m.index + m[0].length;
  let d = 1;
  let i = base;
  for (; i < src.length && d > 0; i++) {
    if (src[i] === '{') d++;
    else if (src[i] === '}') d--;
  }
  return src.slice(base, i);
}

const a11ySrc = read('src/lib/a11y.ts');
const ROW_SLOP_PAD = Number(/export const ROW_SLOP_PAD = (\d+);/.exec(a11ySrc)?.[1] ?? NaN);
const SPACING: Record<string, number> = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
const MIN_TAP_V = 44;
function num(v: string): number | null {
  const t = v.trim();
  if (/^\d+(\.\d+)?$/.test(t)) return Number(t);
  const s = /^spacing\.(\w+)(?:\s*\+\s*(\d+))?$/.exec(t);
  if (s && SPACING[s[1]] != null) return SPACING[s[1]] + Number(s[2] ?? 0);
  if (t === 'ROW_SLOP_PAD') return ROW_SLOP_PAD;
  return null;
}

// ── Effective height = visual height + vertical hitSlop (Reviewer #848) ─────
// Every value has to be READ from source: a literal, spacing.*, font.size.*,
// or a same-file `const NAME = …` of those. Anything else is unknown, and an
// unknown height or slop FAILS unless the Pressable is on the allowlist with a
// reason ('geometry'). Padding alone never counts as 44pt: the visual height
// is 2 × vertical padding + the tallest child (icon size, text line).
const FONT: Record<string, number> = { nano: 10, micro: 11, caption: 12, footnote: 13, body: 15, callout: 16, headline: 17, title3: 20, title2: 22, title1: 28, largeTitle: 34 };
/** iOS system-font line height at default Dynamic Type (~1.19 × size). */
const lineOf = (pt: number) => Math.round(pt * 1.19 * 10) / 10;
const RN_DEFAULT_FONT = 14;
const MIN_FONT = FONT.nano;

function fileConsts(src: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of src.matchAll(/^(?:export )?const (\w+) = ([^;\n]+);/gm)) out[m[1]] = m[2];
  return out;
}
/** Evaluate `a + b - c` of literals / spacing.* / font.size.* / file consts. */
function evalExpr(expr: string, consts: Record<string, string>, depth = 0): number | null {
  const t = expr.trim().replace(/^\((.*)\)$/, '$1');
  if (depth > 4 || t === '') return null;
  const terms = t.split(/\s*(?=[+-]\s)/);
  let total = 0;
  for (const raw of terms) {
    const sign = raw.trim().startsWith('-') && terms.length > 1 ? -1 : 1;
    const term = raw.trim().replace(/^[+-]\s*/, '');
    let v: number | null = null;
    if (/^\d+(\.\d+)?$/.test(term)) v = Number(term);
    else if (/^spacing\.\w+$/.test(term)) v = SPACING[term.slice(8)] ?? null;
    else if (/^font\.size\.\w+$/.test(term)) v = FONT[term.slice(10)] ?? null;
    else if (term === 'ROW_SLOP_PAD') v = ROW_SLOP_PAD;
    else if (/^\w+$/.test(term) && consts[term] != null) v = evalExpr(consts[term], consts, depth + 1);
    if (v == null) return null;
    total += sign * v;
  }
  return total;
}
function styleProp(text: string, prop: string, consts: Record<string, string>): number | null | undefined {
  const m = new RegExp(`(?:^|[\\s{,])${prop}: ([^,\\n}]+)`).exec(text);
  if (!m) return undefined;
  return evalExpr(m[1], consts);
}

/** Vertical slop (top + bottom); null when it can't be read. 0 without hitSlop. */
function verticalSlop(tag: string, consts: Record<string, string>): number | null {
  if (!/hitSlop=/.test(tag)) return 0;
  const n = /hitSlop=\{([^{}]+)\}/.exec(tag);
  if (n) {
    const v = evalExpr(n[1], consts);
    return v == null ? null : 2 * v;
  }
  const o = /hitSlop=\{\{([^}]*)\}\}/.exec(tag);
  if (!o) return null;
  const read = (k: string) => {
    const m = new RegExp(`\\b${k}: ([^,}]+)`).exec(o[1]);
    return m ? evalExpr(m[1], consts) : 0;
  };
  const t = read('top');
  const b = read('bottom');
  return t == null || b == null ? null : t + b;
}

/** Tallest child: icon `size={N}` or a Text line; null when nothing readable. */
function contentHeight(body: string, src: string, consts: Record<string, string>): number | null {
  let h: number | null = null;
  const up = (v: number) => { h = Math.max(h ?? 0, v); };
  for (const m of body.matchAll(/\bsize=\{([^}]+)\}/g)) {
    const v = evalExpr(m[1], consts);
    if (v != null) up(v);
  }
  for (const m of body.matchAll(/<Text\b/g)) {
    const tag = openTag(body, m.index!);
    const styleAttr = /style=\{([\s\S]*?)\}\s*(?:\w+=|>|\/>)/.exec(tag)?.[1] ?? '';
    const refs = [...styleAttr.matchAll(/styles\.(\w+)/g)].map((x) => x[1]);
    const text = [styleAttr, ...refs.map((r) => styleBlock(src, r))].join('\n');
    const lh = styleProp(text, 'lineHeight', consts);
    const fs = styleProp(text, 'fontSize', consts);
    const unresolved = /style=\{(?!\[?\s*styles\.)/.test(tag) && refs.length === 0;
    if (typeof lh === 'number') up(lh);
    else if (typeof fs === 'number') up(lineOf(fs));
    else up(lineOf(unresolved || fs === null ? MIN_FONT : RN_DEFAULT_FONT));
  }
  return h;
}

/** Visual height from the Pressable's own styles; null when unknown. */
function visualHeight(styleText: string, body: string | null, src: string, consts: Record<string, string>): number | null {
  if (/StyleSheet\.absoluteFill|absoluteFillObject/.test(styleText)) return Infinity;
  const explicit = [styleProp(styleText, 'minHeight', consts), styleProp(styleText, 'height', consts)].filter(
    (v): v is number => typeof v === 'number',
  );
  const pv = styleProp(styleText, 'paddingVertical', consts);
  const pa = styleProp(styleText, 'padding', consts);
  const pt = styleProp(styleText, 'paddingTop', consts);
  const pb = styleProp(styleText, 'paddingBottom', consts);
  const padOk = [pv, pa, pt, pb].every((v) => v !== null);
  const pad = typeof pv === 'number' ? 2 * pv : (typeof pt === 'number' || typeof pb === 'number') ? (pt ?? pa ?? 0) + (pb ?? pa ?? 0) : typeof pa === 'number' ? 2 * pa : 0;
  const content = body == null ? 0 : contentHeight(body, src, consts);
  const fromContent = padOk && content != null ? pad + content : null;
  const best = Math.max(...explicit, fromContent ?? -1);
  return best >= 0 ? best : null;
}

const files = [...walk(join(ROOT, 'src')), join(ROOT, 'App.tsx')];
const allowHit = new Set<string>();
let pressables = 0;
let exemptSwallow = 0;
let exemptHidden = 0;
const missing: string[] = [];
const small: string[] = [];
const unknown: string[] = [];
let measured = 0;
const baselineShort: string[] = [];
const baselineLeft = new Map<string, number>(SHORT_BASELINE.map(([f, r, n]) => [`${f}|${r}`, n]));
const badExempt: string[] = [];

for (const f of files) {
  const rel = relative(ROOT, f);
  const src = readFileSync(f, 'utf-8');
  for (const m of src.matchAll(/<Pressable\b/g)) {
    pressables++;
    const tag = openTag(src, m.index!);
    const line = src.slice(0, m.index).split('\n').length;
    const where = `${rel}:${line}`;
    const allowed = (rule: 'label' | 'size' | 'geometry') => {
      const hit = ALLOWLIST.find((a) => a.file === rel && a.rule === rule && a.snippet.test(tag));
      if (hit) allowHit.add(`${hit.file}|${hit.rule}`);
      return Boolean(hit);
    };

    if (/accessible=\{false\}/.test(tag)) {
      const above = src.slice(0, m.index).split('\n').slice(-10).join('\n');
      if (/onPress=\{\(\) => \{\}\}/.test(tag) || /accessible=\{false\}[\s\S]*VoiceOver|VoiceOver[\s\S]*accessible=\{false\}/.test(above)) {
        exemptSwallow++;
      } else {
        badExempt.push(where);
      }
      continue;
    }

    const hidden = /accessibilityElementsHidden/.test(tag) && /importantForAccessibility="no-hide-descendants"/.test(tag);
    if (hidden) exemptHidden++;
    const role = /accessibilityRole=/.test(tag);
    const label = /accessibilityLabel=/.test(tag);
    if (!hidden && (!role || !label) && !allowed('label')) {
      missing.push(`${where}${role ? '' : ' role'}${label ? '' : ' label'}`);
    }

    const refs = [...tag.matchAll(/styles\.(\w+)/g)].map((x) => x[1]);
    const styleText = [tag, ...refs.map((r) => styleBlock(src, r))].join('\n');
    const consts = fileConsts(src);
    const body = tag.endsWith('/>') ? null : src.slice(m.index! + tag.length, closeOf(src, m.index!, 'Pressable'));
    const vh = visualHeight(styleText, body, src, consts);
    const vs = verticalSlop(tag, consts);
    measured++;
    if (vh == null || vs == null) {
      if (!allowed('geometry')) unknown.push(`${where} [${refs.join(',')}] ${vh == null ? 'height?' : `h=${vh}`} ${vs == null ? 'slop?' : `+${vs}`}`);
      continue;
    }
    if (vh + vs < MIN_TAP_V && !allowed('size')) {
      const key = `${rel}|${refs.join(',')}`;
      const eff = `${where} [${refs.join(',')}] ${vh}+${vs}=${Math.round((vh + vs) * 10) / 10}`;
      if ((baselineLeft.get(key) ?? 0) > 0) {
        baselineLeft.set(key, baselineLeft.get(key)! - 1);
        baselineShort.push(eff);
      } else small.push(eff);
    }
  }
}

console.log('\nRules 1–4: Pressables');
// The rule itself (Reviewer #848): padding alone is not 44pt, and an
// unreadable slop is unknown, not a pass.
{
  const src = "const styles = StyleSheet.create({\n  btn: {\n    padding: 12,\n  },\n  t: {\n    fontSize: font.size.footnote,\n  },\n});";
  const body = '<Text style={styles.t}>Go</Text>';
  const vh = visualHeight('styles.btn\n' + styleBlock(src, 'btn'), body, src, {});
  check(`rule: padding 12 + a 13pt line is ${vh}pt, not "tall enough"`, vh === 24 + lineOf(13) && (vh ?? 99) < MIN_TAP_V);
  check('rule: hitSlop={x} with x unreadable is unknown (null), hitSlop={SLOP} with const SLOP = spacing.sm reads 16',
    verticalSlop('<Pressable hitSlop={x}>', {}) === null && verticalSlop('<Pressable hitSlop={SLOP}>', { SLOP: 'spacing.sm' }) === 16);
  check('rule: minHeight 44 reads 44; absoluteFill is a full-screen backdrop', visualHeight('minHeight: 44', null, '', {}) === 44 && visualHeight('StyleSheet.absoluteFill', null, '', {}) === Infinity);
}
check(`every Pressable has accessibilityRole + accessibilityLabel (${missing.length} missing)`, missing.length === 0, missing.join('; '));
check(`every Pressable is ≥ 44pt tall, visual + slop (${small.length} short)`, small.length === 0, small.join('; '));
check(`every Pressable's height and slop are readable, or allowlisted with a reason (${unknown.length} unknown)`, unknown.length === 0, unknown.join('; '));
const stale = [...baselineLeft].filter(([, n]) => n > 0).map(([k, n]) => `${k} ×${n}`);
check(`short baseline has no stale entries (fixed or moved ones must come off; ${stale.length} stale)`, stale.length === 0, stale.join('; '));
console.log(`  (${measured} measured; ${baselineShort.length} known short on the baseline — follow-up, listed on the PR)`);
check('accessible={false} only on tap-swallowing sheets or with a VoiceOver reason above it', badExempt.length === 0, badExempt.join('; '));
check('every allowlist entry is still needed (no stale entries)', ALLOWLIST.every((a) => allowHit.has(`${a.file}|${a.rule}`)),
  ALLOWLIST.filter((a) => !allowHit.has(`${a.file}|${a.rule}`)).map((a) => a.file));
check('every allowlist entry carries a reason', ALLOWLIST.every((a) => a.reason.length > 40));
check('allowlist stays small (≤ 6 entries)', ALLOWLIST.length <= 6, ALLOWLIST.length);
console.log(`  (${pressables} Pressables; ${exemptSwallow} non-elements via accessible={false}; ${exemptHidden} hidden with an accessible alternative; ${ALLOWLIST.length} allowlisted)`);

// Reviewer #848: a bare "Close" doesn't say WHAT closes. Every close control
// (backdrop or X) names its sheet: "Close stake editor".
const bareClose: string[] = [];
for (const f of files) {
  const src = readFileSync(f, 'utf-8');
  for (const m of src.matchAll(/accessibilityLabel=(?:"Close"|\{'Close'\}|\{"Close"\})/g)) bareClose.push(`${relative(ROOT, f)}:${src.slice(0, m.index).split('\n').length}`);
}
check(`every close control names what it closes (${bareClose.length} bare "Close")`, bareClose.length === 0, bareClose.join('; '));

console.log('\nRule 5: text inputs and switches');
const unlabelled: string[] = [];
let inputs = 0;
for (const f of files) {
  const src = readFileSync(f, 'utf-8');
  for (const m of src.matchAll(/<(TextInput|Switch)\s/g)) {
    inputs++;
    if (!/accessibilityLabel=/.test(openTag(src, m.index!))) {
      unlabelled.push(`${relative(ROOT, f)}:${src.slice(0, m.index).split('\n').length}`);
    }
  }
}
check(`every TextInput / Switch has accessibilityLabel (${inputs} checked)`, unlabelled.length === 0, unlabelled.join('; '));

console.log('\nRule 6: M7 — the betslip bar never covers the last row');
const app = read('App.tsx');
const noBarRoutes = [...(/NO_BETSLIP_BAR_ROUTES = new Set<string>\(\[([^\]]*)\]\)/.exec(app)?.[1] ?? '').matchAll(/'(\w+)'/g)].map((x) => x[1]);
check('App.tsx: NO_BETSLIP_BAR_ROUTES parsed', noBarRoutes.length > 0, noBarRoutes);
const exemptFiles = new Set<string>();
for (const r of noBarRoutes) {
  const comp = new RegExp(`name="${r}"\\s*\\n?\\s*component=\\{(\\w+)\\}`).exec(app)?.[1];
  const imp = comp ? new RegExp(`import \\{[^}]*\\b${comp}\\b[^}]*\\} from '@/([^']+)'`).exec(app)?.[1] : null;
  if (imp) exemptFiles.add(`src/${imp}.tsx`);
}
check('no-bar routes resolve to screen files', exemptFiles.size === noBarRoutes.length, [...exemptFiles]);

function ranges(src: string, open: RegExp, close: string): [number, number][] {
  const out: [number, number][] = [];
  for (const m of src.matchAll(open)) {
    const end = src.indexOf(close, m.index!);
    out.push([m.index!, end < 0 ? src.length : end]);
  }
  return out;
}
function closeOf(src: string, start: number, tagName: string): number {
  const re = new RegExp(`<${tagName}\\b|</${tagName}>`, 'g');
  re.lastIndex = start;
  let depth = 0;
  for (let m = re.exec(src); m; m = re.exec(src)) {
    if (m[0].startsWith('</')) {
      depth--;
      if (depth === 0) return m.index;
    } else {
      const t = openTag(src, m.index);
      if (!t.endsWith('/>')) depth++;
      else if (depth === 0) return m.index + t.length;
    }
  }
  return src.length;
}
const uncovered: string[] = [];
let covered = 0;
for (const f of files) {
  const rel = relative(ROOT, f);
  if (exemptFiles.has(rel)) continue;
  const src = readFileSync(f, 'utf-8');
  const modals = ranges(src, /<Modal\b/g, '</Modal>');
  for (const m of src.matchAll(/(?<![\w.])<(ScrollView|FlatList|SectionList)\s/g)) {
    if (/(useRef|createRef|RefObject)$/.test(src.slice(Math.max(0, m.index! - 12), m.index))) continue;
    const at = m.index!;
    const tag = openTag(src, at);
    if (/\bhorizontal\b/.test(tag)) continue;
    if (modals.some(([a, b]) => at > a && at < b)) continue;
    const ok =
      m[1] === 'ScrollView'
        ? /<BetslipBarSpacer \/>\s*<\/ScrollView>/.test(src.slice(at, closeOf(src, at, 'ScrollView') + '</ScrollView>'.length))
        : /ListFooterComponent=\{[\s\S]*BetslipBarSpacer/.test(tag);
    if (ok) covered++;
    else uncovered.push(`${rel}:${src.slice(0, at).split('\n').length} ${m[1]}`);
  }
}
check(`every vertical list the bar floats over ends with BetslipBarSpacer (${covered} covered)`, uncovered.length === 0, uncovered.join('; '));
check('at least 20 lists covered (the audit saw the bar over every tab)', covered >= 20, covered);
const bar = read('src/components/BetslipBar.tsx');
check('BetslipBar publishes its measured height (+ float gap) from onLayout',
  /onLayout=\{\(e\) => \{\s*barHeight\.current = e\.nativeEvent\.layout\.height;\s*setBetslipBarInset\(barHeight\.current \+ floatGap\);/.test(bar));
check('BetslipBar publishes 0 when hidden and on unmount',
  /setBetslipBarInset\(visible && barHeight\.current > 0 \? barHeight\.current \+ floatGap : 0\)/.test(bar) && /useEffect\(\(\) => \(\) => setBetslipBarInset\(0\), \[\]\)/.test(bar));
check('BetslipBar: the publish effects run before the early return (hooks order)',
  bar.indexOf('setBetslipBarInset(visible') < bar.indexOf('if (!visible) return null;'));
const spacer = read('src/components/BetslipBarSpacer.tsx');
check('BetslipBarSpacer: height = useBetslipBarInset(), nothing while the bar is hidden',
  /const inset = useBetslipBarInset\(\);/.test(spacer) && /if \(inset <= 0\) return null;/.test(spacer) && /height: inset/.test(spacer));

console.log('\nH9 / M8 / L13 — tabs');
const toggle = read('src/components/SportToggle.tsx');
check('SportToggle: tablist container, tab items with selected', /accessibilityRole="tablist"/.test(toggle) && /accessibilityRole="tab"/.test(toggle) && /accessibilityState=\{\{ selected: active \}\}/.test(toggle) && !/accessibilityRole="button"/.test(toggle));
check('SportToggle: slop = the in-bounds room + the reach the screen grants; chips abut, so only the ends take side slop',
  /const TOGGLE_ROOM_ABOVE = spacing\.sm \+ 2;/.test(toggle) &&
    /top: TOGGLE_ROOM_ABOVE \+ reachAbove,\s*bottom: 2 \+ reachBelow,\s*left: i === 0 \? 2 : 0,\s*right: i === SPORTS\.length - 1 \? 2 : 0,/.test(toggle) &&
    /const reach = reachFrame\(reachAbove, reachBelow, \{ raise: reachBelow > 0, marginTop \}\);/.test(toggle) &&
    /style=\{reach\.frame\}/.test(toggle) && /contentContainerStyle=\{\[styles\.scroll, reach\.content\]\}/.test(toggle));
const record = read('src/screens/TrackRecordScreen.tsx');
check('TrackRecord sport tabs: tablist + tab + selected + label', /accessibilityRole="tablist"/.test(record) && /accessibilityRole="tab"/.test(record) && /accessibilityState=\{\{ selected: active \}\}/.test(record) && /accessibilityLabel=\{s === 'All' \? 'All sports' : s\}/.test(record));
check('TrackRecord sport tabs: ROW_SLOP_PAD slop inside a framed horizontal ScrollView (L13: one row, no wrap)',
  /hitSlop=\{\{ top: ROW_SLOP_PAD, bottom: ROW_SLOP_PAD/.test(record) && /marginTop: -ROW_SLOP_PAD/.test(record) && /paddingVertical: ROW_SLOP_PAD/.test(record) && !/sportTabs: \{[^}]*flexWrap/.test(record));
const home = read('src/screens/PicksHomeScreen.tsx');
check('PicksHome sub-tabs: tablist + tab + selected', /<View style=\{styles\.subTabs\} accessibilityRole="tablist">/.test(home) && /hitSlop=\{\{ top: SUBTAB_REACH_ABOVE, bottom: 2 \+ SUBTAB_REACH_BELOW \}\}\s*accessibilityRole="tab"\s*accessibilityState=\{\{ selected: active \}\}/.test(home));
const models = read('src/screens/ModelsScreen.tsx');
check('Models segment: tablist + tab + 9pt slop on a ~27pt pill', /<View style=\{styles\.segmentRow\} accessibilityRole="tablist">/.test(models) && /hitSlop=\{\{ top: 9, bottom: 9/.test(models) && /accessibilityRole="tab"/.test(models));
const groupTabs = read('src/components/GroupTabs.tsx');
check('GroupTabs: tablist + tab + label', /accessibilityRole="tablist"/.test(groupTabs) && /accessibilityRole="tab"/.test(groupTabs) && /accessibilityLabel=\{(?:accessibilityLabelFor \? accessibilityLabelFor\(item\) : )?item\}/.test(groupTabs));

console.log('\nH9 — effective target height of the chip rows (visual + in-bounds slop)');
// A horizontal ScrollView takes no touches outside itself, so a chip's
// effective height is its visual height plus only the slop inside the row's
// bounds: its own padding/margin plus what reachFrame lets the frame take.
// Visual heights at default text size: a 13pt line is ~15.5pt.
const LINE13 = 15.5;
const intOf = (src: string, re: RegExp) => Number(re.exec(src)?.[1] ?? NaN);
const TOGGLE_H = intOf(toggle, /export const TOGGLE_CHIP_H = (\d+);/);
const TOGGLE_IN = { above: 10, below: 2 }; // wrap marginTop 8 + padding 2; padding 2
function toggleUse(src: string, marker: RegExp): { above: number; below: number } | null {
  const at = src.search(marker);
  if (at < 0) return null;
  const tag = openTag(src, at);
  return { above: Number(/reachAbove=\{(\d+)\}/.exec(tag)?.[1] ?? 0), below: Number(/reachBelow=\{(\d+)\}/.exec(tag)?.[1] ?? 0) };
}
const picksToggle = toggleUse(home, /<SportToggle\b/);
const modelsSrc = read('src/screens/ModelsScreen.tsx');
const modelsToggle = toggleUse(modelsSrc, /<SportToggle\b/);
const toggleEff = (u: { above: number; below: number } | null) => (u ? TOGGLE_H + TOGGLE_IN.above + u.above + TOGGLE_IN.below + u.below : NaN);
check(`SportToggle on Picks: ${toggleEff(picksToggle)}pt (reach ${picksToggle?.above} over the subtitle text, ${picksToggle?.below} into the gap)`, toggleEff(picksToggle) >= MIN_TAP_V);
check(`SportToggle on Models: ${toggleEff(modelsToggle)}pt (reach ${modelsToggle?.above} of its own 12pt margin)`,
  toggleEff(modelsToggle) >= MIN_TAP_V && /<SportToggle marginTop=\{spacing\.md\} reachAbove=\{(\d+)\} \/>/.test(modelsSrc) && (modelsToggle?.above ?? 99) <= 12);
// Picks: the 12pt between the sport chips and the sub-tabs is shared.
const subAbove = intOf(home, /const SUBTAB_REACH_ABOVE = (\d+);/);
const subBelow = intOf(home, /const SUBTAB_REACH_BELOW = (\d+);/);
const subH = 2 * SPACING.sm + LINE13;
check(`Picks: sport chips and sub-tabs tile the 12pt gap (${TOGGLE_IN.below + (picksToggle?.below ?? 0)} + ${subAbove})`,
  TOGGLE_IN.below + (picksToggle?.below ?? 0) + subAbove === 2 + SPACING.sm + 2 && /reachFrame\(reachAbove, reachBelow, \{ raise: reachBelow > 0/.test(toggle));
check(`Picks sub-tabs: ${subAbove} + ${subH} + ${2 + subBelow} = ${subAbove + subH + 2 + subBelow}pt (below reaches ${subBelow} of the header's 12pt padding)`,
  subAbove + subH + 2 + subBelow >= MIN_TAP_V && subBelow <= 12 && /const subTabsReach = reachFrame\(0, SUBTAB_REACH_BELOW\);/.test(home) && /style=\{subTabsReach\.frame\}/.test(home));
// PlayerStats: two chip rows sharing an 8pt gap (4 each).
const ps = read('src/screens/PlayerStatsScreen.tsx');
const chipH = 2 * 7 + LINE13 + 2; // paddingVertical 7, 1pt border
const rangeBelow = intOf(ps, /const rangeReachBelow = error \? 0 : (\d+);/);
check(`PlayerStats range chips: 4 + ${chipH} + ${4 + rangeBelow} = ${4 + chipH + 4 + rangeBelow}pt (raised over the next sibling; 0 over the ErrorBanner)`,
  4 + chipH + 4 + rangeBelow >= MIN_TAP_V && /hitSlop=\{\{ top: 4, bottom: 4 \+ rangeReachBelow, left: 2, right: 2 \}\}/.test(ps) && /reachFrame\(0, rangeReachBelow, \{ raise: rangeReachBelow > 0 \}\)/.test(ps));
const statAbove = intOf(ps, /const statReachAbove = [^?]+\? (\d+) : 0;/);
check(`PlayerStats stat chips under the group header: ${statAbove + 4} + ${chipH} + 4 = ${statAbove + 4 + chipH + 4}pt`,
  statAbove + 4 + chipH + 4 >= MIN_TAP_V && /hitSlop=\{\{ top: 4 \+ statReachAbove, bottom: 4, left: 2, right: 2 \}\}/.test(ps));
// Known short, each with the reason (reported on the PR). A NEW short case
// fails: every <SportToggle> must be on Picks / Models (reached) or listed here.
const H9_SHORT: { where: string; eff: number; reason: string }[] = [
  { where: 'src/screens/StatsScreen.tsx', eff: TOGGLE_H + TOGGLE_IN.above + TOGGLE_IN.below,
    reason: 'Stats header: 39.5pt from the sportsbook line to the next control (Players/Teams bar or the stat group pill), both interactive (with no player board, the Settings button’s slop sits above instead); the chips (23pt) cannot reach 44 without covering one of them — needs ~5pt more header, a visible change (Designer).' },
  { where: 'src/screens/PlayerStatsScreen.tsx#stat-under-tabs', eff: 4 + chipH + 4,
    reason: 'PlayerStats stat chips under the group tabs: flush against the tab bar above, 8pt gap shared 4/4 with the range chips below — no whitespace left (Designer).' },
  { where: 'src/components/CalendarGrid.tsx', eff: 36,
    reason: 'Calendar day: 36pt is the row pitch; 44pt wide, 36 tall (see the size allowlist).' },
];
const statsUses = (read('src/screens/StatsScreen.tsx').match(/<SportToggle\b[^>]*\/>/g) ?? []);
check(`every <SportToggle> is reached (Picks, Models) or listed short (${statsUses.length} on Stats, all plain)`,
  statsUses.length > 0 && statsUses.every((t) => t === '<SportToggle />') &&
    files.every((f) => { const r = relative(ROOT, f); const n = (readFileSync(f, 'utf-8').match(/<SportToggle\b/g) ?? []).length; return n === 0 || ['src/screens/PicksHomeScreen.tsx', 'src/screens/ModelsScreen.tsx', 'src/screens/StatsScreen.tsx'].includes(r); }));
check('every H9 short entry carries a reason and is really short', H9_SHORT.every((x) => x.reason.length > 40 && x.eff < MIN_TAP_V));
for (const x of H9_SHORT) console.log(`  (short: ${x.where} ≈ ${x.eff}pt — ${x.reason})`);

console.log('\nM8 / M5 / M22 — spoken card');
const card = read('src/components/PickCard.tsx');
check('PickCard label carries game status + time (gameStatusSpeech)', /gameStatusSpeech\(gameStatus\(game, liveState\), gameDayLabelET\(game\?\.commence_time\)\)/.test(card));
check('PickCard label carries the stake, in words', /stakeCaption \? `Stake \$\{unitsSpeech\(stakeCaption\)\}` : null/.test(card));
check('PickCard label carries when it posted and the started line', /timing \? timing\.label : null/.test(card) && /startedSpoken,/.test(card));
check('PickCard: Track / Betslip / book offered as accessibilityActions', /accessibilityActions=\{a11yActions\.length > 0 \? a11yActions : undefined\}/.test(card) && /name === 'track' && canTrack/.test(card) && /name === 'slip' && canSlip/.test(card) && /name === 'book' && handoff/.test(card));
check('PickCard: "Game started" is spoken once — in cardLabel (gameStartedSpeech, full book name), the nested line hidden',
  /startedSpoken,\n/.test(card) && /gameStartedSpeech\(decisionOdds\(pick\), bookName\(storedQuoteBook\(pick\)\)\)/.test(card) &&
    /style=\{styles\.startedLine\}\s*accessibilityRole="text"\s*accessibilityElementsHidden\s*importantForAccessibility="no-hide-descendants"/.test(card));
const detail = read('src/screens/PickDetailScreen.tsx');
check('Pick Detail: the started card speaks gameStartedSpeech, like the card (#847)', /styles\.startedCard\}[\s\S]{0,120}accessibilityLabel=\{gameStartedSpeech\(decisionOdds\(pick\), bookName\(storedQuoteBook\(pick\)\)\)\}/.test(detail));
check('PicksHome: "—" header counts speak "count not available", like the sub-tabs (#845)', /<Text style=\{styles\.subtitle\} accessibilityLabel=\{unknownCountSpeech\(unitsSpeech\(subtitle\)\)\}>/.test(read('src/screens/PicksHomeScreen.tsx')));
check('TrackRecord: "— settled picks" speaks "count not available"', /accessibilityLabel=\{notLoaded \? unknownCountSpeech\('— settled picks'\) : undefined\}/.test(read('src/screens/TrackRecordScreen.tsx')));
check('PickCard: "Price check" is spoken once — in cardLabel, the nested chip hidden',
  /flagged \? 'Price check: this price looks off, so edge and EV are hidden' : `Edge \$\{edgeText\}`/.test(card) &&
    /styles\.priceCheckChip\]\}\s*accessibilityRole="text"\s*accessibilityElementsHidden\s*importantForAccessibility="no-hide-descendants"/.test(card) &&
    !/accessibilityLabel="Price check/.test(card));
check('PickCard: no nested element inside the card is separately accessible', !/\n\s+accessible\n/.test(card.slice(card.indexOf('accessibilityLabel={cardLabel}'))));
check('SharpScorePill: "Sharp score N of 100, band" (M5)', /accessibilityLabel=\{sharpScoreSpeech\(score, BAND_WORD\[band\]\)\}/.test(read('src/components/SharpScorePill.tsx')));
const pill = read('src/components/GameStatusPill.tsx');
check('GameStatusPill: live and final speak gameStatusSpeech (M22)', (pill.match(/accessibilityLabel=\{spoken \?\? '(Live|Final)'\}/g) ?? []).length === 2 && /accessibilityLabel=\{spoken \?\? undefined\}/.test(pill));

console.log('\nM9 / M10 / M18 / M19 / M25 / M26');
const perf = read('src/screens/PerformanceScreen.tsx');
check('M10: stake chip 12pt slop (was 6) + role + label', /hitSlop=\{\{ top: 12, bottom: 12, left: 8, right: 8 \}\}\s*accessibilityRole="button"\s*accessibilityLabel=\{`Edit stake, /.test(perf));
check('M10: stake pills are radios with checked state + 8pt slop', /accessibilityRole="radiogroup"/.test(perf) && /hitSlop=\{\{ top: 8, bottom: 8, left: 2, right: 2 \}\}\s*accessibilityRole="radio"\s*accessibilityState=\{\{ checked: active, selected: active \}\}/.test(perf));
check('M10: StakeEditModal buttons labelled, 12pt slop, tap outside closes', /accessibilityLabel="Reset to \$100"/.test(perf) && /accessibilityLabel="Save stake"/.test(perf) && /<View style=\{styles\.stakeModalBackdrop\}>\s*\{\/\*[\s\S]*?\*\/\}\s*<Pressable\s*style=\{StyleSheet\.absoluteFill\}\s*onPress=\{onClose\}/.test(perf));
check('M10: tracked rows offer Untrack / Edit stake as accessibilityActions (Undo toast is PR 5)', /\{ name: 'untrack', label: 'Untrack' \}/.test(perf) && /actionName === 'untrack'\) onRowLongPress\(row\)/.test(perf));
const tip = read('src/components/InfoTooltip.tsx');
check('M18: InfoTooltip icon slop 12 (20 + 24 = 44)', /hitSlop=\{12\}\s*accessibilityRole="button"/.test(tip));
const onboarding = read('src/components/OnboardingModal.tsx');
check('M19: Skip and Next have roles; dots read "Page N of 4"', /accessibilityLabel="Skip intro"/.test(onboarding) && /accessibilityLabel=\{pageLabel\(step, SLIDES\.length\)\}/.test(onboarding) && /accessibilityLabel=\{last \? 'Get started'/.test(onboarding));
const manual = read('src/components/ManualBetModal.tsx');
check('M25: disabled "Add bet" says why (accessibilityHint = addBetHint) and exposes disabled',
  /const addHint = valid \? undefined : addBetHint\(\{ bet: desc, stake \}\);/.test(manual) && /accessibilityHint=\{addHint\}/.test(manual) && /accessibilityState=\{\{ disabled: !valid \}\}/.test(manual) && /disabled=\{!valid\}/.test(manual));
check('M25: all four inputs are labelled', ['"Bet"', '"Sportsbook, optional"', '"Stake in dollars"', '"Odds, American"'].every((l) => manual.includes(`accessibilityLabel=${l}`)));
const settings = read('src/screens/SettingsScreen.tsx');
check('M9: helpline row reaches 44 (slop below the divider)', /hitSlop=\{\{ top: 0, bottom: 12, left: 0, right: 0 \}\}/.test(settings));
check('M26: Settings Sign out is minHeight 44', /signOutBtn: \{[^}]*minHeight: 44/.test(settings));
check('Sheets: the tap-outside backdrop is a sibling, never the sheet’s parent',
  ['AddLineSheet', 'HitModeSheet', 'PlayerNewsSheet', 'StatePickerSheet', 'ParlayDkHandoff', 'SportsbookPickerSheet', 'InfoTooltip', 'filters/FilterSheet'].every((n) => {
    const s = read(`src/components/${n}.tsx`);
    return /<View style=\{styles\.backdrop\}>/.test(s) && !/<Pressable\s+style=\{styles\.backdrop\}/.test(s);
  }));

console.log('\nlib/a11y.ts (behaviour)');
check('lib/a11y.ts has no imports (pure; loads under plain node)', !/^import /m.test(a11ySrc));

async function behaviour() {
  const a = await import(pathToFileURL(join(ROOT, 'src/lib/a11y.ts')).href);
  check('slopFor(23) → 11/11 (45pt)', JSON.stringify(a.slopFor(23)) === JSON.stringify({ top: 11, bottom: 11, left: 0, right: 0 }), a.slopFor(23));
  check('slopFor(20, 20) → 12 all round', JSON.stringify(a.slopFor(20, 20)) === JSON.stringify({ top: 12, bottom: 12, left: 12, right: 12 }));
  check('slopFor(50) → no slop', JSON.stringify(a.slopFor(50)) === JSON.stringify({ top: 0, bottom: 0, left: 0, right: 0 }));
  check('targetSize(23, 60, ROW_SLOP_PAD frame) ≥ 44', a.targetSize(23, 60, { top: a.ROW_SLOP_PAD, bottom: a.ROW_SLOP_PAD }).height >= a.MIN_TAP);
  check('targetSize(20, 20, 12) = 44 × 44', JSON.stringify(a.targetSize(20, 20, 12)) === JSON.stringify({ height: 44, width: 44 }));
  check('gameStatusSpeech live → "Live, bottom 9th, 2 outs, 3 to 2"',
    a.gameStatusSpeech({ kind: 'live', awayScore: 3, homeScore: 2, inning: 9, inningHalf: 'bottom', outs: 2 }) === 'Live, bottom 9th, 2 outs, 3 to 2');
  check('gameStatusSpeech live, 1 out, top 11th', a.gameStatusSpeech({ kind: 'live', awayScore: 0, homeScore: 0, inning: 11, inningHalf: 'top', outs: 1 }) === 'Live, top 11th, 1 out, 0 to 0');
  check('gameStatusSpeech live, no feed detail → "Live"', a.gameStatusSpeech({ kind: 'live', awayScore: null, homeScore: null, inning: null, inningHalf: null, outs: null }) === 'Live');
  check('gameStatusSpeech final → "Final, 5 to 3"', a.gameStatusSpeech({ kind: 'final', awayScore: 5, homeScore: 3 }) === 'Final, 5 to 3');
  check('gameStatusSpeech pre with day → "Starts Sat 6/14, 10:00 PM ET"', a.gameStatusSpeech({ kind: 'pre', timeLabel: '10:00 PM ET' }, 'Sat 6/14') === 'Starts Sat 6/14, 10:00 PM ET');
  check('gameStatusSpeech pre, no time / ended → null', a.gameStatusSpeech({ kind: 'pre', timeLabel: '' }) === null && a.gameStatusSpeech({ kind: 'ended' }) === null);
  check('unitsSpeech("1.2u → 1.0u") → "1.2 units to win 1.0 units"', a.unitsSpeech('1.2u → 1.0u') === '1.2 units to win 1.0 units', a.unitsSpeech('1.2u → 1.0u'));
  check('sharpScoreSpeech(78, "high")', a.sharpScoreSpeech(78, 'high') === 'Sharp score 78 of 100, high');
  check('pageLabel(1, 4) → "Page 2 of 4"', a.pageLabel(1, 4) === 'Page 2 of 4');
  check('spokenDate("2026-09-28") → "September 28, 2026"', a.spokenDate('2026-09-28') === 'September 28, 2026');
  check('addBetHint names only what is missing (M25)',
    a.addBetHint({ bet: '', stake: '' }) === 'Enter the bet and a stake above zero to add this bet.' &&
      a.addBetHint({ bet: 'Yankees ML', stake: '0' }) === 'Enter a stake above zero to add this bet.' &&
      a.addBetHint({ bet: ' ', stake: '50' }) === 'Enter the bet to add this bet.' &&
      a.addBetHint({ bet: 'Yankees ML', stake: '50' }) === undefined);
  check('joinLabel drops empties', a.joinLabel(['MLB', null, '', false, '2 signals']) === 'MLB, 2 signals');
  check('unknownCountSpeech("Sep 28 · — bets · — scored") → "… bets count not available, …"',
    a.unknownCountSpeech('Sep 28 · — bets · — scored') === 'Sep 28, bets count not available, scored count not available', a.unknownCountSpeech('Sep 28 · — bets · — scored'));
  check('unknownCountSpeech leaves known counts, drops "·"', a.unknownCountSpeech('Sep 28 · 3 bets · 12 scored') === 'Sep 28, 3 bets, 12 scored' && a.unknownCountSpeech('— in play') === 'in play count not available');
}

behaviour()
  .catch((e) => check('lib/a11y.ts behaviour ran', false, String(e)))
  .finally(() => {
    console.log(failures ? `\n${failures} FAILED (${passes} passed)` : `\nALL PASS (${passes} checks)`);
    process.exit(failures ? 1 : 0);
  });
