# HACHIJO HOT 10 — final 1601-track adoption

- Adoption date: 2026-08-31 JST
- Adoption commit: `8ac6b41` (`Adopt final 1601-track HOT10 master`)
- Production master: `HACHIJO_HOT10_master_1601_F41_MONO4_HACHIJOBOOST1_FUKUSHIMA_MINUS1.csv`
- Master SHA-256: `32e77245c26cda593d09dc4946c39dabcdb0fd99fab4265f633d2e5c2d19ca1d`
- Previous production master retained for regression testing: `HACHIJO_HOT10_master_1589_F41_MICROTUNE.csv`
- Detailed retained audit: `HACHIJO_HOT10_1589_PRODUCTION_to_1601_FINAL_diff_audit.csv`

## State and output handling

- Existing track state IDs `1`–`1589`, all state globals, and
  `last_generated_chart_date` (`2026-08-30`) were preserved.
- IDs `1590`–`1601` were appended with the standard blank track state.
- `hot10_output/latest.json` and the current chart file `2026-08-31.json` were
  intentionally not regenerated.
- Future projection files only were regenerated for `2026-09-01` through
  `2027-09-04` (369 days), using the production daily seed convention:
  `random.Random(YYYYMMDD)` per chart day.
- The normal 03:05 JST `today` job remains responsible for overwriting the
  current chart date and advancing production state. Its idempotence continues
  to depend on `last_generated_chart_date`, not on the existence of a projected
  JSON file.

## Validation

- The 1601-master schema and state-migration acceptance tests pass.
- The daily workflow schedule is unchanged: `5 18 * * *` UTC (03:05 JST).
