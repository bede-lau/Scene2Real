# Independent review — England official-form adapter

Date: 2026-10-19. Read-only audit of the uncommitted workbench incident summary. No application files were edited, no tests were run, and no `.env`, team config, `runs/`, or customer footage was opened.

This review does not approve a brief or a mockup set. It does not list official questions, codes, or conditional rules. No current official schema is in this repository, and none is invented here.

## Decision

An additive official-form adapter can be specified only after a versioned Home Office FaRDaP artifact is supplied. Until then the workbench sheet stays a demonstration summary. `report.complete === true` is not a valid official submission. A blank draft is not one either.

Implementation waits for a source-grounded brief and for mockup approval under `.prd-to-production/`. This file is not that brief.

## Source premises

England’s national fire incident record is FaRDaP, which replaces IRS. FaRDaP v2 is in transition in autumn/winter 2026. The live question set, codes, and conditional rules are in the private HO-FaRDaP developer resources. The public 2012 IRS data dictionary is historical. It is not evidence that a form is compliant, and it must not be used to name, order, or code fields.

The effective artifact has to be pinned at build time by publisher, version, and the dates it is valid. A sheet pinned to one side of the v2 transition must not be presented as the other. If that artifact is absent, the official form is unavailable and every official field stays blank.

## What was audited

| Surface | Role |
|---|---|
| `static/incident_report.js` | Builds and renders the one-page sheet from a run object already stored by the pipeline. No model call. |
| `static/app.js` (`renderReport`, `doReport`, `retainReport` call sites, `setRun`) | Generates the sheet from `GET /api/runs/{id}`, keeps it in memory, prints it. |
| `static/index.html` `#s7` | “Incident summary”, Generate, Print / Save as PDF. No eighth stage. |
| `CONTRACT.md` run object and the v2 report paragraph | Persisted run shape. The sheet adds no API route and no stored report object. |
| `scene2real/pipeline.py` confirmation, `scene2real/mobile.py` metrics | Fields the sheet must not promote into official values. |

The node check in `tests/incident_report_check.cjs` was read as the current behavioural contract. It was not executed.

## What the sheet is

`buildReport` freezes a view with: run id, generation time, clip filename / kind / label, model observations, operator zone confirmation, a plan when `planPermitted` allows it, and simulator metrics. The banner is `DRAFT · DEMONSTRATION`. The footer states that cause, casualties, and real-world response outcome are unverified and that the sheet is not an official incident submission.

`report.complete` is true only when operator confirmation, a permitted plan, and a boolean `metrics.success` are all present. An analysed run with no confirmation still renders. Empty slots use the workbench phrases “Not confirmed”, “Not available”, “Not run / not measured”, and “unknown”. Those phrases are labels on the demonstration sheet. They are not official answers.

Generate stays off when `analysisReady` is false: no run, state `uploaded`, missing analysis or `observations.fire_sources`, state `needs_review`, or `failed` with `error.stage === "analyse"`.

## Provenance classes

Any later adapter has to keep these classes in separate fields. A value may be copied into an official answer only from class 1, and only when the pinned schema defines that answer.

| Class | Examples in this repo | Official use |
|---|---|---|
| 1. Officer-accepted official value | Does not exist yet. Workbench zone/slot confirmation is not this class. | The only class that may fill a FaRDaP answer. |
| 2. Model suggestion | Cosmos/Astra descriptions, `suggested_zone`, association candidates, planner `instruction.text` | Show beside the form as a suggestion. Never store as the official value. |
| 3. Workbench confirmation | `confirmed_targets` / legacy `confirmed_target`: zone, slot, members, `association_provenance` | Records what the operator did in Scene2Real. Not an official code. |
| 4. Authored template | `template_position_m`, `position_provenance` “template-assumed …” | Not a surveyed location, address, or map reference. |
| 5. Clip-relative sample | `timestamps_s` on fire observations | Seconds from the start of the clip. |
| 6. Report clock | `generatedAt`; run `created_at` | When the sheet was generated, or when the run record was created. |
| 7. Simulation | `instruction` + `skill` (`aim_spray_demo`, `mobile_suppress_demo`); `metrics.success`, angle, collisions, duration; mobile `suppressed`, `suppressed_at_s`, `suppressed_count`, `best_valid_exposure_s` | Scripted rehearsal. Not an FRS action, method, or outcome. |
| 8. Evidence status | `analysis.cached`, per-view cached flags, filename/label match `/synthetic/i`, clip `sha256`, `clips/demo_cctv_provenance.json` | Must travel with any quoted observation. |
| 9. Unsupported | Cause, casualties, stop message, appliance times, and any question the pinned schema asks that this run does not answer | Blank. |

Sightings (`F1`, `V1:A1`) are not a count of physical fires. Confirmed targets (`T1`…) are groups of sightings plus an authored zone. Association candidates are proposals. None of those lengths is an official number of fires.

## Findings

