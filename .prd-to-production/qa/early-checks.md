# First real slice
- Approved revision: v2 + user-authorized fast-track; local native-HTML design retained.
- Real slice: run r_20261017_140400_db30: one MP4 -> uncached Cosmos + YOLO -> explicit mobile confirmation -> real gpt-6-astra -> MuJoCo mobile trajectory -> H.264 recording -> measured PASS.
- Stored evidence: output/qa-v2/first-slice-analysis.json, first-slice-plan.json, first-slice-complete.json; runs/r_20261017_140400_db30/simulation.mp4.
- Observed: start at station, 1.5m travel, one suppressed target, >=2s measured exposure, zero unintended contacts; recording downloadable. Browser exposed Astra provenance, 1x/2x/4x controls and per-fire QA.
- Validation regression: atomic 1–3 sources, invalid views, reused group membership, duplicate slots, exclusions, legacy multiview bypass, strict Astra target/settings, contact/LOS/exposure and encoder failures covered in focused automated tests.
- Repairs before broader acceptance: excluded evidence target mapping, legacy multiview confirmation bypass, replay water/measurement agreement, self/floor contact accounting, missing demo selection.
- Remaining: full both-set browser journeys, repeated numeric replay, mobile layout and final code digest/evidence.
