# Devin implementation plan — England official incident-report adapter

Date: 2026-10-19. Owner: Devin (primary implementer once gates clear). Status: **preparation only**. No app, test or workflow source was edited; no tests were run; nothing was committed, pushed, deployed or sent. `runs/`, footage, `.env` and team config were not read.

Companion files (Devin-owned): `field-mapping-proposal.csv` (source whitelist), `specification-request.md` (DRAFT enquiry, not sent). Inputs read: `AGENTS.md`, `CONTRACT.md`, `static/incident_report.js`, `static/app.js` (report integration, `act`, `setRun`, operation restore), `scene2real/pipeline.py`, `records.py`, `operations.py`, `mobile.py`, `planner.py`, `clips/*provenance*.json`, `.prd-to-production/brief.md` (v3, unapproved), `inventory.json`, `checkpoint.md`, `fire-reporting/research/*`, `fire-reporting/cursor-review.md`.

## 0. Gates and what is blocked

| Gate | Needed | State |
|---|---|---|
| G0 Source | Pinned official artifact(s): active version, dictionary, enums, conditional/required/repeat rules, output template (if any), validation pack | **Missing.** User has no access. Request drafted, not sent. |
| G1 Brief | Fresh compact brief revision that cites the G0 artifact, then explicit user approval | v3 proposed, **unapproved**; must be revised after G0 (field set, output form) and re-approved |
| G2 Mockups | Desktop + mobile images for every inventoried page/tab of the revised brief, explicit approval | Not started; cannot depict official fields before G0 |
| G3 Build | `workflow.py check --stage build` passes | Blocked by G0–G2 |

Nothing below authorises implementation. Where a step is "schema-independent" it is still held until G1/G2 unless the user separately approves it as ordinary maintenance (see §9, decision D7).

## 1. Architecture: additive, version-pinned adapter

The Cosmos → grounding → association → confirm → planner → sim pipeline and its run object are **read-only inputs**. The adapter reads a run, never writes `run.json`, never calls a model, never submits externally.

```
run.json (unchanged)
   │  whitelist extraction (field-mapping-proposal.csv)
   ▼
EvidenceSnapshot ──source_fingerprint──┐
   │ suggestions (class 2–8, labelled)  │
   ▼                                    ▼
SchemaPack (pinned, hashed) ──► OfficialDraft (persisted, revisioned, per-field provenance)
                                         │ rule engine (pack rules only)
                                         ▼
                                  OutputRenderer (pack template / format) ──► export (freshness-checked)
```

Boundaries:

1. **SchemaPack loader** (`scene2real/official_schema.py`). Loads `official_schema/<pack_id>/manifest.json` + the supplied artifacts unchanged. Manifest records publisher, service applicability, version, valid-from/to (which side of the v2 transition), source URL/route, licence/reuse terms, received date, SHA-256 per file. Format parsers are written **after** G0 against the real format (XSD, JSON Schema, CSV/XLSX dictionary, API spec or PDF-only). Output is a normalised in-memory model: sections → questions (key, label, type, unit, order) → enums (code, label, order) → repeat groups (min/max) → rules (required/conditional/derived/hidden) each carrying a citation back to the artifact location. Hash mismatch or missing pack ⇒ adapter disabled, no official form rendered.
2. **Evidence whitelist** (`scene2real/official_evidence.py`). Encodes `field-mapping-proposal.csv` as code: allowed JSON paths, provenance class, citation fields. Anything not whitelisted (paths, `s3_uri`, raw provider payloads, telemetry) is unreachable, rather than regex-scrubbed after the fact. Produces `EvidenceSnapshot` + `source_fingerprint` (SHA-256 over canonical JSON of every whitelisted path, `run_id`, `state`, `error`). Synthetic status from `clip_ref/video_refs[].sha256` matched against `clips/demo_cctv_provenance.json` (`all_videos_sha256`, `sets[].clips[].registered_sha256`); no match ⇒ "provenance unknown", never "real".
3. **Suggestion binding** (`official_evidence.py`, table `SUGGESTION_BINDINGS`). Maps a whitelisted source to a pinned field key. **Empty until G0.** Each binding must cite the pack definition it relies on and be approved in the revised brief. Free text is never auto-converted to a code.
4. **OfficialDraft store** (`scene2real/official_draft.py`). `runs/<run_id>/official_draft.json` (already git-ignored under `runs/`), atomic tmp+replace, per-run file lock (same `fcntl` pattern as `operations.py`, own lock file). Not archived to VAST by default (D4).
5. **Rule engine** (`scene2real/official_rules.py`). Evaluates only pack rules. If rules are prose-only, each is hand-encoded with its citation and covered by a validation-pack case; unencodable rules are surfaced as "manual check required", never assumed satisfied.
6. **OutputRenderer** (`scene2real/official_output.py` + `static/official_form.css`). Renders from the pack's template/format exactly (§4).
7. **HTTP routes** (`scene2real/app.py`, additive only):
   - `GET /api/official-schema` → active pack metadata or `{available:false, reason}`.
   - `GET /api/runs/{id}/official-draft` → draft + `current_source_fingerprint`, `stale`, `operation_active`, validation result.
   - `POST /api/runs/{id}/official-draft` → create from current snapshot (409 if analysis not ready or operation active).
   - `PATCH /api/runs/{id}/official-draft/fields/{key}` with `If-Match: <draft_revision>` and expected `source_fingerprint` → enter/accept/clear one field; 409 on mismatch.
   - `GET /api/runs/{id}/official-draft/export?format=<pack format>&revision=<n>&fingerprint=<h>` → server-rendered output; 409 if revision, fingerprint, pack hash or run_id mismatch, or an operation is active.