1. **No official schema is available to implement.** The sheet’s headings (“Observed incident”, “Warehouse zone — operator confirmed”, “Proposed / simulation only”, “Simulation result”) are workbench headings. Copying them, or copying 2012 IRS questions, into a “FaRDaP” layout would present a historical or invented form as current. v2’s transition window means the correct version cannot be guessed from the date of this review.

2. **Demo completeness is not a valid submission.** A partial sheet (observations only) and a `complete` sheet (confirmation + plan + sim pass/fail) are both drafts. Mandatory official fields are defined only by the supplied schema version and its conditional rules. The form cannot be submittable while that artifact is missing.

3. **Blank must stay blank.** The run contract stores unobserved values as `null` (`cause`, `scale`, `depth_m`). The sheet omits empty narrative and, when `unintended_collision_count` is absent, prints “unknown” rather than `0`. The mobile simulator still initialises `suppressed` to false and `best_valid_exposure_s` to `0.0` as accounting inside the rehearsal. A measured sim zero is still class 7. It must not be written into casualties, appliances, fatalities, or “no fire”. The words “No”, “None”, “unknown”, and “Not confirmed” must not be sent as coded official answers.

4. **Model text is already on the same page as operator confirmation.** `observationBlock` lists every `observations.fire_sources` entry, including sightings the operator may later exclude. Exclusion reasons live on `run.excluded` and are not rendered. `suggested_zone` is stored on the observation and is not rendered; it must not reappear as the official location. `association_provenance` can read “operator-authored grouping; cross-camera identity is unverified” and is not rendered, so a confirmed zone line looks equally certain for a single-view sighting, a supported proposal, and an unverified group. `confirmed_targets[].image_evidence` copies the model sighting onto the operator record. The planner instruction is model text. Official answers need a separate accept action per field. Accepting a zone in the workbench does not accept an official code.

5. **Clip time is not incident time.** The sheet labels samples “clip-relative time” and formats `generatedAt` as “Report generation time” in `Europe/London`. The current check expects the phrase “Incident time” to be absent. `created_at`, `timestamps_s`, `metrics.duration_s`, and `suppressed_at_s` are different clocks. None of them is call time, incident date/time, or time to stop.

6. **Simulation must not be reported as FRS action or outcome.** The plan renders only for `scene_ready`, `completed`, or `failed` with `error.stage` of `run` or `export`, under “Proposed / simulation only”. A `blocked` plan-stage run keeps `instruction.text` on the run and the sheet hides it. Skills are `aim_spray_demo` and `mobile_suppress_demo`. `metrics.success` prints `true · PASS` or `false · FAIL` against a simulation rule. The mobile rule string says “scripted demo proxy”. The metrics page, which the sheet does not copy, already says “Fires suppressed” and “Yes”/“No” from that exposure proxy. Reset clears metrics and keeps the plan; the old PASS has to disappear. A failed run must not show another run’s PASS.

7. **Cached and synthetic status is easy to drop.** `cacheLabel` prints “cached”, “some cached”, or “not cached” only when boolean flags exist. With no flags it prints nothing, which a reader can take as fresh evidence. “synthetic” is added only when the filename or clip label matches `/synthetic/i`. Clip `sha256`, top-level `model_id` / `prompt_id`, and `clips/demo_cctv_provenance.json` are not on the sheet. The plan’s model id and prompt id are deliberately omitted (`gpt-6-astra`, `mobile_plan_r1_v2`). The README records that the team corpus has no warehouse-fire footage and that the CCTV fixtures are generated stills, locally animated and compressed. Quoted text from those clips has to keep class 8. Silence is not “live, uncached, real footage”.

8. **The snapshot fingerprint does not cover everything the sheet shows.** `fingerprint` includes `run_id`, `state`, `error.stage`, `analysis.cached`, each view’s id/state/cached, the whole `observations` object, both confirmation objects, `instruction`, `skill`, and `metrics`. It does not include `clip_ref`, `video_refs`, `excluded`, `scene`, association payloads, `error.message`, `created_at`, or top-level model/prompt ids. `referenceBlock` does render filename, kind, label, and extra view filenames from the frozen snapshot. A change confined to those fields leaves the previous sheet in place, and Print still prints it. Analyse, confirm, and reset pass an action that drops the sheet immediately, including when the server later fails. That drop is necessary and is not, by itself, a full stale-data check.

9. **Cross-run isolation depends on two clears, and one path does not clear.** `setRun` sets `S.report = null` when `run_id` changes. `retainReport` also returns null when the fingerprint differs or `report.runId` differs. `doReport` records `starting`, refetches, and if the visible run id is no longer `starting` it returns without writing. That return does not itself null the sheet. Isolation holds only because `setRun` already cleared it. A later edit that switches runs without clearing `S.report` would leave run A’s sheet mounted on run B. Identical observation text across two run ids must still fail `retainReport`, because `run_id` is part of the fingerprint.

10. **Secrets are scrubbed on the demo sheet and have to stay scrubbed.** `scrub` redacts S3 URIs, http(s) URLs, home/config-style paths, `runs/…`, bearer tokens, and key assignments. Rendered text is assigned with `textContent`. An official export must not reintroduce `local_path`, `s3_uri`, raw model payloads, or credentials, and must not add a stored submission of the demo sheet.

