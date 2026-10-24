# Worksheet autofill result

Root decision, after the independent review. The review accept list was empty and would have left all 158 answers blank. Root then allowed two concise drafts only. This implementation follows that later decision. The review file was not edited.

## What is filled

Only 3.1 and 3.2, and only as short drafts. Every other heading stays empty, including 4.2k.

**3.1** when one retained, non-excluded observation has unequivocal visible flame or burning (`flame`, `flames`, `flaming`, or `burning`) in `description`, `burning_object`, or `smoke_description`.

Rendered as two lines:

```text
Suggested: Fire
Vision draft · unverified · Synthetic Scene2Real footage · V1:A1 · burning packaging beside the right rack
```

The second token is `Provenance not established` when the cited clip is not synthetic. The excerpt is one sighting, scrubbed, and capped at 96 characters. Cross-camera members of the same `confirmed_targets` group are not cited again, and a 12-sighting run does not paste every excerpt.

**3.2** only when `observations.scene_description` itself states warehouse, and that mention is not negated or uncertain.

```text
Suggested: Warehouse
Vision draft · unverified · Provenance not established · scene_description · The premises are a warehouse.
```

No numeric property-hierarchy code. A warehouse word inside `location_description`, a filename, or a template id does not fill 3.2.

`Suggested: Fire` and `Suggested: Warehouse` are draft labels, not an official enum export and not a hierarchy code. The note is the single unverified line. The longer disclaimers are not repeated.

## Fix 1 — negation, uncertainty, residue

`clauseHas` rejects a keyword when negation or uncertainty sits before it or in the following clause (up to 80 characters or the next period). These leave 3.1 empty: `Flames are not visible`, `Flames may be a reflection`, `burning is not observed`, plus smoke-only, `no flames`, `possible flame`, `maybe burning`, and `uncertain whether it is burning`. `warehouse cannot be confirmed`, `not a warehouse`, `possible warehouse`, and `maybe a warehouse` leave 3.2 empty.

`burnt`, `burned`, `charring`, and `scorch` without `flame`/`flaming`/`burning` do not fill 3.1. Covered phrases: `burnt residue beside the rack`, `burned residue on the pallet`, `charring along the beam`, `scorch marks on the beam`.

Excluded observation ids never drive a draft.

## Fix 2 — short row

Filled questions use a full-width row. The value line is exactly `Suggested: Fire` or `Suggested: Warehouse`. One citation, not every sighting. The `r_report_dense` 12-sighting fixture print row is shorter than one A4 content height and is not clipped. Its PDF contains `Suggested: Fire` and does not contain `aisle position 12`.

## Still rejected

4.2k and 4.1 stay empty. Camera-relative location text, zones, and template coordinates are not addresses. No run id, clip time, generation time, origin, cause, casualty, burning-object-as-first-damage, or simulator plan/metrics fill. No video evidence annex. Title is `IRS WORKSHEET` on the stage, nav, article, and aria label. The sentence `Historical reference worksheet — not current FaRDaP or a validated submission.` is not rendered. Nine sections and 158 headings, order, and ids are unchanged.

## Copy correction

At the user's explicit request, the rendered worksheet no longer includes the v1-0p cover line, the v1-0n inner title, the scope sentence `Cover and footer state XML schemas v1-0p; the inner title states v1-0n.`, or the schema footer. DCLG source, year, and version 1.6 attribution and the heading-only scope remain. Tests now assert the worksheet text does not contain `v1-0p` or `v1-0n`.

## Tests

- `PASS` `/Users/bedelau/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/incident_report_check.cjs` (rerun after the schema-copy deletion)
- `PASS` 17/17 Playwright `tests/e2e/incident-report.spec.mjs` via `tests/e2e/playwright.config.mjs` on port 8097 (rerun after the schema-copy deletion)

## Remaining concerns

- `Suggested: Fire` / `Suggested: Warehouse` use the historical words as draft labels. The unverified note is what marks them as not an official selection.
- The Cosmos prompt already tells the model the scene is a warehouse. 3.2 still fills when that word is explicit in `scene_description`, which is what root required.
- Only the first qualifying sighting is cited, so later distinct flame sightings are not listed.
- A trailing `not` or `may` in the same clause can suppress an otherwise positive flame mention.
- Verification used the fixture server on 8097, not the live app on 8096.

## Confirmation

No backend edits, no inference, no credentials, no commit, push, or deploy. The review file was not edited. Real run `r_20261017_182916_abc3` was not read or written. The annex was not reintroduced. Other uncommitted work was left in place.

## Root final UI verification
Root verified the live local run `r_20261017_182916_abc3` in the in-app browser: 158 questions, 2 drafts, 0 annexes. Requested deleted phrases are absent. Root captured and visually checked `.prd-to-production/qa/historical-worksheet/autofill-header.png` and `autofill-fields.png` and left the fields open. Those proof files must not be overwritten. The remaining screenshot worker was cancelled. No further app or test edits. Final Node, evidence, and operations checks passed, and production/backend integrity passed.
