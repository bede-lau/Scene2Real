# Implement and verify

Both approvals must be current. Read relevant ReUI/coss sources and CopilotKit testing examples in `sources.md`; do not ingest entire catalogs or install both ecosystems wholesale.

## Build

Inspect architecture, package manager/lockfile, scripts, and conventions. Choose the smallest architecture satisfying the brief; preserve suitable existing choices. Use current official documentation for version-sensitive setup. Production grade means functional and operational readiness for this scope, not a fixed infrastructure stack.

Write `component-map.md`: screen IDs → component families → existing/ReUI/coss source → primitive and adaptation. Use one primitive family per interactive component; never conflate Base UI/Radix props or token systems. Preserve focus, keyboard behavior, aria states, portals, dismissal, validation, loading and disabled semantics while matching approved visuals. Inspect registry output/dependencies before installing. Copy only needed source and supporting files, retain notices, and reconcile React/Tailwind/primitive versions.

Build tokens and shell, then the first representative real component/vertical journey. Run the checkpoint below before broad replication; extend it when a materially different primitive or interaction appears. Every control needs a defined outcome. Implement approved server logic, permissions, persistence, migrations, and integrations. Validate server inputs and authorization; hidden buttons cannot enforce security. Keep secrets server-side. Fixtures may support design/tests but cannot replace promised production behavior. Missing credentials remain an explicit blocker.

Delegate non-overlapping modules, independent browser QA, and independent code/visual review. Give agents only the approved brief, their scoped designs/source paths, and exact checks. Workers share the checkout and must preserve others' edits. Name the producer/consumer interfaces and build/test handoff: required completion signal, revision and compiled asset identity. Do not capture or test a partially edited tree or stale build; reconcile independent evidence to the integrated revision. The orchestrator owns interfaces, conflicts, integrated behavior, and evidence. If subagents are unavailable, perform separate implementation/review passes and disclose that limitation.

## First-slice checkpoint

Run automatically as soon as the first representative real slice works, **before** copying its forms, dialogs or state styles broadly. Use the approved contract and existing browser/backend tools; this adds no human approval gate or mandatory product infrastructure. Exercise applicable risks below, recording why a risk is absent rather than forcing unrelated features. Repair shared causes and rerun affected checks before reuse. This early sample does not replace full acceptance coverage.

### Validation ownership

Trace the active native control, primitive/form wrapper, application validator and server path. Deliberately choose one owner for client submission/error presentation and integrate other layers with it; server validation remains authoritative for writes. A styled wrapper can intercept submit before the application handler. For example, a Base UI Form with `type="url"` may consume a malformed URL even with native `noValidate`; inspect the installed behavior. Integrating primitive validation or adapting the control to application validation are conditional choices, not a universal framework/input rule.

In the actual browser, submit a malformed URL alone, then with an earlier invalid field; use analogous conflicting constraints if there is no URL. Pass evidence includes visible actionable field errors, correct invalid state and programmatic association to the actual visible feedback, first-invalid focus in form order, all draft input retained, no write, and successful correction with exactly one durable write. Cover distinct add/edit integrations where present. Assert rendered text separately from accessible descriptions; a description assertion does not prove visible copy. Do not insert hidden matching text merely to satisfy a stale copy test; reconcile the assertion with the approved visible and accessible contracts.

### Completion belongs to its interaction

Trace mutation completion through child callbacks, parent close/redirect and data refresh. Scope UI effects to operation/draft identity **and** initiating route generation; a mounted flag alone may not protect a parent redirect or a reused dialog. Navigation, browser Back and reopening must invalidate obsolete UI ownership synchronously. A committed write must still invalidate/reload server data even when its UI owner is gone; suppress obsolete close/focus/redirect, not the committed effect. Do not repeat a committed mutation or treat request cancellation as rollback.

Test against a real mutation: let the backend commit, hold response delivery, then use Back/navigation and open/fill a new draft or move to a new route. Release the old response. Pass evidence shows durable commit and refreshed data, unchanged newer route, retained newer draft and focus, no stale close/redirect, and no duplicate write. Separately verify normal still-current completion closes/navigates as specified. A sleep before a mocked success cannot establish these properties.

### State fidelity and real error sources

Capture the first real slice on matched desktop/mobile viewports beside its approved state images/spec. Exercise validation, a real duplicate/constraint response, an actual backend write failure and recovery, and a genuinely pending request where applicable. Use isolated test data and an authorized controlled dependency/storage failure, not a live-system outage. Record the actual status/payload and UI mapping: client fallback copy can be overridden by real server field errors. Selected mocked messages are supplementary, never proof of real failure fidelity; if the real path cannot be tested, mark that evidence blocked.

