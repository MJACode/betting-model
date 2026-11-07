/**
 * The server's book lists, read from config.py itself — not retyped here.
 *
 * The app's lists in src/lib/markets.ts drifted from config for seven weeks:
 * the server went from fourteen fetched books to ten on 2026-09-20 and the app
 * kept all fourteen, while two verify scripts pinned the app's own length
 * (`=== 13`) and so could only ever agree with the app. A count typed into a
 * test is a second copy of the list; this reads the first one.
 *
 * It runs Python because config.py is the only place the lists exist: the
 * fetch list and the exclude list are env-overridable Python expressions with
 * comments inside them, which no regex reads reliably.
 *
 * The four overrides are REMOVED from the child's environment, so this compares
 * against config's own defaults. Those defaults are what production runs:
 * neither Railway service (worker, pollers) sets any of the four (Railway
 * variable listing, 2026-11-06). If the repo's .env sets one, the snippet
 * reports it and the caller fails rather than comparing against a local
 * override.
 *
 * Throws when Python or config.py cannot be read. A verify script that
 * skipped the comparison and passed would be the same blind guard again.
 */
import { execFileSync } from 'node:child_process';
import * as path from 'node:path';

export interface ConfigBooks {
  /** config.LINE_SHOP_BOOKMAKERS — every book the server fetches, in order. */
  fetched: string[];
  /** config.BEST_LINE_BOOKMAKERS — the books a pick may be decided at, in order. */
  decided: string[];
  /** config.BEST_LINE_EXCLUDE_BOOKMAKERS — reference-only books. */
  excluded: string[];
  /** Override variables still set after config loaded (from .env). */
  overridden: string[];
}

const OVERRIDES = [
  'LINE_SHOP_BOOKMAKERS',
  'BEST_LINE_BOOKMAKERS',
  'BEST_LINE_EXCLUDE_BOOKMAKERS',
  'BETTABLE_BOOKS',
];

const SNIPPET = [
  'import json, os, config',
  'print(json.dumps({',
  '  "fetched": config.LINE_SHOP_BOOKMAKERS,',
  '  "decided": config.BEST_LINE_BOOKMAKERS,',
  '  "excluded": config.BEST_LINE_EXCLUDE_BOOKMAKERS,',
  `  "overridden": [k for k in ${JSON.stringify(OVERRIDES)} if k in os.environ],`,
  '}))',
].join('\n');

export function readConfigBooks(): ConfigBooks {
  const repoRoot = path.resolve(__dirname, '..', '..');
  const env: NodeJS.ProcessEnv = { ...process.env, PYTHONIOENCODING: 'utf-8' };
  for (const k of OVERRIDES) delete env[k];
  const candidates = [process.env.PYTHON, 'python', 'python3', 'py'].filter(
    (c): c is string => !!c,
  );
  const errors: string[] = [];
  for (const exe of candidates) {
    try {
      const out = execFileSync(exe, ['-c', SNIPPET], {
        cwd: repoRoot,
        env,
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      // config.py may print on import; the JSON is the last line.
      const last = out.trim().split(/\r?\n/).pop() ?? '';
      return JSON.parse(last) as ConfigBooks;
    } catch (err) {
      errors.push(`${exe}: ${(err as Error).message.split('\n')[0]}`);
    }
  }
  throw new Error(`could not read config.py's book lists (${errors.join('; ')})`);
}

/** Same books in the same order. */
export function sameList(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

/** Same books, any order. */
export function sameSet(a: readonly string[], b: readonly string[]): boolean {
  const sa = new Set(a);
  const sb = new Set(b);
  return sa.size === sb.size && [...sa].every((x) => sb.has(x));
}
