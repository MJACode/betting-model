/** Node stand-in so the today's-board read can be imported outside the app. */
export const Platform = {
  OS: 'ios',
  select(options) {
    return options.ios ?? options.default;
  },
};

export const AppState = {
  currentState: 'active',
  addEventListener() {
    return { remove() {} };
  },
};

export const StyleSheet = { create: (styles) => styles };
export const Linking = { openURL: async () => {} };
export const Alert = { alert() {} };
export const AccessibilityInfo = {
  isReduceMotionEnabled: async () => false,
  addEventListener() {
    return { remove() {} };
  },
};

const empty = () => ({});
export const NativeModules = new Proxy({}, { get: empty });
export const TurboModuleRegistry = { get: () => null, getEnforcing: () => ({}) };
