import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  DISCORD_JOIN_STORAGE_KEY,
  discordJoinBlocksRecap,
  discordJoinOffer,
  markDiscordJoinChosen,
  mergeDiscordJoinStores,
  observeDiscordTier,
  parseDiscordJoinStore,
  serializeDiscordJoinStore,
  userDiscordJoinRecord,
  withUserDiscordJoinRecord,
  type DiscordJoinChoice,
  type DiscordJoinStore,
  type DiscordJoinVariant,
  type DiscordTier,
} from '@/lib/discordJoin';

/**
 * Once-only Join screen, per account, on this device.
 *
 * The record is read before anything is written. A trial seen in memory
 * before that read returns is merged in, so a fast Unlock Discord early
 * still counts as a conversion. Join and Maybe later both set `seen`.
 */
export function useDiscordJoin(input: {
  userId: string | null;
  tier: DiscordTier;
  discordPaid: boolean;
  comped: boolean;
  onboardingFinished: boolean;
  surfaceClear: boolean;
  membershipHold: boolean;
}): {
  show: boolean;
  variant: DiscordJoinVariant | null;
  blocking: boolean;
  choose: (choice: DiscordJoinChoice) => void;
} {
  const [store, setStore] = useState<DiscordJoinStore>({ users: {} });
  const [ready, setReady] = useState(false);
  const loaded = useRef<string | null>(null);
  const userIdRef = useRef(input.userId);
  userIdRef.current = input.userId;

  useEffect(() => {
    let mounted = true;
    AsyncStorage.getItem(DISCORD_JOIN_STORAGE_KEY)
      .then((raw) => {
        if (!mounted) return;
        const parsed = parseDiscordJoinStore(raw);
        loaded.current = serializeDiscordJoinStore(parsed);
        setStore((prev) => mergeDiscordJoinStores(parsed, prev));
        setReady(true);
      })
      .catch((err) => {
        console.warn('[discordJoin] load failed', err);
        if (mounted) setReady(true);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const id = input.userId;
    if (!id) return;
    setStore((prev) => {
      const current = userDiscordJoinRecord(prev, id);
      const next = observeDiscordTier(current, input.tier);
      if (next === current) return prev;
      return withUserDiscordJoinRecord(prev, id, next);
    });
  }, [input.userId, input.tier]);

  useEffect(() => {
    if (!ready) return;
    const serial = serializeDiscordJoinStore(store);
    // A failed read leaves loaded null. Do not overwrite storage with the
    // empty memory copy; the next real change is the first write.
    if (loaded.current == null) {
      loaded.current = serial;
      return;
    }
    if (serial === loaded.current) return;
    loaded.current = serial;
    AsyncStorage.setItem(DISCORD_JOIN_STORAGE_KEY, serial).catch((err) => {
      console.warn('[discordJoin] save failed', err);
    });
  }, [store, ready]);

  const choose = useCallback((choice: DiscordJoinChoice) => {
    const id = userIdRef.current;
    if (!id) return;
    setStore((prev) => {
      const current = userDiscordJoinRecord(prev, id);
      const next = markDiscordJoinChosen(current, choice);
      if (next === current) return prev;
      return withUserDiscordJoinRecord(prev, id, next);
    });
  }, []);

  const record = userDiscordJoinRecord(store, input.userId);
  const offer = discordJoinOffer({
    discordPaid: input.discordPaid,
    seen: record.seen,
    sawTrial: record.sawTrial,
    comped: input.comped,
    onboardingFinished: input.onboardingFinished,
    surfaceClear: input.surfaceClear,
    hasAccount: input.userId != null,
  });

  return {
    show: ready && offer.show,
    variant: offer.show ? offer.variant : null,
    blocking: discordJoinBlocksRecap({
      storageReady: ready,
      membershipHold: input.membershipHold,
      show: ready && offer.show,
    }),
    choose,
  };
}
