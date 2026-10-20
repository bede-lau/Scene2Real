# Historical IRS worksheet — independent review

Review only, 2026-10-19. Pending a revised compact brief and design approval. No implementation, inference, backend, or API change. Read-only: worksheet JSON, notes, question index, and `static/incident_report.js` plus its `app.js` generate/retain path. No tests, enquiries, runs, or secrets.

## Correction

The public [HO-FaRDaP GitHub organisation](https://github.com/HO-FaRDaP) only establishes that developer resources are private. It does not establish their contents or a universal printable template. Whether any current form is national or service-specific is unconfirmed. An earlier review overstated that page as proof of the live schema.

## Source fidelity

`historical-worksheet-fields.json` matches `historical-question-index.csv`: 158 unique IDs, same whitespace-normalized labels and order, nine sections (Incident Identity, At Call Details, On Attendance Details, Location Details, Additional Information, Resources Used, Action, Damage, Involvement of Persons). Source is DCLG *Incident Recording System – Questions and Lists* v1.6, April 2012 (July 2012 PDF; hash in the JSON). Cover/footer say XML schema v1-0p; inner title says v1-0n. Keep both. A contents label is not an input type, option list, or rule. The printed page is where the question starts. Unnumbered hidden, derived, and callsign items sit outside the 158 and stay out. No run field is mapped.

## Risks

1. Prefill. Run id is not 1.1. Clip-relative samples and report generation time are not 2.1. An authored zone is not 4.2*. Template metres are not 4.3a/b easting/northing. Sighting counts are not 5.1 seats. A robot or simulation is not 6.2 vehicles or 7.3 FRS action. A flame description is not 8.1 cause. Missing people are not a 9.1 count.
2. Empty means empty. 0, No, None, unknown, PASS, and FAIL are fills. A measured sim collision count of 0 and `suppressed: false` stay out of every answer area. Current official answers stay blank: this run has no genuine supporting facts for them.
3. Group IDs. 4.2* is a contents grouping; the PDF shows 4.2a–4.2g with dependencies the index does not encode. 4.3a/b and 6.14a & b are likewise unexpanded. Keep those strings, plus 4.2k, 5.16a, and 8.35a, verbatim. Do not split or merge them.
4. Conditionals. 3.1 branches later questions; 8.1’s cause list depends on 5.15. The publication omits 200-plus rules. Show all 158 lines. Do not hide, default, or validate them. A filled-looking sheet is still not a valid historical or FaRDaP submission. `report.complete` is only demo-sheet completeness.
5. Annex separation. Observations, clip-relative times, operator zones, and simulation belong in a separate run video-evidence annex, not in the 158 blanks.
6. Layout. The current sheet is a one-page dense A4 demo. 158 blanks need readable multi-page A4 and the same IDs readable on mobile.
7. Freshness and safety. `fingerprint` omits `clip_ref`, `video_refs`, `excluded`, and `error.message`, which the demo sheet can still show. Analyse, confirm, and reset drop the snapshot; switching run id clears it. An in-flight generate for run A must itself discard A’s sheet when B is visible. Escape model and filename text; keep path and credential redaction.

## Checklist

- [ ] Banner states historical IRS v1.6 (April 2012), both schema strings, “not current FaRDaP”, and “not a valid submission”.
- [ ] Nine sections and all 158 IDs/labels, contents order, each with a blank response area and no run prefill.
- [ ] 4.2*, 4.3a/b, and 6.14a & b appear as single contents lines, not invented subfields.
- [ ] Annex is separate, marked demonstration, and holds video evidence only. Sim results stay labelled simulation.
- [ ] Worksheet and annex drop together on analyse, confirm, reset, fingerprint change, and run switch. Print only when the sheet run id is the visible run.
- [ ] Rendered text is escaped. No new stored report or server route.
- [ ] A4 is multi-page and readable; mobile shows every ID and blank without clipping.

Do not build until the revised brief and mockups are approved.
