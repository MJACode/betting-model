/**
 * AI Assistant screens: which state each account sees, and the words.
 *
 *   node --experimental-strip-types scripts/verify_ai_assistant.ts
 */

import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
let failures = 0;
function check(name: string, ok: boolean, detail = ''): void {
  if (ok) console.log(`[PASS] ${name}`);
  else {
    failures += 1;
    console.log(`[FAIL] ${name} ${detail}`);
  }
}
function eq(name: string, actual: unknown, expected: unknown): void {
  check(name, actual === expected, `got ${JSON.stringify(actual)}`);
}

const ai = await import(pathToFileURL(join(ROOT, 'src/lib/aiAssistant.ts')).href);

const base = {
  entitlement: 'paid', eligible: true, can_view: true, preview_only: false, unlimited: false,
  trial_converts_at: null, terms_accepted: true, suspended: false, connected_client: null,
  connected_client_name: null, connected_client_host: null, connected_at: null, last_used_at: null,
  questions_per_day: 10, questions_used: 0, questions_left: 10, resets_at: '2026-11-22T05:00:00+00:00',
};
const s = (o: Record<string, unknown>) => ({ ...base, ...o });

// Who sees what (Matt, 2026-11-20/21).
eq('signed out sees nothing', ai.aiAssistantMode(null), 'hidden');
eq('no access sees nothing', ai.aiAssistantMode(s({ entitlement: 'none', eligible: false, can_view: false })), 'hidden');
eq('a trial sees the locked screen', ai.aiAssistantMode(s({ entitlement: 'trial', eligible: false, can_view: false })), 'trial');
eq('App Review previews', ai.aiAssistantMode(s({ entitlement: 'app_review', eligible: false, preview_only: true })), 'preview');
eq('paid, nothing connected, sets up', ai.aiAssistantMode(s({})), 'setup');
eq('comped sets up', ai.aiAssistantMode(s({ entitlement: 'comped' })), 'setup');
eq('connected', ai.aiAssistantMode(s({ connected_client: 'c1' })), 'connected');
eq('suspended beats connected', ai.aiAssistantMode(s({ connected_client: 'c1', suspended: true })), 'suspended');

// The app's name comes from the host it proved, not the name it chose.
eq('claude.ai is Claude', ai.connectedAppName(s({ connected_client_host: 'claude.ai', connected_client_name: 'x' })), 'Claude');
eq('chatgpt.com is ChatGPT', ai.connectedAppName(s({ connected_client_host: 'chatgpt.com' })), 'ChatGPT');
eq('grok.com is Grok', ai.connectedAppName(s({ connected_client_host: 'grok.com' })), 'Grok');
eq('a lookalike host is not Claude', ai.connectedAppName(s({ connected_client_host: 'evilclaude.ai', connected_client_name: 'Claude Pro' })), 'Claude Pro');
eq('nothing known', ai.connectedAppName(s({})), 'An app');

// Tile lines.
eq('trial tile names the day in ET', ai.aiTileSummary(s({ entitlement: 'trial', eligible: false, trial_converts_at: '2026-11-27T03:00:00Z' })), 'Unlocks Nov 26, when your trial ends');
eq('setup tile', ai.aiTileSummary(s({})), 'Ask Claude, ChatGPT or Grok about Stats');
eq('connected tile counts', ai.aiTileSummary(s({ connected_client: 'c', connected_client_host: 'claude.ai', questions_used: 3, questions_left: 7 })), 'Claude connected · 7 of 10 left today');
eq('founder tile', ai.aiTileSummary(s({ entitlement: 'founder', unlimited: true, questions_left: null, connected_client: 'c', connected_client_host: 'grok.com' })), 'Grok connected · no limit');
eq('badge on a trial', ai.aiTileBadge(s({ entitlement: 'trial', eligible: false })), 'Locked');
eq('badge until connected', ai.aiTileBadge(s({})), 'New');
eq('no badge once connected', ai.aiTileBadge(s({ connected_client: 'c' })), null);

// Meter and clocks.
const now = new Date('2026-11-21T22:19:00Z');
eq('left line', ai.questionsLeftLine(s({ questions_used: 3, questions_left: 7 }), now), '7 left · resets at midnight ET (in 6 h 41 min)');
eq('limit reached says so', ai.questionsLeftLine(s({ questions_used: 10, questions_left: 0 }), now), 'Daily limit reached · resets at midnight ET (in 6 h 41 min)');
eq('per day follows the server', ai.perDayLabel(s({ questions_per_day: 15 })), '15 questions a day');
eq('per day falls back to 10', ai.perDayLabel(null), '10 questions a day');
eq('founder line', ai.questionsLeftLine(s({ unlimited: true, questions_left: null }), now), 'Founder account: no daily limit');
check('meter clamps', JSON.stringify(ai.questionsMeter(s({ questions_used: 14, questions_left: 0 }))) === '{"used":10,"total":10,"left":0}');
eq('since line', ai.connectedSinceLine(s({ connected_at: '2026-11-20T15:00:00Z', last_used_at: '2026-11-21T22:15:00Z' }), now), 'Since Nov 20 · last used 4 min ago');
eq('never used', ai.connectedSinceLine(s({ connected_at: '2026-11-21T15:00:00Z' }), now), 'Since Nov 21 · not used yet');