8. **Frontend** (`static/official_form.js`, `static/official_form.css`, small additive hooks in `static/app.js` + `static/index.html`). The existing `#report` demo sheet (`incident_report.js`) stays, with its banner and footer; the official draft is a separate panel/tab per the approved mockups.

## 2. Value model: suggestion vs officer value; blank vs Unknown/N/A/No/0

Per field in `official_draft.json`:

```json
{"key": "<pinned field key>", "pack_id": "...",
 "state": "unset | entered | accepted | cleared_stale",
 "value": null | "<schema-typed value or code>",
 "suggestion_ref": null | {"s2r_source_id": "S2R-OBS-DESC", "path": "observations.fire_sources[2].description",
                           "source_value": "...", "class": 2, "model_id": "...", "prompt_id": "...",
                           "cached": true|false|"unknown", "synthetic": true|false|"unknown"},
 "basis_fingerprint": "<source_fingerprint at accept time>",
 "entered_at": "iso8601", "entered_by": null | "<operator-typed name, unverified>",
 "revision": 7}
```

- Only `entered`/`accepted` values ever print in an official field. `accepted` = officer chose a suggestion (value may be edited before accept; original kept in `suggestion_ref.source_value`). `entered` = officer typed/selected with no suggestion.
- `unset` renders as an empty field. The app never writes the pack's "Not known", "Not applicable", "No", "None" or `0` codes on its own. Those are ordinary enum values the officer may select **only if the pack offers them for that field**.
- **Rule-hidden** (field not applicable because a pack condition hides it) is a computed rendering state, not a stored value and not an N/A code. Output follows the template's convention for hidden questions (omit vs print blank) as the pack specifies.
- Demo-sheet wording ("Not confirmed", "Not available", "Not run / not measured", "unknown", PASS/FAIL) never becomes a value.
- Measured simulation zeros/false (`unintended_collision_count: 0`, `best_valid_exposure_s: 0.0`, `suppressed: false`) stay in the simulation appendix (§4) and have no binding.
- Validity is a separate computed status: `draft-incomplete` (any pack-required-after-conditions field unset, or manual-check rules pending), `draft-complete-unverified` (all required set; still not an accepted official submission). There is no "submitted" status; external submission is out of scope. `report.complete` from the demo sheet is never consulted.

Fields with **no bindings until evidence exists** (left `unset` regardless of run content): any incident/call/mobilisation/attendance/stop/closure date-time (run `created_at`, clip `timestamps_s`, sim `duration_s`/`suppressed_at_s`, `generatedAt` are different clocks); address/location/grid/origin (`template_position_m`, `zone`, `suggested_zone`, `location_description` are not); cause/motive/ignition source; casualties/rescues/fatalities (YOLO `person` ≠ casualty; no detection ≠ zero); damage/area/spread; resources/appliances/personnel/dispatch; FRS actions, methods, extinguishing media, outcome (all simulation is class 7); number of fires (sightings, candidates and targets are not fire counts).

## 3. Snapshot freshness, persistence and races

