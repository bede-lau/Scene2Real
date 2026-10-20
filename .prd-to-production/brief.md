# Scene2Real — historical IRS worksheet, proposed v4

Replace the local report’s demo presentation with a formal printable worksheet for the user-selected historical fallback. Keep the existing workbench and pipeline.

**P-report-preview** — existing `/?run=:runId#report`: select a run → Generate worksheet → preview → Print / Save as PDF.

- **R-source:** Title “Historical IRS worksheet — 2012 reference”. Attribute DCLG’s IRS Questions and Lists v1.6 (July 2012, from April 2012). Preserve the nine sections and 158 numbered question headings/IDs in the prepared source inventory, including grouped identifiers. This is a worksheet based on the historical question index, not a reconstruction of every subfield, option or conditional rule, and not current FaRDaP or a validated submission.
- **R-blank:** Provide empty answer areas for unsupported incident facts. Current runs do not establish the historical incident fields: do not insert run IDs as incident numbers, clip seconds as incident times, template positions as addresses, or simulation outcomes as real actions. Never replace missing data with zero, No, unknown or N/A.
- **R-evidence:** Put the selected run’s filename/reference, sampled clip-relative timestamps, observations and source/cache/synthetic provenance in a separate video-evidence annex. Keep model observations distinguishable from incident answers. Exclude simulation instructions/results from worksheet answers; no new inference.
- **R-integrity:** Use one current snapshot. Clear stale content after reset, reanalysis, reconfirmation, source changes and run switching; discard late responses. Escape untrusted text and exclude credentials, private URLs and local paths.
- **R-print:** Formal white-paper layout within the existing app, readable on desktop/mobile and across A4 pages. Preserve every question and blank response area without clipping. No one-page limit.
- **R-local:** Change only the local feature checkout. Preserve existing unrelated edits and Cosmos/planner/simulation processing. No new backend service, external submission, enquiry, commit, push or deployment.
- **R-verify:** Check source order/count/labels, truly blank answers, separated evidence, stale/run isolation, escaping, mobile layout and complete multipage print output.

Proposed presentation choice: a printable read-only worksheet with blank answer spaces; no new manual-entry or persistence workflow. Current FaRDaP implementation remains a separate source-dependent future scope.
