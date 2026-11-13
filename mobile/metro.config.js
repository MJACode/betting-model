// getSentryExpoConfig = Expo's default config plus Sentry's debug ids, so a
// stack trace from an OTA bundle maps back to source (lib/sentry.ts).
const { getSentryExpoConfig } = require('@sentry/react-native/metro');
const path = require('path');

const config = getSentryExpoConfig(__dirname);

// @supabase/supabase-js ESM bundle (index.mjs) contains:
//   import(OTEL_PKG)  — dynamic import with a variable argument
// Hermes rejects this with "Invalid expression encountered".
// The CJS bundle (index.cjs) uses require() instead and works fine.
// Force Metro to always resolve @supabase/supabase-js to the CJS entry.
const originalResolveRequest = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName === '@supabase/supabase-js') {
    return {
      filePath: path.resolve(
        __dirname,
        'node_modules/@supabase/supabase-js/dist/index.cjs'
      ),
      type: 'sourceFile',
    };
  }
  if (originalResolveRequest) {
    return originalResolveRequest(context, moduleName, platform);
  }
  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
