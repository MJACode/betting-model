/**
 * ux_scan — the deterministic half of the front-end UX review.
 *
 * Runs with plain Node (>= 22.18 strips types natively; no deps, no tsx). It is
 * .mts rather than .ts so Node loads it as ESM without a "type" field in the
 * app's package.json — a package.json change makes the OTA workflow refuse to
 * publish, and this script is not worth a native rebuild.
 *
 *   node mobile/scripts/ux_scan.mts --changed        # files changed vs origin/master + working tree
 *   node mobile/scripts/ux_scan.mts --all            # every file under mobile/src
 *   node mobile/scripts/ux_scan.mts <file> [...]     # explicit files
 *   add --strict to exit 1 when anything is found (advisory by default)
 *
 * WHY THIS IS A SCRIPT AND NOT PART OF THE AGENT. The same reason Sentinel reads
 * `pipeline_report` instead of writing its own SQL each morning: a check that is
 * re-derived every run produces a different answer every run, and the one thing
 * a review needs is that two reviews of the same diff find the same things. The
 * agent (`.claude/agents/frontend-ux-designer.md`) supplies judgement on top of
 * this output; it does not replace it.
 *
 * Every rule here maps to a line in mobile/docs/UX_REVIEW.md. Keep them in sync.
 */

import { execSync } from 'node:child_process';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';

type Severity = 'blocker' | 'should-fix';

interface Finding {
  file: string;
  line: number;
  rule: string;
  severity: Severity;
  message: string;
}

const REPO = resolve(import.meta.dirname, '..', '..');
const SRC = join(REPO, 'mobile', 'src');

// ---------------------------------------------------------------- rules

const THEME_FILE = join('mobile', 'src', 'lib', 'theme.ts');

/** Hex literals belong in theme.ts. Alpha-only backdrops are tolerated. */
function hexColors(file: string, lines: string[], out: Finding[]): void {
  if (file.endsWith(THEME_FILE)) return;
  const re = /#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?\b/g;
  lines.forEach((text, i) => {
    if (/^\s*(\/\/|\*)/.test(text)) return; // comments
    for (const m of text.matchAll(re)) {
      const hex = m[0].toUpperCase();
      if (hex.startsWith('#000000') && hex.length === 9) continue; // modal backdrop alpha
      out.push({
        file, line: i + 1, rule: 'hex-color', severity: 'should-fix',
        message: `hard-coded colour ${m[0]} — use a token from @/lib/theme (UX_REVIEW §2)`,
      });
    }
  });
}

/** fontSize literals are a type scale nobody agreed to. */
function fontSizeLiterals(file: string, lines: string[], out: Finding[]): void {
  if (file.endsWith(THEME_FILE)) return;
  lines.forEach((text, i) => {
    const m = /\bfontSize:\s*(\d+)\b/.exec(text);
    if (m) {
      out.push({
        file, line: i + 1, rule: 'font-size-literal', severity: 'should-fix',
        message: `fontSize: ${m[1]} — use font.size.* from @/lib/theme (UX_REVIEW §2)`,
      });
    }
  });
}

/**
 * A pressable with neither accessibilityRole nor accessibilityLabel is silent
 * for VoiceOver. Walks the opening tag across lines, tracking JSX braces so a
 * `>` inside an expression does not end the tag early.
 */
function pressableA11y(file: string, source: string, out: Finding[]): void {
  const re = /<(Pressable|TouchableOpacity|TouchableHighlight|TouchableWithoutFeedback)\b/g;
  for (const m of source.matchAll(re)) {
    const start = m.index ?? 0;
    let depth = 0;
    let end = -1;
    for (let j = start; j < source.length; j++) {
      const ch = source[j];
      if (ch === '{') depth++;
      else if (ch === '}') depth--;
      else if (ch === '>' && depth === 0) { end = j; break; }
    }
    if (end < 0) continue;
    const tag = source.slice(start, end + 1);
    // A spread may carry the props from a parent — do not guess, skip.
    if (/\{\.\.\./.test(tag)) continue;
    if (/accessibilityRole|accessibilityLabel|accessible=\{false\}|role=/.test(tag)) continue;
    const line = source.slice(0, start).split('\n').length;
    // Icon-only: VoiceOver has nothing to read at all. With a <Text> child the
    // label is read but the role is missing — still wrong, less severe.
    const close = source.indexOf(`</${m[1]}>`, end);
    const body = close < 0 ? '' : source.slice(end, close);
    const iconOnly = !/<Text\b/.test(body);
    out.push({
      file, line, rule: 'a11y-pressable', severity: iconOnly ? 'blocker' : 'should-fix',
      message: iconOnly
        ? `<${m[1]}> is icon-only with no accessibilityLabel — silent for VoiceOver (UX_REVIEW §5)`
        : `<${m[1]}> has no accessibilityRole or accessibilityLabel (UX_REVIEW §5)`,
    });
  }
}

/** UTC "today" is tomorrow after 8pm ET. CLAUDE.md §7. */
function utcToday(file: string, lines: string[], out: Finding[]): void {
  if (file.endsWith(join('lib', 'format.ts'))) return;
  lines.forEach((text, i) => {
    if (/toISOString\(\)\s*\.\s*(slice|substring|substr)\(\s*0\s*,\s*10\s*\)/.test(text)) {
      out.push({
        file, line: i + 1, rule: 'utc-today', severity: 'blocker',
        message: 'UTC date-only — use todayET() / the *ET formatters (UX_REVIEW §0)',
      });
    }
  });
}

/** The platform is live. No user-facing copy may say otherwise. */
function paperTradingCopy(file: string, lines: string[], out: Finding[]): void {
  lines.forEach((text, i) => {
    if (/^\s*(\/\/|\*|\/\*)/.test(text)) return; // comments may explain history
    if (/['"`][^'"`]*\b(paper[\s-]?trad|simulated|test mode)[^'"`]*['"`]/i.test(text)) {
      out.push({
        file, line: i + 1, rule: 'paper-trading-copy', severity: 'blocker',
        message: 'user-facing copy describes the platform as paper/simulated (UX_REVIEW §0)',
      });
    }
  });
}

/** Access is decided in one place, and it is not the subscriptions table. */
function entitlementGate(file: string, source: string, lines: string[], out: Finding[]): void {
  if (/hooks[\\/]useEntitlement\.ts$/.test(file)) return;
  if (!/useSubscription\(/.test(source)) return;
  lines.forEach((text, i) => {
    if (/useSubscription\(\)\s*\.\s*entitled|const\s*\{[^}]*\bentitled\b[^}]*\}\s*=\s*useSubscription\(/.test(text)) {
      out.push({
        file, line: i + 1, rule: 'entitlement-gate', severity: 'blocker',
        message: 'gates on useSubscription().entitled — use useEntitlement() (UX_REVIEW §0)',
      });
    }
  });
}

/** Dynamic Type must not be switched off. */
function fontScaling(file: string, lines: string[], out: Finding[]): void {
  lines.forEach((text, i) => {
    if (/allowFontScaling=\{false\}/.test(text)) {
      out.push({
        file, line: i + 1, rule: 'font-scaling-off', severity: 'should-fix',
        message: 'allowFontScaling={false} — cap with maxFontSizeMultiplier instead (UX_REVIEW §5)',
      });
    }
  });
}

/** The RN SafeAreaView ignores the home indicator; the context one does not. */
function safeAreaImport(file: string, lines: string[], out: Finding[]): void {
  lines.forEach((text, i) => {
    if (/import\s*\{[^}]*\bSafeAreaView\b[^}]*\}\s*from\s*['"]react-native['"]/.test(text)) {
      out.push({
        file, line: i + 1, rule: 'safe-area-import', severity: 'should-fix',
        message: "SafeAreaView from 'react-native' — import it from react-native-safe-area-context (UX_REVIEW §6)",
      });
    }
  });
}

