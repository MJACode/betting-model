/**
 * Loads the signed-in user's saved BYOM models. No screen. The calls
 * fail until a session exists. This hook does not turn sign-in on.
 */

import { useCallback, useEffect, useState } from 'react';

import {
  deleteByomModel,
  fetchByomModels,
  saveByomModel,
  type ByomFilters,
  type ByomModel,
} from '@/lib/byom';
import { errorText, isAbortError } from '@/lib/errors';

export function useByomModels() {
  const [models, setModels] = useState<ByomModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setModels(await fetchByomModels());
    } catch (e: unknown) {
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      setLoading(false);
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

  return { models, loading, error, reload: load, save, remove };
}