Today's gaps (verified in code, consistent with Cursor findings 8–9):
- `fingerprint()` in `incident_report.js` omits `clip_ref`, `video_refs`, `excluded`, `error.message`, `created_at`, `model_id`/`prompt_id`, association payloads; `referenceBlock` renders some of these from a frozen snapshot.
- `doReport` returns on run switch without nulling `S.report` itself (relies on `setRun`).
- Print uses the in-memory snapshot; server-side background operations (`/api/runs/{id}/operations`, restored on reload at `app.js` ~L859) can change the run in another tab/process without this tab noticing.
- `error.stage === "export"` already means simulation-video export in `pipeline.py`; the official export must not reuse that stage name.

Design:
1. **Server-computed fingerprint** over the whitelist only (§1.2). Clients never compute the official fingerprint. Draft stores `created_fingerprint`; each accepted field stores `basis_fingerprint`.
2. **Staleness.** `GET draft` compares to the current run. On mismatch: draft `stale: true`; every `accepted` field whose source path changed or disappeared → `cleared_stale` (value retained for audit, not printed); reset/reanalysis/reconfirmation clear all suggestion-derived accepted values. `entered` fields without suggestion: D3 decides retain-with-re-review vs clear.
3. **Operation lock-out.** If `operation.json` is `pending|running`, or a synchronous analyse/confirm/scene/run/reset is in flight, draft is read-only and export returns 409.
4. **Optimistic concurrency.** `draft_revision` integer; every PATCH carries `If-Match`; 409 returns the current draft. Two tabs editing the same field cannot silently overwrite.
5. **Cross-run.** Draft path keyed by `run_id`; every response carries `run_id`; client discards any response whose `run_id` ≠ visible run and **nulls its own official state in that branch** (not relying on `setRun`). A request token (`S.officialToken`) increments on run switch; late responses with an old token are dropped.
6. **Export.** Export is rendered server-side from persisted draft + current run at request time. Client sends `revision` + `fingerprint`; mismatch ⇒ 409 and the UI forces reload. Browser printing of the official form uses the export response, re-fetched immediately before `window.print()`; never the in-memory DOM from an earlier generation.
7. **Schema pin changes.** A draft stays pinned to its `pack_id`. If the active pack changes, the old draft is read-only with "pinned to superseded version"; no silent migration.
8. **Demo sheet hardening** (schema-independent, D7): extend `fingerprint()` to all displayed fields; null `S.report` in the `doReport` run-switch branch; label missing cache flags "cache status unknown". Existing demo tests keep passing; one-page A4 test stays for the demo sheet only.

## 4. Output fidelity

- Source of truth is the pack's template/format. Labels, order, codes, units, date/time formats, repeat groups and conditional visibility come from the pack; no Scene2Real headings inside the official form.
- **No page limit.** Repeating sections render every instance (e.g. all persons/resources/fires the template permits); nothing is truncated, ellipsised or `overflow:hidden`. Multipage print with CSS paged media: running header (draft id, run id, pack id/version, `DRAFT — NOT AN ACCEPTED OFFICIAL SUBMISSION` unless the pack defines otherwise), page X of Y, `break-inside: avoid` for single questions, repeat-group headers repeated across page breaks.
- Codes print as the template specifies (code, label, or both). Unset fields print as the template's empty field.
- Machine formats (XML/JSON per XSD/JSON Schema) are produced only if the pack defines one; validated against the schema before download; unset optional elements omitted per schema, required-but-unset ⇒ export allowed only as a clearly named draft file and never claimed valid.
- If the pack has **no universal printable template** (possible: research establishes only private developer resources and service-specific systems), the printable output is a "draft data-entry worksheet" using exact pack labels/codes/order, titled as a worksheet, not as the official form. A service-specific layout is implemented only from that service's supplied template.
- **Simulation appendix** (optional, D6): separate trailing section titled as Scene2Real simulation, outside the official form, with plan text, skill, metrics and rule.
- **Evidence appendix**: suggestions actually accepted, with source class, clip basename, view, clip-relative times, model/prompt, cached/synthetic flags. Never `local_path`, `s3_uri`, raw payloads, credentials. Untrusted text via `textContent` (client) / autoescaping (server).

## 5. File ownership (when build is authorised)

