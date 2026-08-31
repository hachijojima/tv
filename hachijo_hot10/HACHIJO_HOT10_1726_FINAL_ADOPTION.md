# HACHIJO HOT10 1726C Final Adoption

- Adoption time (JST): 2026-08-31
- Production adoption commit: `b6df9d1` (`Adopt 1726-track HACHIJO HOT10 master`)
- Previous master retained: `HACHIJO_HOT10_master_1601_F41_MONO4_HACHIJOBOOST1_FUKUSHIMA_MINUS1.csv`
  (`32e77245c26cda593d09dc4946c39dabcdb0fd99fab4265f633d2e5c2d19ca1d`)
- Adopted master: `HACHIJO_HOT10_master_1726_F41_EDGE125_90S00S_FULL.csv`
  (`98b2bace5438d0e7e5b4a70f2d4638a37edb1f3e23131e01d56e5ca94a2b565e`)
- Master validation: 1726 tracks, IDs 1..1726, exact/normalized duplicates 0.
- Source changes: 180 existing updates, including 47 identity replacements; 125 additions.
- State migration: 1554 unchanged existing track states preserved, 47 replaced identities reset to the standard initial track state, and 125 new track states added. Global state and `last_generated_chart_date` were preserved.
- Protected live output: `latest.json` and the current chart `2026-08-31.json` are byte-identical to their pre-adoption versions. Past output is unchanged.
- Future projection: regenerated with the 1726C master for `2026-09-01` through `2027-09-05` (370 chart days). The one-year projection horizon is retained.
- Verification: source-bundle preflight, post-migration state audit, same-date idempotence check, and `python3 test_hot10.py` (14 tests) all passed.
- Runtime: F4.1-B scoring, 03:00 JST chart boundary, the 03:05 JST production overwrite path, daily cron (`5 18 * * *` UTC), UI, and dashboard remain unchanged.