## Acceptance checklist

The adapter is additive. The demonstration sheet, its banner, and its footer stay. Official labels appear only from the pinned artifact, copied exactly, including version and conditional logic. No IRS 2012 question is added as a stand-in.

### Schema pin

- [ ] A supplied artifact identifies publisher, FaRDaP version, and the interval it is valid, including which side of the v2 transition.
- [ ] With that artifact missing, the official form is not rendered and not submittable. No substitute question list appears.
- [ ] Labels, codes, option order, and conditional rules match the artifact exactly. Nothing in this review is used as a field list.

### Blank draft versus valid submission

- [ ] A blank draft has no class-1 values. It may be shown and printed only as a draft. Submit stays unavailable.
- [ ] Workbench phrases (“Not confirmed”, “Not available”, “Not run / not measured”, “unknown”, “PASS”, “FAIL”) do not become official codes.
- [ ] Unsupported and null answers are empty. They are not `0`, `false`, “No”, “None”, or a dictionary code for none.
- [ ] A measured simulation `0` (collision count, exposure seconds, `suppressed: false`) stays in the simulation section and does not fill any official field.
- [ ] Valid submission is possible only when every mandatory field required by the pinned version, after that version’s conditional rules, holds a class-1 value. `report.complete` does not satisfy this.
- [ ] The demo sheet’s `complete` flag and the official form’s validity are stored and displayed as different states.

### Suggestions and officer values

- [ ] Model observations, `suggested_zone`, association candidates, and `instruction.text` render only as suggestions.
- [ ] A class-1 value is written only by an explicit accept of that official field, and the suggestion it came from remains distinguishable.
- [ ] Workbench zone, slot, and `association_provenance` stay on the workbench record. Unverified cross-camera groups are not shown as confirmed official identity.
- [ ] Excluded sightings do not become official fires. Sighting counts and candidate counts do not become an official fire count.
- [ ] `template_position_m` stays labelled as an authored template assumption. It is not written to an official location, address, or coordinate.

### Clocks

- [ ] `timestamps_s` appears only as clip-relative seconds.
- [ ] `generatedAt` appears only as report generation time.
- [ ] `created_at`, simulation `duration_s`, and `suppressed_at_s` are not copied into incident date/time, call time, or time to stop.
- [ ] Those official time fields stay blank unless a class-1 value was entered.

### Simulation and FRS outcomes

- [ ] Plan text and skill name stay under a simulation-only heading.
- [ ] A blocked plan (`error.stage` not `run` or `export`, state not `scene_ready` or `completed`) does not show its instruction as either a proposal or an official action.
- [ ] `metrics.success`, “Fires suppressed”, and per-target Yes/No stay simulation results. They are not methods used, pumps, personnel, stop, or extinguished.
- [ ] After reset, official outcome fields are blank and the previous PASS/FAIL is gone. A rebuilt demo sheet may still show the retained plan and an unmeasured outcome.
- [ ] After reconfirm, the previous plan and previous sim result are gone.
- [ ] Cause and casualty official fields stay blank. The demo footer’s unverified warning remains.

### Provenance

- [ ] Synthetic clips stay marked synthetic, including fixtures whose names do not match `/synthetic/i`, using `clips/demo_cctv_provenance.json` or an equivalent class-8 flag on the run.
- [ ] Cached and partly cached analysis stays marked. Missing cache flags stay “cache status unknown”, not unmarked live evidence.
- [ ] Clip `sha256` and the model/prompt ids that produced a quoted suggestion are available on the suggestion, not silently dropped.
- [ ] Paths, S3 URIs, raw provider payloads, and credentials never appear on the draft, the official form, or a print.

### Stale snapshot

- [ ] The official draft’s fingerprint includes every field the form or the demo sheet displays, including `clip_ref`, `video_refs`, `excluded`, and `error.message`. A change to any of them drops both the official draft and the demo sheet.
- [ ] Analyse, confirm, and reset drop both immediately, including when the request then fails.
- [ ] State, error stage, observations, confirmation, instruction, skill, metrics, and cache flags still drop the sheet, as they do now.
- [ ] Print is unavailable when the fingerprint or `run_id` does not match the visible run.
- [ ] A sheet generated before a clip-label or exclusion change cannot be printed after that change.

### Cross-run

- [ ] Switching from run A to run B clears A’s sheet before B is shown.
- [ ] An in-flight `doReport` response for A is discarded when B is visible. The discard nulls the sheet itself and does not depend on an earlier clear.
- [ ] `retainReport` returns null when `run_id` differs, even if observations and metrics are identical.
- [ ] A failed run’s sheet contains that run’s own result only. It does not contain another run’s narrative, zones, plan, or PASS.
- [ ] The visible run id and the sheet’s run id are equal whenever a sheet is on screen.

## Gate

Do not implement the adapter from this review. Next product step, when requested, is a compact brief that cites the supplied FaRDaP artifact and an inventory of the official-form screens, then mockups, then approval. Until those exist, `#report` remains the demonstration summary described in `CONTRACT.md`.
