/**
 * Signed unit results round SYMMETRICALLY — half away from zero on both sides.
 *
 * Run with:  npx tsx scripts/verify_signed_units.ts
 *
 * Reviewer, #837 post-merge: formatSignedUnits (lib/format.ts) and
 * DailyResultsModal's unitsColor both used Math.round(u * 10) / 10, which
 * rounds halves UP — so −0.05u printed "0.0u" (grey) while +0.05u printed
 * "+0.1u" (green), and −0.15 became −0.1 while +0.15 became +0.2. A loss and a
 * win of the same size must read as mirror images.
 *
 * Both now use Math.sign(u) * Math.round(Math.abs(u) * 10) / 10 (the same
 * expression draft #833 uses). unitsColor lives in a React Native component,
 * so its half is pinned from the source: it must round exactly as the
 * formatter does, or a "−0.1u" day could be painted as a push.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { formatSignedUnits } from '../src/lib/format';

const ROOT = join(import.meta.dirname, '..');
let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const M = '\u2212'; // the formatter's minus sign
const cases: [number, string][] = [
  [-0.04, '0.0u'],          // rounds to zero: no sign, and never "−0.0u"
  [0.04, '0.0u'],
  [0.05, '+0.1u'],
  [-0.05, `${M}0.1u`],      // was "0.0u" under half-up
  [0.15, '+0.2u'],
  [-0.15, `${M}0.2u`],      // was "−0.1u" under half-up
  [1.45, '+1.5u'],
  [-1.45, `${M}1.5u`],
  [0, '0.0u'],
  [-0, '0.0u'],
  [2.36, '+2.4u'],
  [-2.36, `${M}2.4u`],
];
for (const [u, want] of cases) {
  const got = formatSignedUnits(u);
  check(`formatSignedUnits(${Object.is(u, -0) ? '-0' : u}) = ${want}`, got === want, `got ${got}`);
}
for (const u of [0.05, 0.15, 0.25, 1.45, 3.35]) {
  const pos = formatSignedUnits(u);
  const neg = formatSignedUnits(-u);
  check(`±${u} are mirror images`, neg === pos.replace('+', M), `${pos} / ${neg}`);
}

const fmt = readFileSync(join(ROOT, 'src/lib/format.ts'), 'utf-8');
const modal = readFileSync(join(ROOT, 'src/components/DailyResultsModal.tsx'), 'utf-8');
// Optional parentheses around the rounded magnitude: draft #833 writes
// Math.sign(u) * (Math.round(Math.abs(u) * 10) / 10), the same value.
const HALF = String.raw`Math\.round\(Math\.abs\(\1\)\s*\*\s*10\)\s*\/\s*10`;
const SYM = new RegExp(String.raw`Math\.sign\((\w+)\)\s*\*\s*(?:${HALF}|\(\s*${HALF}\s*\))`);
const fmtBody = fmt.slice(fmt.indexOf('export function formatSignedUnits'));
const colorBody = modal.slice(modal.indexOf('function unitsColor'));
check('formatSignedUnits uses the symmetric expression', SYM.test(fmtBody.slice(0, 600)));
check('unitsColor uses the same symmetric expression', SYM.test(colorBody.slice(0, 400)));
check('unitsColor no longer rounds half-up',
  !/Math\.round\(units \* 10\)/.test(colorBody.slice(0, 400)));

if (failures) {
  console.error(`\n${failures} FAILED`);
  process.exit(1);
}
console.log('\nall signed-units checks passed');
