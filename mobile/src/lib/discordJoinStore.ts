import AsyncStorage from '@react-native-async-storage/async-storage';

import {
  DISCORD_JOIN_STORAGE_KEY,
  notifyDiscordJoinUserForgotten,
  parseDiscordJoinStore,
  serializeDiscordJoinStore,
  withoutUserDiscordJoinRecord,
  type DiscordJoinStore,
} from './discordJoin';

/**
 * One queue for every read and write of the Join map. A deletion that is
 * already queued cannot be overwritten by an older in-flight save, and a
 * read cannot pass a write that has not landed yet.
 */
let tail: Promise<void> = Promise.resolve();

function enqueue<T>(work: () => Promise<T>): Promise<T> {
  const run = tail.then(work, work);
  tail = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

export function readDiscordJoinRaw(): Promise<string | null> {
  return enqueue(() => AsyncStorage.getItem(DISCORD_JOIN_STORAGE_KEY));
}

export function writeDiscordJoinStore(store: DiscordJoinStore): Promise<void> {
  const serial = serializeDiscordJoinStore(store);
  return enqueue(() => AsyncStorage.setItem(DISCORD_JOIN_STORAGE_KEY, serial));
}

/** Remove one account. Other accounts on this device stay in the map. */
export function forgetDiscordJoinUser(userId: string): Promise<void> {
  return enqueue(async () => {
    const raw = await AsyncStorage.getItem(DISCORD_JOIN_STORAGE_KEY);
    const next = withoutUserDiscordJoinRecord(parseDiscordJoinStore(raw), userId);
    await AsyncStorage.setItem(DISCORD_JOIN_STORAGE_KEY, serializeDiscordJoinStore(next));
    notifyDiscordJoinUserForgotten(userId);
  });
}