// One-time moments.
eq('intro for a paying member', ai.shouldShowIntroCard(s({}), false), true);
eq('intro not after dismiss', ai.shouldShowIntroCard(s({}), true), false);
eq('intro never on a trial', ai.shouldShowIntroCard(s({ entitlement: 'trial', eligible: false }), false), false);
eq('intro never for the reviewer', ai.shouldShowIntroCard(s({ entitlement: 'app_review', eligible: false, preview_only: true }), false), false);
eq('intro not once connected', ai.shouldShowIntroCard(s({ connected_client: 'c' }), false), false);
eq('unlocked sheet after trial to paid', ai.shouldShowUnlockedSheet(s({}), 'trial', false), true);
eq('unlocked sheet once', ai.shouldShowUnlockedSheet(s({}), 'trial', true), false);
eq('no sheet without a seen trial', ai.shouldShowUnlockedSheet(s({}), null, false), false);
eq('no sheet while still a trial', ai.shouldShowUnlockedSheet(s({ entitlement: 'trial', eligible: false }), 'trial', false), false);

// Several assistants, one shared pool (Matt, 2026-11-22).
const two = s({
  connected_client: 'c2', questions_used: 4, questions_left: 6, max_assistants: 3,
  assistants: [
    { assistant: 'claude', client_name: 'Claude', client_host: 'claude.ai', connected_at: '2026-11-20T15:00:00Z', last_used_at: null, questions_today: 3 },
    { assistant: 'grok', client_name: 'Grok', client_host: 'grok.com', connected_at: '2026-11-22T13:27:00Z', last_used_at: null, questions_today: 1 },
  ],
});
eq('two assistants are connected', ai.aiAssistantMode(two), 'connected');
eq('names come from the assistant key', ai.connectedAssistants(two).map((a: { name: string }) => a.name).join(','), 'Claude,Grok');
eq('each row disconnects its own assistant', ai.connectedAssistants(two).map((a: { assistant: string }) => a.assistant).join(','), 'claude,grok');
eq('per-assistant count', ai.connectedAssistants(two)[0].questions_today, 3);
eq('tile names both, one shared count', ai.aiTileSummary(two), 'Claude and Grok connected · 6 of 10 left today');
eq('three names', ai.namesLine(['Claude', 'ChatGPT', 'Grok']), 'Claude, ChatGPT and Grok');
eq('an empty list is set up', ai.aiAssistantMode(s({ connected_client: null, assistants: [] })), 'setup');
eq('an unknown host is named by what it registered, never a brand',
  ai.connectedAssistants(s({ assistants: [{ assistant: 'evil.example', client_name: 'Claude', client_host: 'evil.example', connected_at: null, last_used_at: null, questions_today: 0 }] }))[0].name, 'Claude');
eq('a lookalike host is not the Claude key either',
  ai.connectedAssistants(s({ assistants: [{ assistant: 'evilclaude.ai', client_name: null, client_host: 'evilclaude.ai', connected_at: null, last_used_at: null, questions_today: 0 }] }))[0].name, 'An app');
eq('two unknown apps are told apart',
  ai.connectedAssistants(s({ assistants: [
    { assistant: 'a.example', client_name: null, client_host: 'a.example', connected_at: null, last_used_at: null, questions_today: 0 },
    { assistant: 'b.example', client_name: null, client_host: 'b.example', connected_at: null, last_used_at: null, questions_today: 0 },
  ] })).map((a: { name: string }) => a.name).join(','), 'An app (a.example),An app (b.example)');
const old = ai.connectedAssistants(s({ connected_client: 'c', connected_client_host: 'grok.com' }));
eq('an older server is one row', old.length, 1);
eq('an older server disconnects everything', old[0].assistant, null);
eq('max falls back to 3', ai.maxAssistants(s({})), 3);
eq('shared limit line', ai.sharedLimitLine(s({})), 'Up to 3 assistants at once, sharing 10 questions a day');
eq('shared limit line, founder', ai.sharedLimitLine(s({ unlimited: true })), 'Up to 3 assistants at once · founder account: no daily limit');

// Every guide names the address, and the address is the one the server serves.
eq('address', ai.MCP_SERVER_URL, 'https://signalbase-ai.com/mcp');
for (const g of ai.SETUP_GUIDES) {
  check(`${g.name} steps paste the address`, g.steps.some((x: string) => x.includes(ai.MCP_SERVER_ADDRESS)));
  check(`${g.name} has a note`, g.note.length > 0);
}
eq('three assistants', ai.SETUP_GUIDES.map((g: { id: string }) => g.id).join(','), 'claude,chatgpt,grok');

console.log(failures === 0 ? 'ALL PASS' : `${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
