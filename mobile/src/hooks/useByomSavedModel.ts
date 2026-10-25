/**
 * One saved model by id. The list RPC is the only read; there is no
 * single-model call. A slower response does not replace a newer one.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuth } from '@/hooks/useAuth';
import { fetchByomModels, type ByomModel } from '@/lib/byom';
import { errorText, isAbortError } from '@/lib/errors';

export function useByomSavedModel(modelId: string) {
  const { signedIn, ready } = useAuth();
  const [model, setModel] = useState<ByomModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (!ready) return;
    if (!signedIn) {
      seq.current += 1;
      setModel(null);
      setMissing(false);
      setError(null);
      setLoading(false);
      return;
    }
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const models = await fetchByomModels();
      if (seq.current !== id) return;
      const found = models.find((row) => row.model_id === modelId) ?? null;
      setModel(found);
      setMissing(found == null);
    } catch (e: unknown) {
      if (seq.current !== id) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [modelId, ready, signedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  return { model, loading: !ready || loading, error, missing, reload: load, signedIn };
}
