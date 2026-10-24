# Worksheet autofill review

Read-only semantic review of deterministic autofill from a Scene2Real run onto the historical IRS worksheet. No autofill map exists in `static/incident_report.js`. `renderIncidentReport` creates an empty `.irs-answer` for every question (`static/incident_report.js` 115–122). This review judges the three proposed candidates against the report-run schema and IRS v1.6 meanings. It does not approve an in-progress implementation.

## 1. Gate

- `pwd`: `/Users/bedelau/Scene2Real-sim/scene2real-1`
- `git rev-parse --abbrev-ref HEAD`: `main`

## 2. Schema facts observed

`static/irs_2012_worksheet.js` has 9 sections and 158 unique question ids. Answers are not filled from the run.

Report fixtures: `tests/fixtures/report_runs/*/run.json` (nine runs). There is no local `r_20261017_182916_abc3` file in the repo. Keys below are the union of those fixtures. A key listed for one run is not present on every run.

Fire evidence lives on `observations.fire_sources[]`, not on a boolean or an incident category:

- `id` — examples: `F1`, `F9`, `V1:A1`, `V2:A1`
- `timestamps_s` — clip-relative seconds
- `description` — free text. Positive-looking examples: `r_report_ok` `V1:A1` `"burning packaging beside the right rack"`. Counterexample: `r_report_partial` `F9` `"smoke at the dock door"` is still a `fire_sources` entry
- `view_id` — present on multi-view fixtures (`V1`, `V2`, `V3`). Absent on several single-clip fixtures
- `location_description` — present only on some entries. `r_report_ok` `V1:A1`: `"beside the right rack"`. `r_report_dense` entries: `"Warehouse aisle position N, near shelving and stacked boxes."` `V1:A2` and `V2:A1` on `r_report_ok` have no `location_description`
- `burning_object` — sometimes present (`"cardboard"`, `"pallet wrap"`, `"Low pallet-like base; material unclear."`), often absent
- `smoke_description`, `nearby_objects` — present on `r_report_dense` only
- `bbox_normalized`, `suggested_zone` — present on `r_report_confirm` `F1` (`suggested_zone` `"right_rack"`)

`observations.cause` is JSON `null` where the key exists (`r_report_ok`, `r_report_dense`, `r_report_fail`, `r_report_partial`, `r_report_reset`, `r_report_confirm`). The key is absent on `r_report_blocked`, `r_report_uploaded`, and `r_report_xss`. `observations.unknowns` is `["cause","scale","depth"]` on `r_report_ok`, `r_report_dense`, and `r_report_reset`.

`observations.scene_description` is absent from all nine report fixtures. The renderer reads it (`static/incident_report.js` 83) and would show it only in the evidence annex. There is no property-type field anywhere on these runs.

Location-like fields that do exist are not addresses:

- `observations.fire_sources[].location_description` — image-relative text, as above
- `observations.fire_sources[].suggested_zone` — template zone name (`right_rack` on `r_report_confirm`)
- `confirmed_targets[].zone`, `slot`, `template_position_m`, `position_provenance` — `r_report_ok` target `T1` is `zone` `"right_rack"`, `slot` `1`, `position_provenance` `"template-assumed (wh_mobile_v1 zone slot)"`. `r_report_blocked` `confirmed_target.zone` is `"aisle_center"` with `position_provenance` present
- `clip_ref` / `video_refs[]` carry `kind`, `filename`, and sometimes `label`, `duration_s`, `sha256`, `view_id`, `local_path`, `s3_uri`. No address, postcode, or gazetteer field

Multi-camera identity lives in `video_refs[].view_id`, `analysis.views[].view_id`, `fire_sources[].view_id`, and `confirmed_targets[].members`:

- `r_report_ok` and `r_report_reset` (`response_mode` `"mobile"`): `T1.members` = `["V1:A1","V2:A1"]`, `T2.members` = `["V1:A2"]`. Three sightings, two workbench groups. `V2:A1.description` is `"same packaging seen from the east camera"`
- `r_report_dense`: 12 sightings, 12 targets, each `members` length 1, views `V1`–`V3`. Targets do not group the same physical fire across cameras
- Report fixtures do not include `association_provenance` on targets. `r_report_confirm` `observations.association_candidates` is `[]`

