# models/saved — trained artifacts

**Active production `.pkl` files stay tracked in git** so a Railway / local
checkout can score without an extra download step. The keep-list is
[`MANIFEST.md`](MANIFEST.md): `model_registry.is_active = 1`, not "newest
filename per `model_id`".

Older versioned pkls (same `model_id`, a timestamp that is **not** the live
path) are gitignored from the default checkout. They are not the live path:

1. `model_registry.is_active = 1` points at the live `model_path`.
2. If the file is missing on disk, `models.trainer.load_model` restores bytes
   from the Supabase `model_artifacts` table (`_restore_artifact`) — **only
   when a blob exists**. Many live artifacts have no blob; git is still the
   worker's copy.

Do not delete the only copy of an **active** artifact. Before `git rm
--cached` on a pkl, confirm `model_registry` does not list it as active (or
that `model_artifacts` holds the bytes).

`nfl_prop_params.json` stays tracked (small, required by the NFL prop scorer).

**Do not gitignore `nfl/data/odds_cache/`.** That tree is a different diet
question and is irreplaceable.
