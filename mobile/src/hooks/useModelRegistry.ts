import { useEffect, useState } from 'react';
import { fetchModelRegistry } from '@/lib/queries';
import type { ModelRegistryRow } from '@/types';

/** Latest active model_registry row for a model — holdout metrics + version. */
export function useModelRegistry(modelId: string) {
  const [row, setRow] = useState<ModelRegistryRow | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetchModelRegistry(modelId)
      .then((r) => {
        if (mounted) setRow(r);
      })
      .catch(() => {
        if (mounted) setRow(null);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [modelId]);

  return { registry: row, loading };
}
