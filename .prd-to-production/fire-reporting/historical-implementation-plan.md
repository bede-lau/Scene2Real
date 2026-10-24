# Historical IRS worksheet — Devin implementation handoff

2026-10-19 · preparation only · implements brief v4 R-source/R-blank/R-evidence/R-integrity/R-print/R-local/R-verify after brief + design approval (or explicit waiver). No app/test edits, tests, enquiry, commit, push or deploy in this step. Read-only audit: `static/incident_report.js`, `static/app.js` (`act`, `setRun`, `renderReport`, `doReport`), `static/index.html` `#s7`, `static/styles.css` incident + `@media print`, `tests/e2e/incident-report.spec.mjs`, `research/historical-worksheet-fields.json` + notes.

## Boundary
Frontend only. No backend route, stored object, model call, credential, external service or persistence. The input is still `GET /api/runs/{id}` (one snapshot) plus a static copy of the source inventory. Cosmos, planner and simulator are unchanged and `run.json` is never written.

## Future files Devin owns (accommodating existing uncommitted edits)
- `static/irs_2012_worksheet.js` (new): ES module exporting the frozen `historical-worksheet-fields.json` verbatim (status, source, scope, 9 sections, 158 `{id,label,source_page}`). Needed because `static/` cannot serve `.prd-to-production/`. Hand-edited content is not allowed. The check test asserts deep equality with the research JSON.
- `static/incident_report.js`: replace the demo builder/renderer with `buildWorksheet(run, generatedAt)` + `renderWorksheet(doc, ws)`. Keep `scrub`, `analysisReady`, `fingerprint`, `retainReport` (hardened, see below). Remove `planBlock`/`metricsBlock`/zone rendering from output.
- `static/app.js`: only `renderReport`/`doReport`/import names and note strings.
- `static/index.html` `#s7`: heading, button label "Generate worksheet", `?v=` cache-bust bump.
- `static/styles.css`: the `.incident-*` block and the `@media print` report rules only.
- `tests/incident_report_check.cjs`, `tests/e2e/incident-report.spec.mjs`, new fixtures under `tests/fixtures/report_runs/` if needed. The two existing one-A4-page e2e tests are replaced by multipage tests (approved scope change, not weakening).
- `CONTRACT.md` final paragraph and README: Devin supplies text, Codex integrates.

## Worksheet content (in order)
1. Header: "Historical IRS worksheet — 2012 reference" and a fixed source line from `source`: DCLG, *IRS Questions and Lists v1.6, from April 2012*, published July 2012, Crown copyright/OGL (logos excluded), PDF SHA-256, and the v1-0p/v1-0n discrepancy stated as-is. Fixed status line: "Historical reference worksheet. Not the current FaRDaP form, not a validated or complete IRS record, not an official submission." No run-derived value appears in the header except the worksheet generation time, labelled as generation time.
2. Nine sections in JSON order, with the section name as h4. Each of the 158 questions renders the ID verbatim (including `4.2*`, `4.3a/b`, `6.14a & b`), the label verbatim via `textContent`, the source page as "p. {printed}", and an **empty answer area**: a bordered box with no text node, no placeholder or pre-checked control, and `role="group"` + `aria-label="Answer {id}"`. There are no enums, conditions, required markers or subfield expansion.
3. Annex "Video evidence from Scene2Real run — machine observations, not worksheet answers", on a new page:
   - Reference: run id (labelled "Scene2Real run", not an incident number), clip/view basenames, kind, label, cached/some cached/not cached/"cache status unknown", and synthetic when the label matches, otherwise "provenance not established". Also the top-level `model_id`/`prompt_id`.
   - Per observation `id`: description, location_description, burning_object, smoke_description, nearby_objects, and `timestamps_s` labelled "clip-relative seconds". Operator-excluded sightings are tagged "excluded by operator: {reason}" (ambiguity A2).
   - Excluded from the annex: confirmed zones/slots, template coordinates, `suggested_zone`, association candidates, YOLO objects, plan, skill and metrics.
