import { requireOptionalNativeModule } from 'expo';

import { linkShape } from '@/lib/betslipLinks';
import { recordReport } from '@/lib/crashLog';

/**
 * A sportsbook hand-off that did NOT end in the book's app via its claimed
 * link, written to `app_errors` so the cause is a query, not a question to
 * the member (docs/app_errors.md, "Hand-offs that missed the app").
 *
 * 2026-11-15: BetMGM still opened Safari on build 14301. Three causes fit and
 * nothing recorded which: the native module missing from the binary, iOS
 * refusing the claimed link, or the link not being asked about at all. The
 * app logged its version (1.3.0) and not its build, so even "which binary"
 * took a screenshot.
 *
 * Kind `js_error` with a `handoff:` message: the RPC refuses a kind it does
 * not know, and a refused report stops the queue behind it (crashLog), so no
 * new kind without its migration applied first. At most one row per book and
 * route per app session: the crash log's 60-an-hour cap is shared with real
 * crashes. Of the link, only the host and path are kept (the query names the
 * selection), with the member's state masked: the state picker says "Stored
 * on this device only". The answers are repeated in the message because the
 * RPC drops an oversized `extra`.
 */

export type HandoffRoute =
  /** The app, by the scheme that said it is installed (iOS refused the link). */
  | 'scheme'
  /** The App Store. */
  | 'store'
  /** The stored link through Linking.openURL: the app or Safari, iOS decides. */
  | 'link'
  /** The book's web root. */
  | 'web'
  /** Nothing opened. */
  | 'failed';

export interface HandoffMiss {
  book: string;
  route: HandoffRoute;
  /** isBookAppInstalled: true / false / null (cannot tell). */
  installed: boolean | null;
  /** The link iOS was asked to open in the app only, or null if none. */
  claimed: string | null;
  /** openUniversalLinkOnly: true / false / null (cannot ask, or not asked). */
  viaApp: boolean | null;
  /** Is the OpenInApp native module in this binary? */
  moduleInBinary: boolean;
  /** The scheme that was opened, on the 'scheme' route. */
  scheme?: string | null;
}

const logged = new Set<string>();

/** The binary's build number (CFBundleVersion), or null when it cannot be read. */
export function nativeBuild(): string | null {
  try {
    const app = requireOptionalNativeModule<{ nativeBuildVersion?: string | null }>('ExpoApplication');
    return app?.nativeBuildVersion ?? null;
  } catch {
    return null;
  }
}

const flag = (v: boolean | null): string => (v === null ? '?' : v ? '1' : '0');

export function noteHandoffMiss(miss: HandoffMiss): void {
  const key = `${miss.book}:${miss.route}`;
  if (logged.has(key)) return;
  logged.add(key);
  void recordReport({
    kind: 'js_error',
    message: `handoff: ${miss.book} -> ${miss.route} (inst=${flag(miss.installed)} via=${flag(miss.viaApp)} mod=${flag(miss.moduleInBinary)} claimed=${flag(miss.claimed != null)} build=${nativeBuild() ?? '?'})`,
    extra: {
      handoff: {
        book: miss.book,
        route: miss.route,
        installed: miss.installed,
        claimed: linkShape(miss.claimed),
        viaApp: miss.viaApp,
        moduleInBinary: miss.moduleInBinary,
        scheme: miss.scheme ?? null,
        nativeBuild: nativeBuild(),
      },
    },
  });
}

export function resetHandoffLogForTests(): void {
  logged.clear();
}