Exclusions: the key `excluded` is absent on all nine report fixtures. The renderer treats `run.excluded` as a list of `{id, reason}` and matches `excluded[].id` to `fire_sources[].id` (`static/incident_report.js` 62–73). `scene2real/pipeline.py` `confirm_targets` writes that same shape (each exclusion needs `id` and a non-empty `reason`). Do not invent an exclusion example from the fixtures; the key is simply not there.

Other run fields the sheet must not treat as IRS answers: `run_id`, `created_at`, `state`, `error`, `instruction` (`text`, `source`, …), `skill` (`name`, `target_id` / `target_ids`), `metrics` (`success`, `rule`, `duration_s`, angle errors, `unintended_collision_count`), `timings_s`, `telemetry`. Worksheet generation time is a client clock in `buildReport`, not a run incident time.

The Cosmos observation prompt (`scene2real/cosmos.py` 15–41) defines `location_description` as an image-relative position, requires `cause` null unless ignition is itself visible, and tells the model it is looking at “a short video of a warehouse” and to fill `scene_description` with “visible warehouse layout”. That prompt is why the word “warehouse” in model text is not independent property evidence. Report fixtures still have no `scene_description`.

## 3. Historical meanings

Source: `historical-irs-questions-v1.6.pdf`, extracted with pypdf. Labels also match `historical-worksheet-fields.json` and `static/irs_2012_worksheet.js`.

**3.1** — label “Please indicate if the incident is a Fire, Special Service, or False Alarm Incident” (printed 28, PDF page 32). Section 5.3 is information “as observed on attendance”, and these questions decide which later questions are asked. Format is a dropdown. The notes name the stored category as `Fire`, `SpecialService`, or `FalseAlarm`. It is the incident category, not a statement that a flame was visible in a clip.

**3.2** — label “What type of Property was involved?” (printed 28, PDF pages 32–33). Mandatory hierarchy, numeric 0–9999, “the type of property at/in which the incident occurred.” Nine top categories are listed; the Non Residential Buildings covering text includes the word “warehouses” among other building kinds. The page says the full list is in the Taxonomy Spreadsheet, which is not in this repo. “Warehouse” is not a code shown on the page.

**4.2k** — label “Additional Location description” (printed 34, PDF page 38). Optional free text. Depends on **4.1 = No** (incident did not occur at an addressable gazetteer location). Section 5.4 says IRS location is the incident’s real location: easting/northing are mandatory, and an address is recorded when the location is addressable. Extracted notes under 4.2k are empty. The field is an extra description of a non-addressable incident location, not a camera caption. **4.2\*** is the BS7666 address group (4.2a–4.2g) and depends on 4.1 = Yes. **4.3a/b** is easting and northing.

Other headings that look fillable and are not:

- **1.1** “FRS Incident Number” — an FRS incident number (`historical-worksheet-notes.md`).
- **2.1** “What was the time and date of call?” — when the call was received.
- **5.1** “Did the fire have multiple seats?” — fire seats, not a count of image detections.
- **8.1** “What was the cause of the fire?”
- **8.6** “What Item/material was damaged first?”
- **8.14** “What type of room/compartment did the fire start in (Location of Origin)?”
- **7.3** actions by FRS personnel; **6.2** FRS vehicles; **9.1** people evacuated (`historical-worksheet-notes.md`).

No other question is semantically fillable from the fields observed above. Free text on a sighting does not become an IRS answer because the heading is also free text.

## 4. Accept / reject

Accept list: **none**. Leave all 158 `.irs-answer` nodes empty.