| Path | Owner | Change |
|---|---|---|
| `official_schema/<pack_id>/` | Devin (artifacts supplied by user/MHCLG/FRS, stored unchanged) | new |
| `scene2real/official_schema.py`, `official_evidence.py`, `official_draft.py`, `official_rules.py`, `official_output.py` | Devin | new |
| `scene2real/app.py` | Devin, additive routes only; coordinate with backend owner | edit |
| `static/official_form.js`, `static/official_form.css` | Devin | new |
| `static/app.js`, `static/index.html` | Devin, minimal hooks; coordinate with frontend owner / concurrent edits | edit |
| `static/incident_report.js` | Devin, D7 hardening only | edit |
| `tests/test_official_schema.py`, `test_official_draft.py`, `test_official_output.py`, `tests/official_form_check.cjs`, `tests/e2e/official-form.spec.mjs`, `tests/fixtures/official/` | Devin | new |
| `scene2real/pipeline.py`, `cosmos.py`, `grounding.py`, `matching.py`, `planner.py`, `sim.py`, `mobile.py`, `scene.py`, `records.py`, `operations.py` | **not touched** | — |
| `.prd-to-production/brief.md`, `inventory.json`, `checkpoint.md`, approvals | Codex | — |
| `fire-reporting/cursor-review.md` | Cursor | — |
| `CONTRACT.md`, `README.md` | orchestrator; Devin supplies text for new routes/draft object | — |

Test fixtures: only the supplied validation pack counts as authoritative. Rule-engine unit tests may use a tiny synthetic pack under `tests/fixtures/official/TEST-ONLY-pack/` whose manifest says `test_only: true`; the loader refuses `test_only` packs outside tests. It must not imitate real question names or IRS questions.

## 6. Acceptance cases

Schema pin
- AC-01 No pack installed ⇒ `GET /api/official-schema` `{available:false}`; no official form/tab content, no substitute question list; demo sheet unaffected.
- AC-02 Pack file hash ≠ manifest ⇒ adapter disabled with reason.
- AC-03 Labels, codes, option order, units, sections and repeat limits rendered equal the pack (golden comparison against pack-derived expectation, every field).
- AC-04 Every pack validation-pack case yields the pack's expected required/conditional/hidden/valid result.
- AC-05 `test_only` pack is rejected in non-test runtime.

Values
- AC-06 New draft on any fixture run (`r_report_*`) has every field `unset`; nothing auto-filled.
- AC-07 Accepting a suggestion stores officer value and `suggestion_ref` separately; editing value before accept keeps original `source_value`.
- AC-08 Unset prints blank; no "unknown", "No", "None", "0" or N/A code appears unless the officer selected that pack option.
- AC-09 A run with `unintended_collision_count: 0`, `suppressed:false`, `best_valid_exposure_s:0` produces no value in any official field.
- AC-10 `created_at`, `timestamps_s`, `duration_s`, `suppressed_at_s`, `generatedAt` never appear as suggestions for any time field.
- AC-11 `template_position_m`, `zone`, `suggested_zone` never appear as suggestions for any location field.
- AC-12 Excluded sightings never appear as suggestions; sighting/candidate/target counts never suggested as fire counts.
- AC-13 YOLO `person` detections never suggested for casualty/rescue fields; empty detections never become zero.
- AC-14 Required-after-conditions unset ⇒ `draft-incomplete`; all set ⇒ `draft-complete-unverified`; no status claims acceptance/submission; demo `complete` ignored.

Provenance
- AC-15 Demo-set clips (sha in provenance file) marked synthetic on every quoted suggestion even when label lacks "synthetic"; unknown uploads marked "provenance unknown".
- AC-16 Missing cache flags ⇒ "cache status unknown"; partial ⇒ "some cached".
- AC-17 Export and DOM contain no `s3://`, `runs/`, absolute paths, bearer/keys, raw payloads (`r_report_xss`-style fixtures + injected secrets).
- AC-18 Script/HTML in descriptions/filenames rendered inert in form, export and print.

Freshness and races
- AC-19 Reanalyse/reconfirm/reset ⇒ draft `stale`, suggestion-derived accepted values `cleared_stale`, export 409 until reviewed.
- AC-20 Change confined to `clip_ref.label`, `video_refs`, `excluded`, `error.message` also marks stale (official + demo).
- AC-21 Background operation active ⇒ draft read-only, export 409.
- AC-22 Two concurrent PATCHes with same `If-Match` ⇒ one 200, one 409; no lost update.
- AC-23 Run A draft request in flight, user switches to B ⇒ A response discarded, official state nulled in that branch, B shows only B.
- AC-24 Export with old revision/fingerprint ⇒ 409; print uses freshly fetched export.
- AC-25 Identical observation text on two runs ⇒ drafts and exports never cross (`run_id` asserted).
- AC-26 Pack superseded ⇒ old draft read-only, labelled with its pinned version.

