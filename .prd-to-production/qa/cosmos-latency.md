# Cosmos analysis latency — 17 October 2026

## Diagnosis

The screenshot corresponds to `r_20261017_172035_799e`. Its 58.1 s label
combined three serial view pipelines, including Astra review, rather than one
Cosmos request. Cosmos took 6.82, 6.36 and 3.47 s. Astra reviews took 15.03,
16.15 and 9.65 s. Two additional association calls took 3.69 and 15.44 s
after the displayed timer stopped. The complete operation took about 77 s.

## Change

Cosmos requests remain serial and ordered. A completed view's independent Astra
review overlaps subsequent views. After every view passes, Cosmos association
and Astra matching run concurrently. Separate bounded worker pools avoid nested
executor waits; submitted work inherits tracing context. Collection and record
mutation remain ordered on the calling thread.

The change preserves all five sampled frames per view, model settings, prompts,
strict validation, failure states, raw responses, review provenance and
conservative association checks. It does not enable caching. New analysis timers
include association, with separate phase timings retained through confirmation.
The UI distinguishes selected-view Cosmos, Astra review and full analysis time;
older partial timers are labelled "View processing".

## Live comparison

Sequential, uncached runs used identical source files in identical order:
`demo-set-2-east.mp4`, `demo-set-2-west.mp4`,
`synthetic-warehouse-fire.mp4`. Baseline used the original running server;
candidate used an isolated server with the same credentials and configuration.

| Measurement | Baseline | Candidate |
| --- | ---: | ---: |
| Client-observed operation wall time | 78.28 s | 44.16 s |
| View phase | 59.24 s | 30.10 s |
| Association phase | serial | 13.76 s |
| Cosmos V1 / V2 / V3 | 6.59 / 6.43 / 3.81 s | 6.60 / 6.45 / 4.43 s |
| Astra review V1 / V2 / V3 | 16.03 / 16.02 / 9.71 s | 14.20 / 16.77 / 10.75 s |
| Cosmos association | 2.56 s | 4.02 s |
| Astra matching | 14.53 s | 13.76 s |
| Validated sightings V1 / V2 / V3 | 3 / 3 / 1 | 3 / 3 / 1 |

Baseline: `r_20261017_174637_d1da`.
Candidate: `r_20261017_174810_869b`.
Measured wall time decreased 43.6%. This is one controlled pair, not a latency
guarantee; provider response times vary. The gain comes from overlapping work,
not faster Cosmos inference or weaker analysis.

## Regression evidence

- All views were live, retained five sampled frames, original Cosmos evidence
  and Astra raw responses.
- All six independently annotated fires in the two CCTV clips matched at
  IoU >=0.5 in both runs. Candidate minimum IoU was 0.8226. This small synthetic
  frame check is not a general accuracy estimate.
- Both association results remained unverified with no automatic candidates.
- Candidate confirmation explicitly used three V1 sightings and excluded the
  other four because cross-camera identity was unverified. Real Astra planning,
  simulation, MP4/trajectory serving, reset and rerun passed: 3/3 targets
  suppressed and zero unintended collisions on both rehearsals.
- Final backend suite: 179 passed. The event-driven concurrency test checks
  overlap, serial Cosmos order, result order, retained evidence and contextvars.
  Existing tests cover invalid/unavailable reviews and blocked confirmation.
- Both frontend suites and JavaScript syntax check passed, including selected
  view timings, legacy partial timing labels, evidence and async polling.
