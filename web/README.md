# Signal Base marketing site

Static site for signalbase-ai.com. Three pages: `/`, `/terms`, `/privacy`.

The record row on the landing page is not a stored number. The browser reads the same public view as the app's Record tab, `v_public_track_record`, with the public Supabase anon key, and rolls the rows up the same way `mobile/src/lib/trackRecord.ts` does (retired models left out, picks = wins + losses + pushes, posted-stake `units`). If that request fails or comes back empty, the row stays hidden.

`web/src/public-config.json` holds that anon key. It is the public key already shipped in the app (`EXPO_PUBLIC_SUPABASE_ANON_KEY` for project `vvprgnrmzeekokzkrkfu`). It is not a service-role key. The build refuses any key whose JWT role is not `anon`.

Terms and Privacy are rendered at build time from `content/terms.md` and `content/privacy.md`. Those files stay as drafted. The build strips the DRAFT banner, removes bracketed `[ATTORNEY NOTE: …]` notes, fills `[DATE]` with the build date in America/New_York, and drops the “filled in at publish” clause so the line is “Effective date:” plus that date. The build fails if a `[` still appears in any generated HTML page.

No cookies, analytics, third-party scripts, or hosted fonts. Type is the system font stack.

## Local preview

From `web/`:

```bash
python3 build.py --serve
```

Then open http://127.0.0.1:8765/ , http://127.0.0.1:8765/terms , and http://127.0.0.1:8765/privacy .

`python3 build.py` alone writes `web/dist/` and does not serve it. `dist/` is gitignored.

To check the record math without a browser:

```bash
node --test src/record-math.test.mjs
```

## Vercel

Create a project from this repo. Do not change DNS from here.

- Root Directory: `web`
- Framework Preset: Other
- Build Command: `python3 build.py` (also set in `vercel.json`)
- Output Directory: `dist` (also set in `vercel.json`)
- Install Command: none. The build uses the Python standard library.

The build reads `mobile/src/lib/thresholds.generated.ts` when that file is in the checkout, and fails if `src/retired-models.json` has drifted from `RETIRED_MODELS`. Vercel needs the rest of the repo visible during the build. In Project Settings → Build & Deployment → Root Directory, leave **Include source files outside of the Root Directory in the Build Step** on (the default for projects created after 27 August 2020).

Add both `signalbase-ai.com` and `www.signalbase-ai.com` on the project's Domains screen, and set one to redirect to the other.

### DNS

Vercel's current docs (the [A record guide](https://vercel.com/kb/guide/a-record-and-caa-with-vercel) and [Adding a custom domain](https://vercel.com/docs/domains/working-with-domains/add-a-domain), checked 2026-10-24) do **not** use a single shared `www` target of `cname.vercel-dns.com`.

Use the values on the project's domain card after the domain is added:

| Host | Type | Value |
|---|---|---|
| `@` (apex) | A | The card's A value. For most projects that is `76.76.21.21`. Newer projects can be assigned a different anycast address (the docs' example is `216.198.79.1`). |
| `www` | CNAME | The card's CNAME target. That is a per-project name, for example `d1d4fc829fe7bc7c.vercel-dns-017.com`, not `cname.vercel-dns.com`. |

Do not add an AAAA record. Vercel does not support IPv6 for a domain that uses a third-party DNS provider, and an AAAA record can block the certificate.

The domain card is what Vercel checks. If the card shows `76.76.21.21`, that is the apex A record to publish.
