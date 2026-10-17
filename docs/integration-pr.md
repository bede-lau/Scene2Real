# Proposed PR

Title: Integrate incident workbench and G1 rehearsal with gated W&B mobile planning

Scene2Real now keeps the current multi-video incident workbench at `/` and provides the server-owned
MuJoCo G1 renderer at `/live.html`. Incident handoff validates complete target coverage and exact authored
anchors; unsupported R1/mobile cases receive an explanation rather than losing targets or moving them.
A shared reviewed-evidence request builder adds an explicitly configured W&B mobile planner and a
non-executable shadow mode. Astra remains the default, including its independently attributed vision
grounding/matching roles. Invalid, truncated, unavailable and mismatched-model outputs cannot execute;
no mobile cross-provider fallback is substituted.

The integration preserves source histories and existing spatial/approval records. Stable local/Weave
milestones link HTTP and background operations; immutable redacted evidence remains archived to VAST.
G1 logging/export I/O is outside the physics lock and freshness is revalidated before authorization.
The historical R1 backward-aim self-collision is corrected with a predefined carry pose while travelling;
contact checks and suppression definitions are unchanged.

## Review stages

1. Merge/history and existing planner: `a7928f2` + `b71c168`. Phase1:169 tests and existing frontend checks passed.
2. Opt-in W&B provider, capability identity/handoff, carry-pose correction and correlated telemetry/evaluation:
   subsequent focused commits. Read docs/integration-plan.md and docs/integration-qa.md before enabling a candidate.

## Verification and measured outcomes

- 233 Python tests passed; frontend evidence checks, compileall, diff and uv lock checks passed.
- 19/19 full browser checks with mocked model boundaries and real ingest/MuJoCo/recording; screenshots and recordings retained.
- 6/6 G1 deterministic physics controls; inherited freshness, occlusion, wrong-aim, actuator and worker cleanup tests preserved.
- Fresh W&B candidate:19/20 valid successful plans,15/16 locked trials (93.75%),zero collisions; one truncated response rejected.
- Active Astra comparison unavailable because server key absent. Candidate remains inactive; no automatic promotion.
- Final live G1 browser16/17: positive returned uncertainty and correctly blocked spray; no-fire passed. Autonomous positive
 suppression is unverified. Video incident detection2/2; exact-frame localization unscored because source boxes are untimestamped.
- The unmodified multiview acceptance script correctly fails its real-provider gate on the explicit mocked fixture; it is not a live pass.
- Request ledger20W&B/0Astra/6Cosmos; no verified monetary cost. No training, new physics engine or mobile G1 policy.

[W&B locked evaluation](https://wandb.ai/vastdata/team-28/r/call/01a14a56-7d1f-71c2-b0e9-54eabc1474e8).
Full evidence, sources and limitations: docs/integration-qa.md and docs/integration-qa/provenance.json.

## Compatibility, migration and rollback

Existing run/API contracts and legacy single-target path remain. New simulation identity and provider metadata
are additive; old saved runs load without inventing identity. W&B text planning does not replace Astra vision.
Use project-local requirements or the reconciled uv lock; no global packages or frontend migration.

Rollback selects `SCENE2REAL_PLANNER_PROVIDER=astra`. Set `SCENE2REAL_LIVE_COSMOS=0` to stop automatic live inference;
if the additional UI must be removed, disable its navigation and `/api/live` router inclusion in a reviewed follow-up.
Retain all saved records/artifacts. No main merge or deployment is included in this work.
