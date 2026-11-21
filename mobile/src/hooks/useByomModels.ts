/**
 * Loads the signed-in user's saved BYOM models. No screen. The calls
 * fail until a session exists. This hook does not turn sign-in on.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  deleteByomModel,
  fetchByomModels,
  saveByomModel,
  type ByomFilters,
  type ByomModel,
} from '@/lib/byom';
import { splitLoadError } from '@/lib/errors';

export function useByomModels() {
  const [models, setModels] = useState<ByomModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  // A response lands only when no newer load has started.
  const seq = useRef(0);

  const load = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    setNoAccess(false);
    try {
      const next = await fetchByomModels();
      if (seq.current !== id) return;
      setModels(next);
      setNoAccess(false);
    } catch (e: unknown) {
      if (seq.current !== id) return;
      const split = splitLoadError(e);
      if (split.noAccess) setModels([]);
      setNoAccess(split.noAccess);
      setError(split.error);
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(async (
    name: string,
    filters?: ByomFilters,
    season: number | null = null,
  ) => {
    await saveByomModel(name, filters, season);
    await load();
  }, [load]);

  const remove = useCallback(async (modelId: string) => {
    await deleteByomModel(modelId);
    await load();
  }, [load]);

  return { models, loading, error, noAccess, reload: load, save, remove };
}
