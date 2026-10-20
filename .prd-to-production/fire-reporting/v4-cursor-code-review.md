# v4 historical IRS worksheet — independent code review

Read-only, 2026-10-19. Approved brief `.prd-to-production/brief.md` and `.prd-to-production/design/spec.md` (mockup approval explicitly waived). Compared `static/irs_2012_worksheet.js` with `research/historical-worksheet-fields.json`. Inspected `static/incident_report.js`, report/print paths in `static/app.js`, `#irs-print-guard` in `static/index.html`, and the print block in `static/styles.css`. No app/test edits, no test run, no browser or PDF pass (those are in progress elsewhere). No FaRDaP question set is claimed.

## Holds

Embedded inventory equals the research JSON: 9 sections, 158 unique IDs and labels, including `4.2*`, `4.2k`, `4.3a/b`, `5.16a`, `6.14a & b`, `8.35a`. Each row is `.irs-question[data-question-id]` plus an empty `.irs-answer` (`incident_report.js` 105–111). No run id, clip time, zone, template coordinate, plan, skill, or metric is written into those areas. Annex is a separate `.irs-evidence-annex` with a print page break. Title, 2012 attribution, v1-0p/v1-0n, and the not-current-FaRDaP / not-a-submission status match the spec. Cache with no booleans is “Cache status unknown”; a known fixture hash or a synthetic name is “Synthetic”; otherwise “Provenance not established”. Evidence text uses `textContent` / `createTextNode` (no worksheet `innerHTML`). Analyse, confirm, and reset null the snapshot; `fingerprint` covers clip, views, exclusions, observations, and spatial-review ids. `doReport` / `printReport` ignore a late response when the busy token, run id, or fingerprint no longer matches, and they do not `setRun` onto another run. Unverified Ctrl/Cmd+P hits `beforeprint` → `clearVerifiedPrint` → guard `#irs-print-guard` and hides `.app` unless `body.irs-print-verified`. `afterprint`, page change, fingerprint change, and the 15s timeout clear that class.

## Defects

**P1 — private paths survive scrub** (`incident_report.js` 4–11). Proven against the function: `~/secret/clip.mp4` and `file:///etc/passwd` are unchanged; `file:///Users/...` becomes `file://[redacted]` only because `/Users/` matches. A spaced path `/Users/Bede Lau/secret` becomes `[redacted] Lau/secret`. Relative `config/team-28.config` is unchanged. Named absolute prefixes, `runs/`, `./`, `../`, drive letters, UNC, `s3`, `http(s)`, bearer, and `sk-` are removed. Markup is not stripped; XSS still depends on `textContent` (not executed here).

**P2 — print invalidation timer is replaced, not cleared** (`app.js` 619–621). `printReport` assigns `verifiedPrintExpiry = setTimeout(clearVerifiedPrint, 15000)` without clearing an existing timer. A previous timeout can call `clearVerifiedPrint` during a later dialog and drop `irs-print-verified`. Whether the open dialog then shows the guard is untested.

**P2 — Cosmos vs Astra is only partly labeled** (`incident_report.js` 22–25, 72–73, 127–135, 141). Header Model/Prompt are `run.model_id` / `run.prompt_id` (Cosmos ids set on the run). Per-view “View analysis” reads `analysis.model_id` / `prompt_id`, which Cosmos does not store, so those ids are omitted. After grounding, the narrative is Astra’s and is attributed only on “Spatial review” and `bbox_provenance`. A disabled review’s `reason` (unreviewed Cosmos boxes) is dropped, so the line is only “Status: disabled”.

**P3 — aggregate cache can hide an unknown view** (`incident_report.js` 47–49). Non-booleans are removed before the all/some/none test. One `true` plus a missing flag summarizes as “Cached”. Current Cosmos analysis always writes a boolean, so this is the legacy/partial shape.

**P3 — blank exclusion reason is filled in the annex** (`incident_report.js` 63): `scrub(reason) || 'Reason not recorded'`. Worksheet answers stay empty.

## Untested here

Desktop/mobile overflow (320px; `.irs-question-id` and `.irs-source-page` are `nowrap`), multipage A4 clipping (`body` keeps `overflow-x:hidden`), PDF completeness, native Ctrl+P / `afterprint` ordering versus `window.print()`, and a live late A/B response. The code guards that race; this review did not execute it. No current official form was reviewed because none is in this checkout.