| Field | Proposed source | Decision | Rationale |
|---|---|---|---|
| 3.1 | Any retained `observations.fire_sources[]` text (`description`, `burning_object`) | **Reject** | 3.1 is the attendance dropdown `Fire` / `SpecialService` / `FalseAlarm` and it routes later questions. Writing `Fire` is an official enum guess. A `fire_sources` entry is not that category: `r_report_partial` `F9` is only `"smoke at the dock door"`. Non-excluded sightings are still model observations. |
| 3.2 | Word “warehouse” in scene or location text | **Reject** | 3.2 is a numeric property hierarchy. This PDF does not define a Warehouse code; “warehouses” is an example under Non Residential Buildings. No report fixture has `observations.scene_description` or a property-type field. `r_report_dense` only has “Warehouse” inside `location_description` (“Warehouse aisle position N…”). The Cosmos prompt already tells the model the video is a warehouse. `position_provenance` values such as `wh_mobile_v1` are authored template ids. |
| 4.2k | `observations.fire_sources[].location_description`, qualified as camera-relative | **Reject** | 4.2k is optional incident-location text and is shown only when 4.1 = No. 4.1 cannot be answered: there is no gazetteer result. `location_description` is image-relative (`"beside the right rack"`). Putting it in 4.2k asserts a non-addressable incident location. `r_report_ok` has a location string on `V1:A1` only, while `T1` also contains `V2:A1`. |

## 5. Fields that must stay empty

Every question id stays empty, including the three candidates. Specific forbidden fills:

- **1.1** from `run_id`. A run id is not an FRS incident number.
- **2.1, 2.5, 2.6** from `created_at`, worksheet generation time, `timestamps_s`, `metrics.duration_s`, or `timings_s`. Those clocks are run, clip, or sim time.
- **3.1** from flames, smoke, `burning_object`, or a non-empty `fire_sources` array. Do not write `Fire`, `SpecialService`, or `FalseAlarm`.
- **3.2** from the word warehouse, the Cosmos prompt, `wh_mobile_v1` / `wh_aisle_v1`, or a zone name. Do not write `Warehouse` or any hierarchy number.
- **3.5, 3.6, 9.x** from people visible or not visible, or from an empty person list. Absence is not zero casualties or zero evacuees. These report fixtures have no person-count field.
- **3.7, 6.x** from `skill`, robot rehearsal, or sim vehicles. Those are not FRS appliances.
- **4.1** Yes or No. Addressability is unknown.
- **4.2\*** and **4.2a–4.2g** from zones, filenames, labels, or location text. None of these are an address.
- **4.2k** from `location_description`, `suggested_zone`, or `confirmed_targets`.
- **4.3a/b** from `template_position_m`, `bbox_normalized`, or zone anchors. Those are not easting/northing.
- **5.1** from `fire_sources.length` or `confirmed_targets.length`. Sighting counts are not seats. `r_report_ok` has 3 sightings and 2 targets; `r_report_dense` has 12 of each and still does not establish seats.
- **8.1, 8.3, 5.15** from `description` or `observations.cause`. `cause` is null or absent, and `unknowns` lists `cause` on the completed multi-view fixtures.
- **8.6** from `burning_object`. A visible burning object is not “the item/material damaged first.”
- **8.14** and any origin/room field from `location_description` or `zone`. Camera side and template zone are not the compartment of origin.
- **7.x** from `instruction.text` or `skill.name`. A robot plan is not an FRS action.
- **metrics.success**, `suppressed`, collision counts, and distances into outcome, damage area, or casualty fields.

If a source field is missing, null, or only present on an excluded sighting, the answer stays empty. Do not substitute “Not known”, “No”, or `0`.

## 6. Double-count and exclusion rules

These are testable even though no answer is accepted. If any later change fills a field, these still apply.

