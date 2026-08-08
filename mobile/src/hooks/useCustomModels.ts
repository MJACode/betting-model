import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { pickMatchesFilters, type FilterablePick } from '@/lib/customModelFilters';
import type { CustomModel, CustomModelFilters, CustomModelRule } from '@/types';

const KEY = 'customModels.v1';

const listeners = new Set<(list: CustomModel[]) => void>();
let cached: CustomModel[] | null = null;

async function load(): Promise<CustomModel[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    cached = raw ? (JSON.parse(raw) as CustomModel[]) : [];
  } catch {
    cached = [];
  }
  return cached;
}

async function persist(list: CustomModel[]) {
  cached = list;
  await AsyncStorage.setItem(KEY, JSON.stringify(list));
  listeners.forEach((fn) => fn(list));
}

function newId(): string {
  return `cm_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function useCustomModels() {
  const [models, setModels] = useState<CustomModel[]>(cached ?? []);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((m) => {
      if (!mounted) return;
      setModels([...m]);
      setReady(true);
    });
    const listener = (m: CustomModel[]) => setModels([...m]);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const create = useCallback((
    name: string,
    rules: CustomModelRule[],
    filters?: CustomModelFilters,
  ): CustomModel => {
    const now = new Date().toISOString();
    const model: CustomModel = {
      id: newId(),
      name: name.trim() || 'Untitled model',
      rules,
      filters,
      created_at: now,
      updated_at: now,
    };
    const next = [...(cached ?? []), model];
    persist(next).catch((err) => console.warn('[customModels] create failed', err));
    return model;
  }, []);

  const update = useCallback((
    id: string,
    patch: Partial<Pick<CustomModel, 'name' | 'rules' | 'filters'>>,
  ) => {
    const now = new Date().toISOString();
    const next = (cached ?? []).map((m) =>
      m.id === id
        ? {
            ...m,
            name: patch.name != null ? patch.name.trim() || m.name : m.name,
            rules: patch.rules ?? m.rules,
            filters: 'filters' in patch ? patch.filters : m.filters,
            updated_at: now,
          }
        : m,
    );
    persist(next).catch((err) => console.warn('[customModels] update failed', err));
  }, []);

  const remove = useCallback((id: string) => {
    const next = (cached ?? []).filter((m) => m.id !== id);
    persist(next).catch((err) => console.warn('[customModels] remove failed', err));
  }, []);

  const get = useCallback((id: string): CustomModel | undefined => {
    return (cached ?? []).find((m) => m.id === id);
  }, []);

  return { models, ready, create, update, remove, get };
}

/**
 * Does this pick satisfy at least one rule AND all of the model's filters?
 *
 * Rules are OR'd (any model_id at its own prob/edge minimums); the model-level
 * filters are then AND'd over the survivors. A model with no filters behaves
 * exactly as it did before the filter builder shipped.
 */
export function pickMatchesModel(
  pick: FilterablePick & { model_probability: number; edge: number },
  model: CustomModel,
): boolean {
  if (model.rules.length === 0) return false;
  const passesRule = model.rules.some(
    (r) =>
      pick.model_id === r.model_id &&
      pick.model_probability >= r.min_prob &&
      pick.edge >= r.min_edge,
  );
  if (!passesRule) return false;
  return pickMatchesFilters(pick, model.filters);
}