// ---------------------------------------------------------------- driver

function scanFile(abs: string): Finding[] {
  const file = relative(REPO, abs).split(sep).join('/');
  const source = readFileSync(abs, 'utf8');
  const lines = source.split('\n');
  const out: Finding[] = [];
  hexColors(file, lines, out);
  fontSizeLiterals(file, lines, out);
  if (file.endsWith('.tsx')) pressableA11y(file, source, out);
  utcToday(file, lines, out);
  paperTradingCopy(file, lines, out);
  entitlementGate(file, source, lines, out);
  fontScaling(file, lines, out);
  safeAreaImport(file, lines, out);
  return out.sort((a, b) => a.line - b.line);
}

function walk(dir: string, acc: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.tsx?$/.test(name)) acc.push(p);
  }
  return acc;
}

function changedFiles(): string[] {
  const run = (cmd: string): string[] => {
    try {
      return execSync(cmd, { cwd: REPO, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
        .split('\n').map((s) => s.trim()).filter(Boolean);
    } catch {
      return [];
    }
  };
  const base = run('git merge-base origin/master HEAD')[0] ?? 'origin/master';
  const set = new Set<string>([
    ...run(`git diff --name-only ${base} -- mobile/src`),
    ...run('git diff --name-only -- mobile/src'),
    ...run('git ls-files --others --exclude-standard -- mobile/src'),
  ]);
  return [...set].filter((f) => /\.tsx?$/.test(f)).map((f) => join(REPO, f));
}

function main(): void {
  const args = process.argv.slice(2);
  const strict = args.includes('--strict');
  const mode = args.find((a) => a === '--all' || a === '--changed');
  const explicit = args.filter((a) => !a.startsWith('--')).map((a) => resolve(a));

  let files: string[];
  if (mode === '--all') files = walk(SRC);
  else if (mode === '--changed' || explicit.length === 0) files = changedFiles();
  else files = explicit;
  files = files.filter((f) => {
    try { return statSync(f).isFile(); } catch { return false; }
  });

  if (files.length === 0) {
    console.log('ux_scan: no front-end files in scope (nothing under mobile/src changed).');
    return;
  }

  const findings = files.flatMap(scanFile);
  const byFile = new Map<string, Finding[]>();
  for (const f of findings) byFile.set(f.file, [...(byFile.get(f.file) ?? []), f]);

  console.log(`ux_scan: ${files.length} file(s), ${findings.length} finding(s)\n`);
  for (const [file, list] of [...byFile.entries()].sort()) {
    console.log(file);
    for (const f of list) {
      console.log(`  ${String(f.line).padStart(4)}  ${f.severity === 'blocker' ? 'BLOCKER ' : 'should  '} ${f.rule.padEnd(20)} ${f.message}`);
    }
    console.log();
  }

  const counts = new Map<string, number>();
  for (const f of findings) counts.set(f.rule, (counts.get(f.rule) ?? 0) + 1);
  if (findings.length) {
    console.log('by rule:');
    for (const [rule, n] of [...counts.entries()].sort((a, b) => b[1] - a[1])) {
      console.log(`  ${rule.padEnd(20)} ${n}`);
    }
  }
  const blockers = findings.filter((f) => f.severity === 'blocker').length;
  console.log(`\nblockers: ${blockers}   should-fix: ${findings.length - blockers}`);
  if (strict && findings.length) process.exit(1);
}

main();
