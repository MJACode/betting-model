# Signalbase — TestFlight submission runbook

Everything you need to take the current `mobile/` codebase from "works in Expo
Go" to "available in TestFlight on your phone." All commands run from a
Windows terminal in the `mobile/` folder unless noted.

---

## 0. Prerequisites (one-time)

- [ ] Apple Developer Program enrollment active ($99/yr).
- [ ] Logged in to https://appstoreconnect.apple.com with the same Apple ID.
- [ ] Node 20 LTS installed (`node --version` shows v20.x).
- [ ] `npm install -g eas-cli` then `eas login`.
- [ ] Privacy policy live at https://signalbase-ai.com/privacy
      (copy `docs/privacy.html` to the domain, or use any static host).
- [ ] In `mobile/`, copy `.env.example` to `.env` and paste the Supabase
      `anon` key. Confirm `npm start` loads picks on your phone via Expo Go
      before trying to build.

---

## 1. Create the App Store Connect record

Do this in the App Store Connect web UI **once** before the first build.

1. https://appstoreconnect.apple.com → **My Apps** → **+** → **New App**
2. Fill in:
   - **Platforms:** iOS
   - **Name:** `Signalbase`
   - **Primary language:** English (U.S.)
   - **Bundle ID:** `com.mja.bettingpicks` (select from dropdown — EAS will
     register it on first build if it's not there yet)
   - **SKU:** `signalbase-ios-001` (any unique string, never shown to users)
   - **User access:** Full Access
3. Click Create. You don't need to fill in the full App Store listing yet —
   TestFlight only requires the app shell.

---

## 2. Set the Supabase key as an EAS secret

The `.env` file is gitignored, but EAS Build runs in the cloud and needs
the value. One time:

```
eas secret:create --scope project --name EXPO_PUBLIC_SUPABASE_URL  --value https://vvprgnrmzeekokzkrkfu.supabase.co
eas secret:create --scope project --name EXPO_PUBLIC_SUPABASE_ANON_KEY --value <paste-anon-key>
```

Verify with `eas secret:list`.

---

## 3. Build the IPA

```
cd mobile
npm install
eas build --platform ios --profile production
```

On the first run EAS will prompt for:
- Apple ID + app-specific password (or it opens a browser SSO flow)
- "Generate a new Apple Distribution Certificate?" — **Yes**
- "Generate a new Provisioning Profile?" — **Yes**

Build takes ~15–25 min in the cloud queue. When it's done you'll get an
emailed download link and the build is also visible at https://expo.dev.

---

## 4. Submit to TestFlight

```
eas submit --platform ios --latest
```

This uploads the IPA you just built to App Store Connect. ~5 min.

Once uploaded, the build appears in App Store Connect → **TestFlight** tab
with status "Processing" (15–30 min) → "Ready to Submit" → fill out:

- **Test Information** (required before any tester can install):
  - **Beta App Description:** see `APP_STORE_METADATA.md`
  - **Email:** matt.alksninis@gmail.com
  - **Privacy Policy URL:** https://signalbase-ai.com/privacy
  - **What to Test:** see `APP_STORE_METADATA.md`
- **Export Compliance:** "Does your app use encryption?" → **No** (we set
  `ITSAppUsesNonExemptEncryption: false` in `app.json` so this should auto-fill).

For **internal testing** (up to 100 testers from your team, no Apple review
required): add yourself under TestFlight → Internal Testing → create a group
→ add your Apple ID → enable the build. The TestFlight invite email arrives
within a minute.

For **external testing** (up to 10,000 testers, requires light Apple review,
~24h): create a public link under External Testing.

---

## 5. Shipping a new build

Builds are **manual-only** so the push to TestFlight is always deliberate.
Trigger from the Actions tab → **Mobile TestFlight build** → **Run workflow**,
selecting the branch you want to build (`.github/workflows/mobile-build.yml`,
`workflow_dispatch`). It runs `eas build --profile production` then
`eas submit`. Nothing ships to TestFlight on a plain merge to `master`.

The `production` profile in `eas.json` has `autoIncrement: true`, so the
build number bumps automatically. Bump the `version` field in `app.json`
manually when you cut a real release (e.g. 1.0.0 → 1.1.0).

For the unattended submit step to work, EAS must have an **App Store
Connect API key** registered (one-time setup, see "ASC API key" below).
Manual fallback when CI is unavailable:

```
cd mobile
eas build --platform ios --profile production
eas submit --platform ios --latest
```

### ASC API key (one-time)

1. https://appstoreconnect.apple.com/access/integrations/api → **+** →
   create a key with **Admin** or **App Manager** role. Download the `.p8`.
2. From a local machine:
   ```
   cd mobile
   eas credentials
   ```
   → iOS → production → **App Store Connect API key** → Add new → paste
   the Issuer ID + Key ID and upload the `.p8`. EAS stores it server-side;
   CI runs after this can submit non-interactively.

---

## 6. Over-the-air updates (no rebuild)

For JS/asset-only changes (no native code, no new permissions), publish an
OTA update instead of a full build:

```
eas update --branch production --message "Tweak threshold display"
```

Open TestFlight on the phone, force-quit Signalbase, reopen — the update
loads on launch. Saves ~20 min per change vs. a full build.

---

## 7. Common rejections / how to avoid

| Issue | Fix |
|---|---|
| "Missing Privacy Policy URL" | Make sure step 0 is done before step 4. |
| "App references gambling" | We frame it as model output / research (see metadata). Don't add a "Place Bet" button. |
| "Crashes on launch" | Test the release build locally first: `eas build --platform ios --profile preview` then install via the link. |
| "Anon key doesn't work" | Verify both EAS secrets are set with `eas secret:list`. EAS bakes them at build time, not runtime. |
| "Age rating mismatch" | Set 17+ in App Store Connect → App Information → Age Rating → "Frequent/Intense Simulated Gambling: Yes". |