1. Build the retained set as `observations.fire_sources` whose `id` is not equal to any `excluded[].id`. Comparison is the same exact `id` match as `static/incident_report.js` 72. If `excluded` is absent or not an array, there are no exclusions; that does not mean the sightings are confirmed IRS facts.
2. An excluded sighting contributes no answer text. Its `reason` is not an answer. A location or “warehouse” string on an excluded id is ignored.
3. When `confirmed_targets` is an array, ids in one `members` list are one workbench group. `r_report_ok` `T1.members` `["V1:A1","V2:A1"]` is one group. Emitting one fire, seat, or location per member double-counts that group. `V2:A1` description `"same packaging seen from the east camera"` must not become a second incident.
4. `confirmed_target` on a mobile run is the first target, not an extra fire (`r_report_ok` `confirmed_target.fire_id` is `T1`). Do not add its facts on top of `confirmed_targets`.
5. `fire_sources.length` and `confirmed_targets.length` are not the number of fires and not the answer to 5.1. `r_report_dense` keeps 12 ungrouped targets across `V1`–`V3`; lack of grouping is not proof of 12 fires.
6. Do not merge or split fires because `zone` or `suggested_zone` strings match. Those are template slots (`right_rack`, `left_rack`, `aisle_center`).
7. A `fire_sources` entry whose `description` does not state visible flame or a burning object is not positive fire evidence. Fixture: `r_report_partial` `"smoke at the dock door"`.

## 7. Qualifier and provenance

Do not write a qualifier into an answer as a way to fill a rejected field. Empty is the correct answer.

If a future review accepts a field, the answer text must include both the source path and this qualifier, and must keep synthetic provenance on the cited clip:

`Machine-observed, unverified. Not an FRS finding. Source: observations.fire_sources[<id>].<field>.`

If the cited `clip_ref` / `video_refs[]` `sha256` is in `KNOWN_SYNTHETIC_SHA256`, or the filename or label matches synthetic, append `Synthetic Scene2Real footage.` Otherwise append `Provenance not established.` Do not write official tokens (`Fire`, `SpecialService`, `FalseAlarm`, `Warehouse`, or a hierarchy number) in that sentence.

## 8. Risks if anything beyond the accept list is filled

The accept list is empty, so any filled `.irs-answer` is out of scope.

- **3.1 = Fire** marks the incident as an attendance category and would be read as unlocking fire-only questions (primary/secondary, chimney, appliances). The run never recorded that category.
- **3.2 = Warehouse** publishes a property class the taxonomy page does not code here, from a prompt-primed word or from a location phrase.
- **4.2k** from `location_description` states a non-addressable incident location and conflicts with the empty 4.1 gate. Copying every view’s string multiplies one fire into several places (`r_report_ok` `T1`, `r_report_dense` positions 1–12).
- Filling **8.6** from `burning_object`, **8.14** from a zone, or **8.1** from a flame description invents origin, cause, or first damage.
- Copying `metrics` or `instruction` into sections 6 or 7 reports a simulator result as FRS action or outcome.
- Using an excluded sighting, or counting both members of `T1`, double-counts or revives a sighting the operator removed.

## 9. UI constraints already violated in current source

Not fixed here. Observed only:

- The title is not exactly `IRS WORKSHEET`. Stage heading is `Historical IRS worksheet` (`static/index.html` 138, `id="h7"`). `STAGES[6]` is the same string (`static/app.js` 5). The article `aria-label` and `h3` are `Historical IRS worksheet — 2012 reference` (`static/incident_report.js` 100–102).
- The sentence `Historical reference worksheet — not current FaRDaP or a validated submission.` is still rendered (`static/incident_report.js` 103).
- Cover/footer versus inner title are not separate. One header sentence says both `v1-0p` and `v1-0n` (`static/incident_report.js` 105). The `h3` does not state `v1-0n`.
- The video evidence annex is still appended in preview (`static/incident_report.js` 126–165) and is given a print page break (`.irs-evidence-annex` in `static/styles.css`).
- Source, year, Crown copyright, and the heading-only scope sentence are present (`static/incident_report.js` 104–105). Those stay. They do not claim current FaRDaP compliance.

## 10. What this review did not do

No application, test, fixture, CSS, HTML, JS, README, or CONTRACT edits. No backend tests. No inference calls. No API credentials or config reads. No commit, push, deploy, or messages. No git checkout, restore, reset, clean, or stash. Run `r_20261017_182916_abc3` was not read or modified, and port 8096 was not touched. No PDF was created. `worksheet-autofill-cursor-result.md` was not written. The only file written is this review.
