/**
 * AI Assistant (the Stats connector at signalbase-ai.com/mcp): what the app
 * shows, decided from one read, `public.mcp_my_status()`.
 *
 * Matt, 2026-11-20/21: paying and comped members connect; founders are
 * unlimited; a free trial sees the screen and the date it unlocks; the App
 * Review account sees the screens but cannot connect. 10 questions a day,
 * reset at midnight ET. Since 2026-11-22 (Matt): up to three assistants at
 * once, sharing the 10, each disconnected on its own. The server enforces every
 * one of those (mcp_meter.begin_call); this file only chooses the words.
 *
 * Pure: no React, no network. The reads live in aiAssistantApi.ts.
 */

export const MCP_SERVER_ADDRESS = 'signalbase-ai.com/mcp';
export const MCP_SERVER_URL = `https://${MCP_SERVER_ADDRESS}`;

/** One connected assistant (mcp_multi_assistant_2026_11_22.sql). */
export interface McpAssistant {
  /** 'claude' | 'chatgpt' | 'grok', another app's host, or a client id. */
  assistant: string;
  client_name: string | null;
  client_host: string | null;
  connected_at: string | null;
  last_used_at: string | null;
  questions_today: number;
}

/**
 * The row `public.mcp_my_status()` returns (mcp_status_client_2026_11_21.sql,
 * `assistants` and `max_assistants` from mcp_multi_assistant_2026_11_22.sql;
 * a server without them reads as one connected app).
 */
export interface McpStatus {
  entitlement: 'founder' | 'paid' | 'comped' | 'app_review' | 'trial' | 'none';
  eligible: boolean;
  can_view: boolean;
  preview_only: boolean;
  unlimited: boolean;
  trial_converts_at: string | null;
  terms_accepted: boolean;
  suspended: boolean;
  connected_client: string | null;
  connected_client_name?: string | null;
  connected_client_host?: string | null;
  connected_at: string | null;
  last_used_at: string | null;
  assistants?: McpAssistant[];
  max_assistants?: number;
  questions_per_day: number;
  questions_used: number;
  questions_left: number | null;
  resets_at: string | null;
}

/**
 * Which screen the member gets.
 *  - hidden     no tile at all (no access, or not signed in)
 *  - trial      "Unlocks when your paid subscription starts"
 *  - preview    App Review: the setup screen, without the address to connect
 *  - suspended  access paused by support
 *  - setup      eligible, nothing connected yet
 *  - connected  eligible, at least one assistant connected
 */
export type AiAssistantMode = 'hidden' | 'trial' | 'preview' | 'suspended' | 'setup' | 'connected';

export function aiAssistantMode(status: McpStatus | null): AiAssistantMode {
  if (!status) return 'hidden';
  if (status.entitlement === 'trial') return 'trial';
  if (status.preview_only) return 'preview';
  if (!status.eligible) return 'hidden';
  if (status.suspended) return 'suspended';
  return connectedAssistants(status).length > 0 ? 'connected' : 'setup';
}

export type AssistantId = 'claude' | 'chatgpt' | 'grok';

/**
 * The assistant's name, from the HOST its sign-in returns to. Anyone can
 * register an OAuth client under any name, so a known host wins over the
 * registered name; an unknown host shows the registered name, never a brand
 * it did not prove.
 */
export function connectedAppName(status: McpStatus | null): string {
  return nameFor(status?.connected_client_host, status?.connected_client_name);
}

function nameFor(hostIn: string | null | undefined, registeredIn: string | null | undefined): string {
  const host = (hostIn ?? '').toLowerCase();
  const known: [string, string][] = [
    ['claude.ai', 'Claude'],
    ['claude.com', 'Claude'],
    ['chatgpt.com', 'ChatGPT'],
    ['openai.com', 'ChatGPT'],
    ['grok.com', 'Grok'],
    ['x.ai', 'Grok'],
  ];
  for (const [suffix, name] of known) {
    if (host === suffix || host.endsWith(`.${suffix}`)) return name;
  }
  const registered = (registeredIn ?? '').trim();
  return registered.length > 0 ? registered.slice(0, 40) : 'An app';
}

/** One row of the connected list. `assistant` null: an older server, disconnect all. */
export interface ConnectedAssistant {
  assistant: string | null;
  name: string;
  connected_at: string | null;
  last_used_at: string | null;
  questions_today: number | null;
}

const KNOWN_ASSISTANTS: Record<string, string> = { claude: 'Claude', chatgpt: 'ChatGPT', grok: 'Grok' };