4. Footer on every printed page: worksheet title, "Historical reference — not FaRDaP", "page X of Y" if feasible (A5).

Rules: no run value ever enters an answer area. The annex keeps its existing empty labels ("No fire observations recorded") because they are not answers. All text goes through `textContent`/`scrub`, basenames come from `safeFilename`, and `local_path`, `s3_uri`, raw payloads and secrets are never read.

## Integrity (retain + harden)
- `fingerprint()` adds `clip_ref`, `video_refs` (minus `local_path`/`s3_uri`), `excluded`, `error.message`, `model_id`, `prompt_id`. Simulation fields stay in the fingerprint harmlessly, which means a run/reset still invalidates the worksheet.
- `act('analyse'|'confirm'|'reset')` drops the worksheet immediately (existing). `setRun` drops it on a run switch (existing). The `doReport` stale-run branch now sets `S.report = null` itself. `retainReport` still requires `runId` equality. Print only when `S.report` matches the current fingerprint.
- Generate gating is unchanged (`analysisReady`).

## Print and layout
Replace the fixed `height:297mm` two-column print grid with flowing single-column A4 using `@page{size:A4;margin:12mm}`, `break-inside:avoid` per question row, `break-after:avoid` on section headings, and annex `break-before:page`. Answer boxes are about 14mm minimum height, with no `overflow:hidden`, no truncation and no density shrinking. On screen it is a white sheet at `min(100%,210mm)`. On mobile (360px) ID/label stack above the answer box, with no horizontal scroll.

## Verification after approval (focused)
- `node tests/incident_report_check.cjs`:
  - the module deep-equals the research JSON; 9 sections and 158 IDs render in order with exact labels;
  - every answer area has empty `textContent` across all `r_report_*` fixtures;
  - no `0`/`No`/`unknown`/`N/A`/PASS/FAIL/plan/skill/zone/coordinate text inside answer areas or anywhere outside the annex;
  - excluded sightings are tagged; escaping/XSS fixture is inert; secrets/paths are redacted;
  - fingerprint drops on label/video_refs/excluded/error.message changes; cross-run identical text is still rejected.
- `tests/frontend_evidence_check.cjs` still passes.
- Playwright `tests/e2e/incident-report.spec.mjs`:
  - generate on ok/fail/partial/xss fixtures;
  - reset, reconfirm and run-switch clear the worksheet; a late response for run A while B is visible is discarded;
  - 360px and desktop screenshots show no horizontal overflow;
  - the A4 PDF has more than one page, its extracted text contains all 158 IDs and the annex title, and no answer box is clipped (`scrollHeight <= clientHeight`).
- Visual check of desktop, mobile and print against the approved mockups. Python/backend tests are not required (no backend change); run `pytest -q tests/test_pipeline.py` only to confirm untouched.

## Real ambiguities for Codex / user
- A1 Simulation: should it be omitted entirely (recommended), or kept in a separate labelled simulation annex? The brief excludes it only from "answers".
- A2 Excluded sightings in the annex: show them tagged with the operator reason (recommended, auditable), or omit them?
- A3 Workbench confirmation (operator zone grouping): omit (recommended; zones are template assumptions and risk being read as location), or include as annex-only?
- A4 Synthetic detection: the frontend sees only labels, while the SHA-based provenance in `clips/demo_cctv_provenance.json` is not served. Are label match + "provenance not established" acceptable, or may a static SHA list be copied into `static/`?
- A5 "Page X of Y" in browser print is unreliable without paged-media support. Is a running footer without totals acceptable?
- A6 The answer area is a uniform box per heading, including grouped IDs like `4.2*` that cover 4.2a–g in the source. Is one box per heading acceptable, given no subfield expansion is permitted?
- A7 Section 7 heading/nav text ("Incident summary") and the PAGES key `report`: rename the label only (recommended) and keep the route `#report`.
