# Scene2Real branch integration

## Refreshed source comparison

- Requested branch: `merge` (user name takes precedence over suggested integration/wandb-live-simulation).
- Main: `cdf6adf641e905c5a75a1232db1d65a54ee26368`.
- Simulation: `8a4e03d` (full source revision recorded in output/integration/source-refs.json).
- Merge base: `cdf6adf641e905c5a75a1232db1d65a54ee26368`.
- Refresh found main 0 commits ahead and simulation 2 commits ahead. Simulation had already merged
  main in 8a4e03d. The earlier nine-conflict preview no longer applies. No shared branch was reset.
- Existing evaluation checkout and simulation worktree, including uncommitted work, remain untouched.

## Stage 1 review boundary

A non-fast-forward merge preserves both source histories. The default `/` remains main's multi-video
workbench, with upload, per-timestamp reviewed overlays, grouped/excluded sightings, R1 mobile replay
and recording. `/live.html` loads server-owned MuJoCo G1 dynamics with vendored renderer dependencies.
`/legacy.html` redirects to the current workbench. The /api/live router precedes the static catch-all;
all existing run/video routes remain. Cross-mode handoff must never select only the first target or
move a template anchor. The source branch's permissive side-based link was replaced by a neutral
independent preview until the capability adapter is installed.

There were no new textual conflicts to resolve. Existing main spatial-QA and approval files remain
in history. Physics evidence brought by a9c6a94 and integration documentation from8a4e03d are historical,
not measured evidence of this build. Fresh phase1 results live under output/integration/phase1.
No new product/design approval records were created.

## Remaining implementation stages

1. Preserve explicit identity and capabilities for legacy aim/spray, authored R1 mobile exposure,
   and fixed-base Menagerie G1 intensity suppression. Strict incident adapter rejects all incompatible
   targets and coordinates; the mobile workflow remains available.
2. Shared reviewed-evidence builder; Astra default, W&B selected model and explicit shadow/evaluation;
   schema validation, model/finish/usage/attempt provenance and blocked errors without provider fallback.
3. Stable linked local/Weave trace events across requests/threads; bounded background logging;
   independent stage and physics provenance. No credentials, recordings or every-step events.
4. Fresh versioned provider comparison and mode-specific regression/browser evidence. The previous
   29/30-valid,25/30-success campaign is historical and will not be relabelled as this build.

## Acceptance and rollout

Default remains Astra; its vision grounding/matching dependencies remain independently visible.
Live Cosmos remains disabled unless explicitly enabled. No browser physics or learned G1 walking is added.
Candidate promotion requires >=90% locked-test simulation success, baseline comparison, zero unintended
contacts, and passing rejection/staleness checks. No main merge or deployment is authorized.
Rollback: select Astra and, if required, disable the optional live entry point; retain saved evidence.
