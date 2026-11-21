/**
 * No name is read before the line that declares it (2026-11-21).
 *
 * Bet all crashed on every open, for every member, on OTA 01a1fef3: one line
 * of BetAllSheet read `selected.has(...)` five lines ABOVE
 * `const [selected] = useState(...)`. tsc does not flag it (the read sits
 * inside a `.filter(...)` callback, which TypeScript assumes may run later),
 * and the shipped bundle turns `const` into `var`, so the read sees
 * `undefined`: "TypeError: Cannot read property 'has' of undefined",
 * five `render` rows in app_errors at 16:58 UTC.
 *
 * The rule: inside any function body under src/, a statement may not refer to
 * a `const`/`let` that a LATER statement of the same body declares — unless
 * the reference sits inside a function that is only defined there (an arrow
 * assigned to a name, or handed to a React hook such as useEffect /
 * useCallback / useMemo), which runs after the declaration has happened.
 * A callback passed to anything else (`.filter`, `.map`, `.some`, …) runs on
 * the spot, so it counts as a read.
 *
 * Run with:
 *
 *   npx tsx scripts/verify_no_use_before_declare.ts
 */
import { readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import ts from 'typescript';

const ROOT = join(__dirname, '..');
const SRC = join(ROOT, 'src');

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(name) && !name.endsWith('.d.ts')) out.push(p);
  }
  return out;
}

// Hooks whose callback runs after render, never during the line that calls them.
const DEFERRED_CALLEES = new Set([
  'useEffect',
  'useLayoutEffect',
  'useCallback',
  'useMemo',
  'useFocusEffect',
  'setTimeout',
  'setInterval',
  'requestAnimationFrame',
  'addEventListener',
  'then',
  'catch',
  'finally',
]);

function calleeName(call: ts.CallExpression): string | null {
  const e = call.expression;
  if (ts.isIdentifier(e)) return e.text;
  if (ts.isPropertyAccessExpression(e)) return e.name.text;
  return null;
}

/** True when `node` sits inside a function (below `stmt`) that does not run on the spot. */
function insideDeferredFunction(node: ts.Node, stmt: ts.Node): boolean {
  let n: ts.Node | undefined = node.parent;
  while (n && n !== stmt) {
    if (ts.isFunctionLike(n)) {
      const p = n.parent;
      // `const f = () => …`, `function f() {…}`, an object method, a JSX prop
      // handler (onPress={() => …}): defined here, called later.
      if (!p || !ts.isCallExpression(p) || p.expression === n) return true;
      // Handed to a call: deferred only for the hooks / timers above.
      const name = calleeName(p);
      if (name && DEFERRED_CALLEES.has(name)) return true;
    }
    n = n.parent;
  }
  return false;
}

interface Finding {
  file: string;
  line: number;
  name: string;
  declaredLine: number;
}

export function findUseBeforeDeclare(files: string[]): Finding[] {
  const program = ts.createProgram(files, {
    noResolve: true,
    noLib: true,
    allowJs: false,
    jsx: ts.JsxEmit.ReactJSX,
    target: ts.ScriptTarget.ES2022,
  });
  const checker = program.getTypeChecker();
  const findings: Finding[] = [];

  for (const sf of program.getSourceFiles()) {
    if (!files.includes(sf.fileName)) continue;
    const visitBody = (body: ts.Block) => {
      const stmts = body.statements;
      // Every const/let a statement of this body declares, by symbol.
      const declaredAt = new Map<ts.Symbol, number>();
      stmts.forEach((s, idx) => {
        if (!ts.isVariableStatement(s)) return;
        if (!(s.declarationList.flags & (ts.NodeFlags.Const | ts.NodeFlags.Let))) return;
        const collect = (name: ts.BindingName) => {
          if (ts.isIdentifier(name)) {
            const sym = checker.getSymbolAtLocation(name);
            if (sym) declaredAt.set(sym, idx);
          } else {
            for (const el of name.elements) if (!ts.isOmittedExpression(el)) collect(el.name);
          }
        };
        for (const d of s.declarationList.declarations) collect(d.name);
      });
      if (declaredAt.size === 0) return;
      stmts.forEach((s, idx) => {
        const scan = (n: ts.Node) => {
          if (ts.isIdentifier(n)) {
            const sym = checker.getSymbolAtLocation(n);
            const at = sym ? declaredAt.get(sym) : undefined;
            if (at !== undefined && at > idx && !insideDeferredFunction(n, s)) {
              const decl = sym!.declarations?.[0];
              findings.push({
                file: relative(ROOT, sf.fileName),
                line: sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1,
                name: n.text,
                declaredLine: decl ? sf.getLineAndCharacterOfPosition(decl.getStart(sf)).line + 1 : -1,
              });
            }
          }
          ts.forEachChild(n, scan);
        };
        scan(s);
      });
    };
    const visit = (n: ts.Node) => {
      if (ts.isBlock(n) && n.parent && ts.isFunctionLike(n.parent)) visitBody(n);
      ts.forEachChild(n, visit);
    };
    visit(sf);
  }
  return findings;
}

// The shape that shipped, kept as a fixture so the rule is seen to catch it.
const FIXTURE = `
export function Sheet({ picks }: { picks: { key: string }[] }) {
  const ticked = picks.filter((p) => selected.has(p.key)).length;
  const [selected] = useState(() => new Set(picks.map((p) => p.key)));
  const later = () => selected.size;
  useEffect(() => { void selected; }, []);
  return ticked + later();
}
`;

function check(cond: boolean, msg: string) {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    process.exitCode = 1;
  } else console.log(`ok: ${msg}`);
}

const fixturePath = join(ROOT, 'scripts', '__use_before_declare_fixture.tsx');
{
  // Run the rule on the fixture through an in-memory file.
  const fs = require('node:fs') as typeof import('node:fs');
  fs.writeFileSync(fixturePath, FIXTURE, 'utf-8');
  try {
    const f = findUseBeforeDeclare([fixturePath]);
    check(
      f.length === 1 && f[0]!.name === 'selected' && f[0]!.line === 3,
      'the shipped BetAllSheet shape (read inside .filter above its useState) is caught, and only it',
    );
  } finally {
    fs.unlinkSync(fixturePath);
  }
}

const findings = findUseBeforeDeclare(walk(SRC));
for (const f of findings) {
  console.error(`  ${f.file}:${f.line} reads \`${f.name}\` before it is declared on line ${f.declaredLine}`);
}
check(findings.length === 0, `no name under src/ is read before its declaration (${findings.length} found)`);
