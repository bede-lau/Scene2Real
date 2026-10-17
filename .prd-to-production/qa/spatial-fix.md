# Spatial review and warehouse UI verification

Verified locally on 17 October 2026 against base `6036c8f26c8ef2bc36faa1220c060d18fc9152d7`. Actual Cosmos/YOLO GPU endpoints and the user's configured OpenAI API were used. Credentials stayed outside the checkout. Earlier evidence in `results.md` remains historical; this report supersedes its spatial limitations only within the checks described here.

## Changes and evidence

Cosmos v4 ingestion and original responses are retained. Astra `astra_fire_grounding_v1` independently reviews all five timestamped frames per view and supplies effective `A` sightings, frame-specific boxes and actual returned-model provenance. Original observations live in each view's `analysis.spatial_review.original_observations`. Invalid or unavailable enabled grounding blocks the analysis; it does not silently reuse bad boxes.

Cross-camera suggestions use Astra `astra_fire_association_v1`, persistent shared landmarks, viewpoint reasoning and masked background SIFT/RANSAC registration with a projected fire-base consistency check. This is a conservative planar consistency test, not camera calibration. Matching uses only boxes for the exact supplied frame timestamp. Original Cosmos suggestions remain audit data and do not initialize groups. Provider failures and malformed responses produce review states with preserved, redacted evidence.

The user's UI edits are included: inset selector arrow; spaced live pill; removed cause/scale/depth/unknowns list, per-fire visual-evidence disclosures and Cosmos grouping audit from the visible flow; timestamps moved from Video to Confirm target; display labels renamed Warehouse set 1/2. Clip IDs, source filenames/hashes and stored evidence remain unchanged. Bounding boxes remain visible.

## Live results

| Run | Analysis and matching | Confirmed rehearsal | Mechanical result |
| --- | --- | --- | --- |
| `r_20261017_144730_cdba` | Three live views, completed Astra grounding; identity unverified, zero proposals | Four separate V1 sightings; all eight V2/V3 sightings explicitly excluded | Initial plus three resets passed, 32 checks |
| `r_20261017_144708_4f1b` | Three live views, completed Astra grounding; identity unverified, zero proposals | Three separate V1 sightings; all six V2/V3 sightings explicitly excluded | Initial plus three resets passed, 32 checks |
| `r_20261017_144735_bb53` | Three known projective variants of the same video; four correct automatic three-view proposals | Automatic proposals confirmed unchanged | Initial plus three resets passed, 32 checks |

All twelve simulation executions began at the station, walked, suppressed every confirmed template target with at least two continuous seconds of valid spray exposure, recorded zero unintended collisions and produced decodable MP4s. Reset cleared outcomes and recordings; repeated measured outcomes and trajectory hashes matched. Real `gpt-6-astra` generated each instruction using `mobile_plan_r1_v2`. See [provider provenance](evidence/spatial-fix/provider-provenance.json), [set 1](evidence/spatial-fix/set1-acceptance.json), [set 2](evidence/spatial-fix/set2-acceptance.json) and [positive acceptance](evidence/spatial-fix/positive-acceptance.json).

Independent visual annotations were recorded before predictions and were never sent to inference. At the 2.5-second frame of each original clip, all 21 effective boxes matched the 21 references at IoU ≥0.5; minimum IoU 0.7318, maximum 0.9664. Preserved Cosmos boxes matched 3 references from 22 predictions in this rerun. These approximate annotations need independent adjudication, and six synthetic frames cannot establish general accuracy. See [localization report](evidence/spatial-fix/localization-evaluation.json) and `tests/fixtures/fire_localization.json`.

The positive control's twelve detections each mapped uniquely to one of four held-out transformed reference sites. All four proposed groups matched those sites. Two groups contain different source numbers in V3, so matching did not merely group identical IDs. Input order was permuted. This control uses projective variants of one video, not independent physical cameras or measured 3D geometry. See [positive evaluation](evidence/spatial-fix/positive-evaluation.json), [fixture transforms](evidence/spatial-fix/positive-fixture.json) and [upload order](evidence/spatial-fix/positive-upload-order.json). QA-only generation and evaluation scripts are retained beside them; their `output/spatial-fix/positive-e2e` paths describe the original local evidence layout. Held-out transforms enter evaluation only after inference.

## Regression and browser checks

- Full final Python suite: **141 passed**, two existing FastAPI startup deprecation warnings; [JUnit](evidence/spatial-fix/pytest.xml).
- Focused Node checks and JavaScript syntax passed: raw response fidelity, uncertainty in retained JSON, source provenance, measured verdict, frame-specific overlays including absent sources, abstention, display-only names and timestamp seeking.
- Actual API code review found three issues: wrong-time boxes, missing model identity fallback and malformed provider envelopes. All were repaired with regressions before the live reruns; [review findings](evidence/spatial-fix/astra-review-findings.json) and [API metadata](evidence/spatial-fix/astra-review-metadata.json) preserve that earlier review snapshot.
- Browser verification used the in-app Chromium at 1440×1000, 727×853 and 390×844. No horizontal document overflow at these sizes. Confirm's timestamp chip paused and sought the source to 2.5 s and scrolled to it. Correct boxes were inspected across both sets' views. Removed sections were absent; raw and validated JSON remained available. The selected-view raw response SHA-256 matched the saved Cosmos response (`d5447dfd4258fb662738b43f0755a0e4e468dd6038719b15ecaf9eff038c647a`).
- Recording 4× selection set the actual media playback rate to 4; recording decoded at 960 px width, readyState 4, no media error. Interactive replay and keyboard Home scrubbing worked. Reload restored the completed incident. Console warnings/errors were empty in both inspected runs.

Local screenshots, raw API responses and recordings remain in ignored `output/spatial-fix/`; source clips remain unchanged. A credential-content scan and final source hashes are recorded with the release evidence.

## Limits

The original six independently generated camera images change warehouse structure between views; physical fire identity cannot be established from them. Correct abstention avoids invented matches. V1-only rehearsals do not demonstrate incident-wide multi-camera fire coverage. Template target positions, reduced R1 proxy motion and suppression exposure are authored demonstration behavior, not reconstructed geometry or validated firefighting physics. Weave tracing and VAST archival remain explicitly skipped because their credentials are absent. No VM deployment or universal failure-free guarantee is claimed.
