import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  DISCORD_JOIN_STORAGE_KEY,
  discordJoinBlocksRecap,
  discordJoinOffer,
  discordJoinVisible,
  markDiscordJoinChosen,
  mergeDiscordJoinStores,
  observeDiscordTier,
  onDiscordJoinUserForgotten,
  parseDiscordJoinStore,
  serializeDiscordJoinStore,
  userDiscordJoinRecord,
  withUserDiscordJoinRecord,
  withoutUserDiscordJoinRecord,
  type DiscordJoinChoice,
  type DiscordJoinStore,
  type DiscordJoinVariant,
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
  /** A loaded trialing row. Not the fallback tier. */
  trialConfirmed: boolean;
  discordPaid: boolean;
  comped: boolean;
  onboardingFinished: boolean;
  surfaceClear: boolean;
  membershipHold: boolean;
}): {
  show: boolean;
  variant: DiscordJoinVariant | null;
  /** This account already dismissed Join. Replay intro uses the Settings sentence. */
  joinSeen: boolean;
  blocking: boolean;
  choose: (choice: DiscordJoinChoice) => void;
} {
  const [store, setStore] = useState<DiscordJoinStore>({ users: {} });
  const [ready, setReady] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const loaded = useRef<string | null>(null);
  const readGen = useRef(0);
  const userIdRef = useRef(input.userId);
  userIdRef.current = input.userId;

  useEffect(() => {
    let mounted = true;
    const gen = ++readGen.current;
    AsyncStorage.getItem(DISCORD_JOIN_STORAGE_KEY)
      .then((raw) => {
        if (!mounted || gen !== readGen.current) return;
        const parsed = parseDiscordJoinStore(raw);
        loaded.current = serializeDiscordJoinStore(parsed);
        setStore((prev) => mergeDiscordJoinStores(parsed, prev));
        setReady(true);
      })
      .catch((err) => {
        console.warn('[discordJoin] load failed', err);
        if (!mounted || gen !== readGen.current) return;
        // Stay hidden, and do not write. A write here would replace every
        // other account's record with whatever this session has in memory.
        setLoadFailed(true);
        setReady(true);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    return onDiscordJoinUserForgotten((id) => {
      readGen.current += 1;
      setStore((prev) => {
        const next = withoutUserDiscordJoinRecord(prev, id);
        loaded.current = serializeDiscordJoinStore(next);
        return next;
      });
      setReady(true);
    });
  }, []);

  useEffect(() => {
    const id = input.userId;
    if (!id || !input.trialConfirmed) return;
    setStore((prev) => {
      const current = userDiscordJoinRecord(prev, id);
      const next = observeDiscordTier(current, 'trial');
      if (next === current) return prev;
      return withUserDiscordJoinRecord(prev, id, next);
    });
  }, [input.userId, input.trialConfirmed]);

  useEffect(() => {
    if (!ready || loadFailed) return;
    const serial = serializeDiscordJoinStore(store);
    if (loaded.current == null) {
      loaded.current = serial;
      return;
    }
    if (serial === loaded.current) return;
    loaded.current = serial;
    AsyncStorage.setItem(DISCORD_JOIN_STORAGE_KEY, serial).catch((err) => {
      console.warn('[discordJoin] save failed', err);
    });
  }, [store, ready, loadFailed]);

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
  const show = discordJoinVisible({
    ready,
    loadFailed,
    offerShow: offer.show,
  });

  return {
    show,
    variant: show ? offer.variant : null,
    joinSeen: ready && !loadFailed && record.seen,
    blocking: discordJoinBlocksRecap({
      storageReady: ready,
      membershipHold: input.membershipHold,
      show,
    }),
    choose,
  };
}