Output
- AC-27 Maximal fixture (12 targets, max repeat instances permitted by pack, long free text) prints all content across pages; no clipping (overflow check on every field box), headers/page numbers on each page.
- AC-28 Machine export (if pack defines one) validates against pack schema when complete; draft file name/marking when incomplete.
- AC-29 Simulation appendix (if D6 = include) is outside the official form, titled as simulation; absent from machine export.

Preservation
- AC-30 Existing suites (`pytest`, `tests/incident_report_check.cjs`, `tests/frontend_evidence_check.cjs`, `tests/e2e/incident-report.spec.mjs` incl. one-page demo A4) still pass; `run.json` byte-identical before/after draft create/edit/export; no model or network call from adapter code paths.

## 7. Sequence after gates

1. G0: receive artifacts → store unchanged under `official_schema/<pack_id>/` with manifest → write a source note (format, version, applicability, printable-template yes/no, licence).
2. Revise `field-mapping-proposal.csv`: replace `UNASSIGNED` only where a pack definition and a whitelisted source genuinely agree; everything else stays unbound. Hand to Codex for brief revision; user approval (G1).
3. Mockups of official form, draft review panel, stale/incomplete states, multipage print, desktop+mobile (G2).
4. Build order: loader + manifest checks → whitelist/fingerprint → draft store + routes + concurrency → rule engine against validation pack → renderer/export → frontend panel → first-slice checkpoint (one section incl. one repeat group and one conditional, real PATCH with delayed response) → replicate → full acceptance → evidence.

## 8. Review of Cursor's findings

Agree (and verified in code): fingerprint gaps; `doReport` cross-run branch not self-clearing; `excluded`, `association_provenance`, `suggested_zone` not rendered; cache-flag silence; synthetic detection by regex only; simulation/clock/template separation; scrub coverage.

Disagree or correct:
- **Overstated source claim.** Cursor states the live question set, codes and conditional rules "are in" the private HO-FaRDaP resources. Public sources only establish that a private developer-resources repository exists. They do not establish its contents, that it contains business rules in machine-readable form, or that an exact universal printable form exists anywhere. The plan treats the printable template as an open question (§4).
- **Publisher.** Cursor says "Home Office FaRDaP artifact". The research pack attributes FaRDaP to MHCLG (org page title "MHCLG - Fire & Rescue Data Platform"; only the URL slug carries an `HO-` prefix, whose origin is not established). Pin by the publisher named on the supplied artifact, not by org slug.
- **"Submit stays unavailable" / "valid submission possible only when…".** External submission is out of scope in the brief; there should be no submit state at all, only `draft-incomplete` / `draft-complete-unverified`.
- **Internal tension.** Cursor says without the artifact the official form "is not rendered", and also that a "blank draft … may be shown and printed only as a draft". Without a pack there is no official draft to print; only the demo sheet exists.
- **Class 1 only from acceptance.** Officer-typed values with no machine suggestion (`entered`) must also be class 1; most required official fields will have no suggestion at all.
- **Synthetic flag via provenance file.** Correct direction, but runs do not reference that file; matching must be by `sha256`, and non-matching uploads are "unknown", not "real".
- **Missed:** server-side background operations race; `error.stage "export"` name collision; officer identity is unverifiable without auth (D2); personal data in drafts (D4).

## 9. Open decisions for the user / Codex brief

- D1 Which FRS/service and version is the target (national v1, v2, or a service bespoke system)? Determines pack.
- D2 Officer identity without authentication: record optional operator-typed name labelled "unverified", or nothing?
- D3 On evidence change, retain officer-`entered` (non-suggestion) values flagged for re-review, or clear them?
- D4 Drafts may hold personal data (names, addresses, casualties). Keep local-only (default, not archived to VAST S3), retention period, and whether to allow entry of such fields at all in a demo deployment.
- D5 Persist drafts server-side (recommended; required for races/audit) vs browser-only.
- D6 Include a simulation appendix in printed output, or keep simulation only in the workbench?
- D7 Approve the schema-independent demo-sheet hardening (§3.8) as maintenance now, or hold it for G3?
