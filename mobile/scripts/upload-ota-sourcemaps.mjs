#!/usr/bin/env node
/**
 * Upload the source maps of the bundle this OTA published.
 *
 * The workflow exports with `expo export --source-maps` and publishes that
 * directory (`eas update --skip-bundler --input-dir`). The maps and the
 * bundle are the same files. `eas update` on its own does not leave them
 * where an upload step can read them.
 *
 * Release and dist are the native SDK's, read from app.json:
 *   release = <ios bundle id>@<version>+<buildNumber>
 *   dist    = <buildNumber>
 * That is what an event carries when Sentry.init does not override them, so
 * the upload and the event name the same release. The debug id written by
 * the Sentry metro config (metro.config.js) is what picks this bundle out
 * from the embedded one under that same release.
 *
 *   node scripts/upload-ota-sourcemaps.mjs [--dry-run] <export-dir>
 *
 * --dry-run prints the plan as JSON and does not call sentry-cli.
 * Needs SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT when it actually uploads.
 */

import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

function appRelease() {
  const app = JSON.parse(fs.readFileSync(path.join(here, '..', 'app.json'), 'utf8')).expo;
  const bundleId = app.ios.bundleIdentifier;
  const version = app.version;
  const build = String(app.ios.buildNumber);
  return { release: `${bundleId}@${version}+${build}`, dist: build };
}

function isBundle(name) {
  return name.endsWith('.map') || name.endsWith('.js') || name.endsWith('.hbc');
}

function walk(dir) {
  const files = [];
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, item.name);
    if (item.isDirectory()) files.push(...walk(full));
    else if (item.isFile() && isBundle(item.name)) files.push(full);
  }
  return files;
}

function groupAssets(assetPaths) {
  const groups = new Map();
  for (const assetPath of assetPaths) {
    const parsed = path.parse(assetPath);
    const key = parsed.ext === '.map' ? path.join(parsed.dir, parsed.name) : assetPath;
    const list = groups.get(key) ?? [];
    list.push(assetPath);
    groups.set(key, list);
  }
  return groups;
}

function stampDebugId(mapPath) {
  const sourceMap = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
  if (sourceMap.debugId && sourceMap.debug_id !== sourceMap.debugId) {
    sourceMap.debug_id = sourceMap.debugId;
    fs.writeFileSync(mapPath, JSON.stringify(sourceMap));
  }
  return sourceMap.debugId ?? sourceMap.debug_id ?? null;
}

function sentryCliPath() {
  if (process.env.SENTRY_CLI_EXECUTABLE) return process.env.SENTRY_CLI_EXECUTABLE;
  try {
    return require.resolve('@sentry/cli/bin/sentry-cli');
  } catch {
    return null;
  }
}

function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const dirArg = args.find((arg) => arg !== '--dry-run');
  if (!dirArg) {
    console.error('Usage: upload-ota-sourcemaps.mjs [--dry-run] <export-dir>');
    process.exit(1);
  }
  const dir = path.resolve(dirArg);
  if (!fs.existsSync(dir)) {
    console.error(`Export directory not found: ${dir}`);
    process.exit(1);
  }

  const { release, dist } = appRelease();
  const groups = [];
  for (const [, assets] of groupAssets(walk(dir))) {
    const mapPath = assets.find((file) => file.endsWith('.map'));
    if (!mapPath) continue;
    const debugId = stampDebugId(mapPath);
    groups.push({
      files: assets,
      hermes: assets.some((file) => file.endsWith('.hbc')),
      debugId,
    });
  }
  if (groups.length === 0) {
    console.error(
      `No source maps in ${dir}. The export has to be \`expo export --source-maps\`.`,
    );
    process.exit(1);
  }

  const plan = { release, dist, groups: groups.map(({ files, hermes, debugId }) => ({ files, hermes, debugId })) };
  if (dryRun) {
    process.stdout.write(`${JSON.stringify(plan)}\n`);
    return;
  }

  const org = (process.env.SENTRY_ORG || '').trim();
  const project = (process.env.SENTRY_PROJECT || '').trim();
  const token = (process.env.SENTRY_AUTH_TOKEN || '').trim();
  if (!org || !project || !token) {
    console.error('SENTRY_ORG, SENTRY_PROJECT and SENTRY_AUTH_TOKEN are required.');
    process.exit(1);
  }
  const cli = sentryCliPath();
  if (!cli) {
    console.error('sentry-cli was not found. Install @sentry/react-native (it ships @sentry/cli).');
    process.exit(1);
  }
  const url = (process.env.SENTRY_URL || 'https://sentry.io/').trim();
  for (const group of groups) {
    const cmd = [
      'sourcemaps', 'upload',
      '--release', release,
      '--dist', dist,
      '--org', org,
      '--project', project,
    ];
    if (group.hermes) cmd.push('--debug-id-reference');
    cmd.push(...group.files);
    execFileSync(cli, cmd, {
      stdio: 'inherit',
      env: { ...process.env, SENTRY_URL: url, SENTRY_ORG: org, SENTRY_PROJECT: project, SENTRY_AUTH_TOKEN: token },
    });
  }
  console.error(`Uploaded ${groups.length} source map(s) for ${release} dist ${dist}.`);
}

main();
