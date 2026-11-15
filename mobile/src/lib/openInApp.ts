import { requireOptionalNativeModule } from 'expo';
import { Platform } from 'react-native';

/**
 * Open an https link ONLY in an installed app that claims it.
 *
 * `Linking.openURL` cannot do this: it opens Safari when no app claims the
 * link and reports success either way. The native module
 * (modules/open-in-app) calls iOS with `universalLinksOnly`, so:
 *
 *   true   an installed app took the link
 *   false  no installed app took it, and nothing was opened
 *   null   this build cannot ask (Android, web, or a binary built before the
 *          module existed). The caller keeps its old route.
 *
 * `requireOptionalNativeModule` returns null instead of throwing when the
 * binary has no such module, so this file is safe in any bundle.
 */
interface OpenInAppNative {
  openUniversalLinkOnly(url: string): Promise<boolean>;
}

const native: OpenInAppNative | null =
  Platform.OS === 'ios' ? requireOptionalNativeModule<OpenInAppNative>('OpenInApp') : null;

/** Is the native module in this binary? False on Android and on a binary
 *  built before it existed. A `null` from the call below with this `true`
 *  means iOS was asked and the call threw. */
export const openInAppAvailable = native != null;

export async function openUniversalLinkOnly(url: string): Promise<boolean | null> {
  if (!native) return null;
  try {
    return (await native.openUniversalLinkOnly(url)) === true;
  } catch {
    return null; // asked and not answered: no evidence either way
  }
}