/**
 * Every connected assistant, oldest connection first. The server groups a
 * member's sign-ins by the host they return to, so a reconnected Claude is
 * still one Claude. A server from before 2026-11-22 sends no list: its one
 * connected app becomes the only row.
 */
export function connectedAssistants(status: McpStatus | null): ConnectedAssistant[] {
  if (!status) return [];
  if (Array.isArray(status.assistants)) {
    return status.assistants.map((a) => ({
      assistant: a.assistant,
      name: KNOWN_ASSISTANTS[a.assistant] ?? nameFor(a.client_host, a.client_name),
      connected_at: a.connected_at,
      last_used_at: a.last_used_at,
      questions_today: typeof a.questions_today === 'number' ? a.questions_today : null,
    }));
  }
  if (!status.connected_client) return [];
  return [{
    assistant: null,
    name: connectedAppName(status),
    connected_at: status.connected_at,
    last_used_at: status.last_used_at,
    questions_today: null,
  }];
}

/** "Claude", "Claude and Grok", "Claude, ChatGPT and Grok". */
export function namesLine(names: string[]): string {
  if (names.length <= 1) return names[0] ?? '';
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/** How many assistants may be connected at once (3 unless the server says). */
export function maxAssistants(status: McpStatus | null): number {
  const n = status?.max_assistants;
  return typeof n === 'number' && n > 0 ? n : 3;
}

const ET = 'America/New_York';

/** "Nov 27": the trial's conversion day in ET, or null when unknown. */
export function shortDateET(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: ET });
}

/** "6 h 41 min", "12 min", "under a minute". */
export function untilLabel(iso: string | null | undefined, now: Date): string | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  const mins = Math.max(0, Math.floor((t - now.getTime()) / 60000));
  if (mins < 1) return 'under a minute';
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

