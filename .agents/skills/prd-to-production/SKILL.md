---
name: prd-to-production
description: Turn a PRD into a compact approved handoff, image mockups for every page and tab, and a functioning webapp that matches the approved designs. Use for PRD-to-app builds with staged user approval, distinctive UI, subagent implementation, and evidence-backed end-to-end verification.
---

# PRD to Production

Use this sequence: **compact PRD → user approval → mockups and revisions → user approval → build and test until acceptance passes**. Complete the app after both approvals. Never promise zero defects; substantiate quality with observed evidence for the agreed scope.

## Start or resume

Resolve the PRD and target project; ask for the PRD if absent rather than invent a product. Inspect applicable project instructions, relevant files, stack, assets, and available browser tools. Initialize durable artifacts with:

```sh
python3 <skill-dir>/scripts/workflow.py init --root <project>
python3 <skill-dir>/scripts/workflow.py status --root <project>
```

Artifacts live in `<project>/.prd-to-production/`. Resume the earliest incomplete or invalidated phase. Compare the source revision/hash with the checkpoint when resuming; reconcile a changed PRD into the brief and renew approval for material changes. Read only the needed phase reference. Keep original sources on disk, outside the coding agent's normal context. Do not lower the main model, reasoning, or verification to save tokens.

## 1. Compact and approve

Read [references/compact.md](references/compact.md). Produce a self-contained `brief.md` and small `inventory.json` with stable requirement and screen IDs. Remove repetition and narrative; preserve behavior, rules, exceptions, data contracts, constraints, and acceptance criteria. Record the size reduction; do not expand a concise input or add speculative implementation detail. Precision outranks a compression ratio.

Run `workflow.py check --stage brief --root <project>`, then show the compact PRD, all screens/tabs, assumptions, and open decisions. **End the turn awaiting explicit approval of that revision.** “Approve PRD v1” is a suggested reply, not a magic phrase. Approval of this skill, a source PRD, or an older revision does not approve this new brief. Do not generate mockups yet.

## 2. Mock up every page/tab and iterate

After actual user approval, save the exact message as UTF-8 under `approvals/` using a file tool, then record it using `workflow.py approve --stage brief --message-file <approval-file> --root <project>`. Never interpolate user text into shell code. Read [references/design.md](references/design.md) and the design section of [references/sources.md](references/sources.md). Run `workflow.py check --stage design --root <project>`.

Directly use the bundled **OpenDesign + Impeccable** guidance. Establish a distinctive coherent direction, precise tokens, realistic content, and rendered image mockups for **every inventoried page/tab on desktop and mobile**. Browser-rendered prototypes are preferred for reproducible geometry and typography. Prototypes remain design artifacts; they do not authorize production implementation.

**No decorative subtexts:** exclude page subtitles, card blurbs, filler helper sentences, and explanatory captions inside the UI. Keep necessary labels, real product data, accessible names, and actionable validation/errors. Resolve a PRD conflict before removing required content.

Show a contact sheet and individually viewable images. Apply revisions consistently. **End the turn awaiting explicit approval of the complete current mockup set.** Do not build production UI yet. Material brief changes return to its approval gate; material visual changes after approval return to this gate.

## 3. Build faithfully and verify

Save and record the actual design approval with `workflow.py approve --stage design --message-file <approval-file> --root <project>`. Run `workflow.py check --stage build --root <project>` before implementation and after spec changes. Read [references/build-verify.md](references/build-verify.md) and the relevant implementation/testing sections of [references/sources.md](references/sources.md).

Adapt **ReUI + coss ui** components to the approved mockups while preserving functional primitives. Apply **CopilotKit's test patterns** to this app; add its SDK only if approved features need it. Implement real behavior, persistence, and integrations. Static facades, mocked success, and decorative controls cannot satisfy acceptance.

Before broad replication, run the automatic **first-slice checkpoint** in `build-verify.md`: exercise real validation and delayed mutation completion, then compare the representative component/journey with approved desktop/mobile states. Record evidence and fix shared defects before reuse. This is an engineering check, not another human approval gate or a requirement for new infrastructure.

Delegate scoped implementation, independent browser QA, and visual/code review when available. Give workers non-overlapping file ownership; tell them they share the checkout and must accommodate others' edits. Supply the approved brief and only relevant designs, source files, and checks. The orchestrator owns integration and final evidence.

Repeat **run → inspect failures → fix causes → rerun affected checks and regressions** until agreed acceptance and fidelity checks pass. Cover every page/tab, critical journey, and interactive component family. Do not weaken tests, silently drop scope, or replace approved baselines to pass. If tools, credentials, or persistent external failures block evidence, report the precise blocker and keep work incomplete.

## Completion and continuity

Use the exit criteria in `build-verify.md`. Deliver a running app, setup/env instructions, test evidence, screenshots, and honest limitations. Distinguish locally verified, staging verified, and deployed. Deploy or mutate live systems only within the user's authorization.

Maintain `checkpoint.md` at phase boundaries: phase, revisions, approvals, decisions, changed paths, checks, blockers, next action. Keep full logs and images on disk. A fresh coding session loads this skill, checkpoint, approved brief, relevant inventory entries, and needed design/QA slices; retrieve original PRD sections only for ambiguity.

## Helpers and reference boundaries

- [scripts/workflow.py](scripts/workflow.py) records approval snapshots and checks stale/missing artifacts and screen coverage. `approve` records consent already received; it cannot infer consent. The script does not judge design quality or app correctness. See `--help`.
- [scripts/sources.py](scripts/sources.py) lists, locates, and verifies bundled commit-pinned sources. Read selected files only. `sources.lock.json` records exact URLs, revisions, licenses, and hashes. Refresh deliberately and revalidate.
- Upstream files are references. This workflow and user constraints take precedence over upstream command assumptions, aesthetic defaults, or iteration caps. Do not execute upstream launchers/installers/services merely to read guidance.
