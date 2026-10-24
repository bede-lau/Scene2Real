# Historical worksheet integration decisions

Preparation only; no application changes authorised by this file. V4 compact-brief approval is pending.

Codex reviewed the 56-line Devin handoff and Cursor's independent source review. Both use the nine-section, 158-heading inventory without claiming a historical form schema or current FaRDaP compliance. Source metadata/hash matches the unmodified PDF.

Resolve routine handoff choices without adding product workflows:

- Video-evidence annex only. Omit simulation plan/results, authored zones/coordinates and grouping proposals from this worksheet output; those remain in their existing workbench stages.
- If an excluded sighting is retained as auditable evidence, tag it with the operator exclusion and reason. It must never become a worksheet answer or established incident fact.
- Preserve known synthetic provenance using static fixture hashes where available; unmatched source provenance remains unknown. Do not label unmatched footage real.
- One blank response area per historical index heading, including grouped IDs. No guessed historical subfields, response types, enums, conditional hiding or required-field validation.
- Keep #report route and run selection. Rename visible report label only.
- Flowing A4 pages, no invented page totals. Use ordinary browser pagination and verify extracted PDF includes all question headings and evidence.
- Devin remains primary implementation owner for worksheet source/renderer, local report hooks and scoped CSS after approval. Codex will own test updates and integration/docs; coordinate those explicit boundaries at dispatch.

These are implementation recommendations within the proposed v4 scope, not additional approval or a waiver. No enquiry, push, commit or deployment.
