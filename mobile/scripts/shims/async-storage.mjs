/** Node stand-in for @react-native-async-storage/async-storage: one in-memory map. */
// One map per process, even when ESM and CJS each load this file.
const store = (globalThis.__asyncStorageShim ??= new Map());
const AsyncStorage = {
  async getItem(k) { return store.has(k) ? store.get(k) : null; },
  async setItem(k, v) { store.set(k, String(v)); },
  async removeItem(k) { store.delete(k); },
  async multiRemove(keys) { for (const k of keys) store.delete(k); },
  __store: store,
};
export default AsyncStorage;
