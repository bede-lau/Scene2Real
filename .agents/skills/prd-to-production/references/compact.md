# Compact handoff

Make a fresh coding agent able to build the same product without the long PRD. Compression is semantic, not a lossy summary or an instruction to erase active context.

Read the original once in scoped sections if needed. Record its location and revision/hash in `checkpoint.md`; retain a source copy/map under `source/` where useful. Preserve the original.

Assign stable `R-...` requirement IDs and `P-...` screen IDs. Retain:

- Goal, users/roles, scope and exclusions; every page/tab, nested route, role-specific surface, navigation relationship, and critical journey.
- Actions, business rules, calculations, permissions, transitions, validation, failure/retry/undo behavior, and boundary cases.
- Entities/fields/types, persistence, API/integration contracts, uploads/exports, authentication and sessions.
- Stack/external constraints, measurable targets, accessibility/responsive requirements, and testable acceptance.
- Decisions, contradictions, and explicitly marked assumptions. Never promote a guess into a requirement.

Remove repeated rationale, marketing language, chronology, and speculative implementation. Keep examples that specify calculations or exceptions. Preserve units, limits, time zones, and inclusive/exclusive boundaries. Terse clauses work; unexplained abbreviations and “standard CRUD” do not.

Use the fewest words that preserve the contract; there is no minimum length. **Never expand an already concise PRD to fill a template or word target.** For verbose PRDs, seek a substantial reduction by removing repetition, not rules. Count source and brief words/bytes and record the comparison in `checkpoint.md`. If the brief grows, remove repeated acceptance/checklist/screen descriptions and speculative detail; justify only unavoidable normalization. Do not invent entity fields, endpoint contracts, or status transitions that the source does not specify. Keep suggested decisions outside the canonical requirement clauses until approved.

For large products, use a compact global brief plus complete feature slices and an explicit load map. No requirement may survive only in the discarded original. Building the whole product still covers every slice.

## Artifacts

`brief.md` is canonical and self-contained. Use only applicable headings: goal/scope; terse screen map; requirement clauses with IDs, rules, and acceptance together; essential constraints; open decisions. State each fact once. Do not restate requirements in a final acceptance checklist, a second data schema, and a narrative screen list. Include data/API contracts only to the extent specified by the PRD. A short PRD may need only a few dense paragraphs or a table. Open decisions stay short and clearly distinct from approved requirements.

`inventory.json` indexes coverage without becoming a second PRD:

```json
{
  "brief_revision": "v1",
  "requirement_ids": ["R-create", "R-permissions"],
  "screens": [
    {"id": "P-projects", "route": "/projects", "tab": null, "roles": ["member"], "requirements": ["R-create"]},
    {"id": "P-settings", "route": "/projects/:id", "tab": "settings", "roles": ["owner"], "requirements": ["R-permissions"]}
  ]
}
```

Use real product IDs and routes. Every tab gets an entry even with a shared URL. Dialogs can be screen states. After compression edits, reconcile IDs across brief, inventory, and loss audit; do not rename in only one artifact. Run `workflow.py check --stage brief --root <project>` before presenting: every declared requirement ID must occur exactly as an ID in the canonical brief, and screen references must resolve. The helper checks identity relationships, not whether criteria are meaningful or complete. Keep indexing machine-readable; coding agents load relevant entries on demand rather than a duplicate full product description.

## Loss audit and approval

For every original PRD section, record a retained requirement ID or a reason it was redundant/out of scope in `source/coverage.md`. This small audit is author evidence, not normal coding context. For complex PRDs, an independent reviewer compares the original and compact output for omissions and invented scope.

Present the brief, screen inventory, and material decisions. Stop for explicit user approval. Record the subsequent approving message bound to the exact brief/inventory files. Edits invalidate the approval. Do not assume that creating the original PRD approved a compressed revision.
