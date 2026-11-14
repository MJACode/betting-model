/**
 * Tracking several picks at once keeps every one of them. Run with:
 *
 *   npx tsx scripts/verify_tracked_batch.ts
 *
 * Matt, 2026-11-14: Bet all's "Placed · track" on three picks left one
 * tracked on the phone, while tracked_bets held all three (21:16:23 UTC).
 * Each add wrote [...render's ids, id], so the last write won. This runs the
 * real store (src/hooks/useTrackedBets.ts) on an in-memory AsyncStorage.
 */
import { registerHooks } from 'node:module';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const rn = new URL('./shims/react-native.mjs', import.meta.url).href;
const storage = new URL('./shims/async-storage.mjs', import.meta.url).href;
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'react-native' || specifier.startsWith('react-native/')) return { url: rn, shortCircuit: true };
    if (specifier === '@react-native-async-storage/async-storage') return { url: storage, shortCircuit: true };
    return nextResolve(specifier, context);
  },
});
process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://example.invalid';
process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
// The server write is fire-and-forget and not under test here.
globalThis.fetch = (async () => new Response('[]', { status: 201 })) as typeof fetch;
console.warn = () => {};

async function main(): Promise<void> {
  const store = await import('../src/hooks/useTrackedBets');
  const shared = (globalThis as unknown as { __asyncStorageShim: Map<string, string> }).__asyncStorageShim;

  type P = Parameters<typeof store.trackPicks>[0][number];
  const pick = (id: number, live = false) =>
    ({ pick_id: id, is_live: live, game_id: `g${id}`, model_id: 'm', pick_side: 'home', pick_label: `P${id}`,
       dk_odds: -110, scored_line: -1.5, game_date: '2026-11-14' }) as unknown as P;

  const saved = async () => JSON.parse(shared.get('trackedBets.pickIds.v1') ?? '[]') as number[];

  await store.trackPicks([pick(1)]);
  await store.trackPicks([pick(4486048), pick(4486005), pick(4486000)]);
  check('three picks tracked in one tap are all kept', JSON.stringify(await saved()) === '[1,4486048,4486005,4486000]',
    JSON.stringify(await saved()));

  // Three separate calls in the same tick, as a loop of track() did.
  await Promise.all([store.trackPicks([pick(7)]), store.trackPicks([pick(8)]), store.trackPicks([pick(9)])]);
  const all = await saved();
  check('three adds in one tick are all kept', [7, 8, 9].every((id) => all.includes(id)), JSON.stringify(all));

  await store.trackPicks([pick(8)]);
  check('tracking again adds nothing', (await saved()).filter((id) => id === 8).length === 1);

  await store.untrackPicks([pick(4486005), pick(8)]);
  const after = await saved();
  check('untracking two keeps the rest', !after.includes(4486005) && !after.includes(8) && after.includes(4486000) && after.includes(9),
    JSON.stringify(after));

}

void main().then(() => {
  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
});
