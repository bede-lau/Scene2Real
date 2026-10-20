# Local historical IRS worksheet validation

19 October 2026. Local checkout `/Users/bedelau/Scene2Real-sim/scene2real-1`. No commit, push or deploy. No provider calls or credentials added. Production checkout `/Users/bedelau/Desktop/Scene2Real` remains clean on main; all 19 local backend files match the preimplementation manifest.

## Automated evidence

- Python suite: 179 passed; two existing FastAPI `on_event` deprecation warnings.
- `tests/incident_report_check.cjs`: passed. Exact source inventory equality, immutable snapshots, invalidation, sanitization, single-view provenance, mixed cache flags and ordinary prose preservation.
- `tests/frontend_evidence_check.cjs`: passed. Existing evidence/overlay/confirmation contract preserved. Obsolete hardcoded cache version assertion replaced with matching nonempty asset-version checks.
- `tests/frontend_operations_check.cjs`: passed. Existing polling and recovery preserved.
- Chromium `incident-report.spec.mjs`: 15/15 passed (20.8 s). Complete-success, failed and partial runs; 158 blank answers; evidence separation; XSS escaping; private paths; single-view context/provenance; run switches; reset/reconfirmation; stale/failed print checks; late A/B generation and print/navigation races; native-print guard; 320/390/1440 widths; complete A4 PDF text.
- After final print-only CSS correction, the A4/responsive/PDF test passed again (1/1, 3.4 s).

Used existing bundled Node and `/Users/bedelau/Scene2Real-sim/.venv/bin/python`. Isolated fixture server ran on 8097 without inference. Real-run capture used read-only run retrieval on 8096.

## Review corrections

Cursor and Codex reviews identified private path variants, single-view grounding attribution, unknown cache flags, missing scene context, blank exclusion reasons and replacement of a print-expiry timer. All were corrected. Exclusions remain visible without an invented reason. Provider raw responses are not copied. The old expiry timer is cleared before replacement. Visual review found dark page margins inherited from the app colour scheme; explicit light print styling corrected this.

## Real selected run and visual review

Run `r_20261017_182916_abc3`: 158 questions, 158 blank answer areas, zero page errors (`real-run-capture.json`). Generated in the visible in-app browser and left open at `http://127.0.0.1:8096/?run=r_20261017_182916_abc3#report`.

`desktop.png`, `mobile.png` and `evidence-annex.png` show the local preview. `output/pdf/historical-irs-worksheet.pdf` has 13 A4 pages. All page renders were reviewed together; pages 1, 10 and 13 were also inspected at readable size. Final output has white margins, readable text, complete rows and a separate evidence annex. No clipped text or blank trailing page observed. Visual evidence is in `print/contact-sheet.png` and `print/page-*.png`; file digests are in `final-hashes.json`.

## Limits

Approved historical heading-only IRS reference, not current FaRDaP or a validated submission. Not all historical input controls, options and validation rules are reconstructed. Current run data does not establish historical incident answers; all remain blank. Machine observations stay in the annex and simulation outcomes do not become real-world outcomes. PDF tested in Chromium; no cross-browser certification or live robot validation claimed.

## Superseding local autofill revision

The latest direct user requests replace the v4 title, blank-only rendering and evidence annex. Current title is IRS WORKSHEET, requested disclaimer/XML-version text and Video evidence section are absent. Cursor Grok agents implemented and reviewed the revision; focused Node and 17/17 browser tests passed after the final text correction. Codex reran report/evidence/operations Node checks and diff whitespace checks, verified all 19 backend hashes unchanged and production clean on main, then generated the real local run in the in-app browser. It has 158 questions, two explicitly unverified vision drafts and 156 blank answers, with zero annexes. Screenshots autofill-header.png and autofill-fields.png were captured through the browser and visually checked. Live facts and hashes are in autofill-live-verification.json. Earlier 13-page PDF and screenshots in this folder reflect the prior v4 delivery, not the current form. No commit, push, deploy or new inference.