Inspect exact visible text, wrapping, error borders, dialog dimensions, pending/disabled colors and typography. Keep disabled/busy/focus/keyboard semantics while matching styles. Measure agreed control bounds at rest, focused and while pressed; line-height plus padding is not a guaranteed minimum, and transforms can shrink targets. Inspect native-resolution approved/actual images, readable crops/overlays and DOM geometry; full-frame pixel percentages alone cannot pass a sparse screen. Retained input, retry and durable recovery must pass alongside appearance, without baseline replacement.

Record a compact `qa/early-checks.md` (or equivalent matrix section): slice and reuse boundary; approved revision; code/diff digest and compiled asset identity; browser/viewports; each applicable trigger → observed UI/data outcome and verdict; command/exit code plus log, response, screenshot/crop and measurement paths; defects, repairs and rerun results. Keep baselines separate. This is observed engineering evidence, not an approval record. `workflow.py` checks artifact/approval integrity only; it cannot judge these app behaviors or pixels.

## Coverage and evidence

Maintain `qa/matrix.md` or structured equivalent: requirement ID, journey, test/assertion, environment, result, evidence. Add screen/state and component-family coverage. An ID mentioned in a test is insufficient; assert visible outcomes and durable effects, with relevant server/data assertions.

| Area | Evidence when applicable |
|---|---|
| Build | Locked clean dependency install; types, lint, required existing tests, production build; smoke the production runtime. |
| Journeys | Browser E2E for all critical flows and page/tab navigation; domain operations, reload persistence, roles, validation, empty/loading/error/retry, deep links, search/filter/pagination if present. |
| Components | Keyboard/focus/selection in menus, dialogs, comboboxes, tabs, forms, grids; escape/dismiss/return-focus; double-submit, loading/disabled, destructive confirmation. Cover unique variants and integrations, not every identical instance. |
| Responsive/a11y | Desktop/mobile for every screen plus representative tablet/zoom/long-content checks; overflow, contrast, labels, focus, keyboard, reduced motion; automated accessibility checks plus manual interaction. |
| Fidelity | Actual screenshots beside approved images at matched viewports; compare type, spacing, geometry, color, borders, icons, content, states and no-subtext rule. Use overlays/diffs to locate changes and inspect visually. |
| Runtime/server | Unexpected browser exceptions and relevant console/network errors fail checks; explicitly identify expected errors. Test authorization, session, persistence, constraints, failed writes and recovery. |
| Operations | Usable environment example without secrets; run/build/migration/deployment instructions; health/error handling and performance evidence against requested targets. |

Use Playwright or the project's existing equivalent for repeatable E2E. CopilotKit examples demonstrate browser assertions, layout/style regression checks, and retained failure traces. Adapt patterns to this app, not CopilotKit's app-specific tests or long AI waits. Use its SDK only for approved AI functionality. Test deterministic AI tool/state transitions separately from a small real-provider integration check; mock outputs cannot prove real integration.

In `qa/results.md`, record commands, timestamps, exit codes, tested commit or dirty-tree digest, environment, and log/report paths. Keep full diagnostics on disk and report concise results. Evidence must match current code. Skipped, unrun, flaky, blocked, and mocked-only checks are not passes. Failure-path mocks are useful but do not replace working core integrations. Claim only the browsers actually tested.

## Repair loop

Run mapped checks; inspect screenshots, console, failed requests, and server logs. Group failures by cause and assign independent fixes. Add regression assertions for meaningful observable defects. Rerun affected checks, then required integrated regression/build checks for the final tree. Rerun visuals for affected screens and consumers of changed shared components; avoid redundant unaffected suites.

Continue until the approved acceptance and fidelity criteria pass. Do not impose an arbitrary two-pass cap on needed bug fixes, or endlessly polish after acceptance passes. If an external blocker persists after targeted diagnosis, checkpoint the evidence and request only the needed input. Never suppress errors, weaken assertions, drop features, or bless new baselines to declare success.

## Exit criteria

- Every approved requirement and page/tab is implemented and mapped to relevant passing evidence; real core flows, persistence, and integrations work.
- Required checks and production build pass for the final tree. No known unresolved functional, security, or fidelity defect remains in scope; intentional exceptions need explicit user acceptance.
- Independent QA/review findings are resolved and retested; actual images closely match the approved visual contract, with any accepted environment variation documented.
- Setup/env/migration/run instructions are usable. Report whether the app is locally verified, staging verified, or deployed; do not imply deployment without evidence.

Deliver the app/run location, concise changes, pass/fail counts with evidence paths, and remaining blockers or accepted limitations. A finite test suite cannot guarantee zero defects; state concrete verified results.
