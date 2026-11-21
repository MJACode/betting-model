/**
 * One saved model by id. The list RPC is the only read; there is no
 * single-model call. A slower response does not replace a newer one.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuth } from '@/hooks/useAuth';
import { fetchByomModels, type ByomModel } from '@/lib/byom';
import { splitLoadError } from '@/lib/errors';

export function useByomSavedModel(modelId: string) {
  const { signedIn, ready } = useAuth();
  const [model, setModel] = useState<ByomModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  const [missing, setMissing] = useState(false);
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (!ready) return;
    if (!signedIn) {
      seq.current += 1;
      setModel(null);
      setMissing(false);
      setError(null);
      setNoAccess(false);
      setLoading(false);
      return;
    }
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    setNoAccess(false);
    try {
      const models = await fetchByomModels();
      if (seq.current !== id) return;
      const found = models.find((row) => row.model_id === modelId) ?? null;
      setModel(found);
      setMissing(found == null);
      setNoAccess(false);
    } catch (e: unknown) {
      if (seq.current !== id) return;
      const split = splitLoadError(e);
      if (split.noAccess) setModel(null);
      setNoAccess(split.noAccess);
      setError(split.error);
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [modelId, ready, signedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  return { model, loading: !ready || loading, error, noAccess, missing, reload: load, signedIn };
}