/** "4 min ago", "3 h ago", "Nov 20". Null when never used. */
export function agoLabel(iso: string | null | undefined, now: Date): string | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  const mins = Math.max(0, Math.floor((now.getTime() - t) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `${h} h ago`;
  return shortDateET(iso);
}

/** "Since Nov 20 · last used 4 min ago" / "Since Nov 20 · not used yet". */
export function connectedSinceLine(
  status: Pick<McpStatus, 'connected_at' | 'last_used_at'>,
  now: Date,
): string {
  const since = shortDateET(status.connected_at);
  const used = agoLabel(status.last_used_at, now);
  const usedPart = used ? `last used ${used}` : 'not used yet';
  return since ? `Since ${since} · ${usedPart}` : usedPart;
}

/** The used/total pair for the meter, or null for an unlimited account. */
export function questionsMeter(status: McpStatus): { used: number; total: number; left: number } | null {
  if (status.unlimited) return null;
  const total = Math.max(1, status.questions_per_day || 10);
  const used = Math.min(total, Math.max(0, status.questions_used || 0));
  const left = status.questions_left ?? Math.max(0, total - used);
  return { used, total, left };
}

/** "7 left · resets at midnight ET (in 6 h 41 min)"; at zero, "Daily limit reached · …". */
export function questionsLeftLine(status: McpStatus, now: Date): string {
  const meter = questionsMeter(status);
  if (!meter) return 'Founder account: no daily limit';
  const until = untilLabel(status.resets_at, now);
  const reset = until ? `resets at midnight ET (in ${until})` : 'resets at midnight ET';
  return meter.left === 0 ? `Daily limit reached · ${reset}` : `${meter.left} left · ${reset}`;
}

/** "Up to 3 assistants at once, sharing 10 questions a day." */
export function sharedLimitLine(status: McpStatus | null): string {
  const n = maxAssistants(status);
  if (status?.unlimited) return `Up to ${n} assistants at once · founder account: no daily limit`;
  return `Up to ${n} assistants at once, sharing ${perDayLabel(status)}`;
}

/** "10 questions a day", from the server's limit (10 if it is missing). */
export function perDayLabel(status: McpStatus | null): string {
  const n = status?.questions_per_day && status.questions_per_day > 0 ? status.questions_per_day : 10;
  return `${n} question${n === 1 ? '' : 's'} a day`;
}

/** The Settings tile's one line. */
export function aiTileSummary(status: McpStatus | null): string {
  const mode = aiAssistantMode(status);
  if (!status || mode === 'hidden') return '';
  if (mode === 'trial') {
    const day = shortDateET(status.trial_converts_at);
    return day ? `Unlocks ${day}, when your trial ends` : 'Unlocks when your trial ends';
  }
  if (mode === 'preview') return 'Preview: connecting is for paying members';
  if (mode === 'suspended') return 'Paused on this account';
  if (mode === 'connected') {
    const meter = questionsMeter(status);
    const name = namesLine(connectedAssistants(status).map((a) => a.name));
    return meter ? `${name} connected · ${meter.left} of ${meter.total} left today` : `${name} connected · no limit`;
  }
  return 'Ask Claude, ChatGPT or Grok about Stats';
}

/** The tile's badge: New until connected, Locked on a trial. */
export function aiTileBadge(status: McpStatus | null): 'New' | 'Locked' | null {
  const mode = aiAssistantMode(status);
  if (mode === 'trial') return 'Locked';
  if (mode === 'setup' || mode === 'preview') return 'New';
  return null;
}

export interface SetupGuide {
  id: AssistantId;
  name: string;
  steps: string[];
  note: string;
}

/**
 * Setup steps, checked 2026-11-21 against each vendor's current help pages
 * (Claude: custom connectors; ChatGPT: developer mode and MCP apps; Grok:
 * grok.com/connectors). Menu names differ by plan and change often, so each
 * step names the place and the action, and the note says where it varies.
 */
export const SETUP_GUIDES: SetupGuide[] = [
  {
    id: 'claude',
    name: 'Claude',
    steps: [
      'In the Claude app or on claude.ai, open Settings, then Connectors.',
      `Tap Add custom connector and paste ${MCP_SERVER_ADDRESS}.`,
      'Tap Connect, sign in with your Signal Base email and tap Allow.',
      'Start a new chat and ask about Stats.',
    ],
    note: 'Free Claude plans allow one custom connector.',
  },
  {
    id: 'chatgpt',
    name: 'ChatGPT',
    steps: [
      'On chatgpt.com, open Settings, then Apps.',
      'Under Advanced settings, turn on Developer mode if ChatGPT asks for it.',
      `Choose Create app, paste ${MCP_SERVER_ADDRESS} and pick OAuth.`,
      'Sign in with your Signal Base email, tap Allow, then pick Signal Base in a new chat.',
    ],
    note: 'Set it up on the web. Menu names differ between ChatGPT plans.',
  },
  {
    id: 'grok',
    name: 'Grok',
    steps: [
      'Go to grok.com/connectors.',
      'Tap New Connector, then Custom.',
      `Paste ${MCP_SERVER_ADDRESS}, sign in with your Signal Base email and tap Allow.`,
      'Ask Grok about Stats in a new chat.',
    ],
    note: 'Set it up on grok.com. Business teams may need an admin to add it first.',
  },
];

export const TRY_ASKING: string[] = [
  'How often has Jokić gone over 11.5 rebounds in his last 10?',
  "Who leads tonight's NBA slate in points hit rate?",
  'Best price on the Lakers total right now?',
];

export const AI_FOOTNOTE =
  'Answers come from your assistant and can be wrong. Personal use only: no sharing or reselling data. 21+ in the US. Bet responsibly.';

// ── One-time moments ───────────────────────────────────────────────────────

/** AsyncStorage keys. Bump the suffix only if the moment itself changes. */
export const INTRO_DISMISSED_KEY = 'ai_assistant_intro_dismissed_v1';
export const LAST_ENTITLEMENT_KEY = 'ai_assistant_last_entitlement_v1';
export const UNLOCKED_SHOWN_KEY = 'ai_assistant_unlocked_shown_v1';

/**
 * The intro card at the top of Picks: paying or comped members who have not
 * connected and have not dismissed it. Never on a trial, never for the
 * reviewer, never once connected.
 */
export function shouldShowIntroCard(status: McpStatus | null, dismissed: boolean): boolean {
  return !dismissed && aiAssistantMode(status) === 'setup';
}

/**
 * The "AI Assistant is unlocked" sheet: once, the first time the app sees a
 * member who was on a trial and is now paying. The last entitlement seen on
 * this device is the memory; a device that never saw the trial does not show
 * it (the intro card covers that member instead).
 */
export function shouldShowUnlockedSheet(
  status: McpStatus | null,
  lastSeenEntitlement: string | null,
  alreadyShown: boolean,
): boolean {
  if (alreadyShown || !status) return false;
  return lastSeenEntitlement === 'trial' && status.eligible && !status.suspended;
}
