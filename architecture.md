# Browser Training demo architecture

The workbench opens a standalone browser Training page while retaining the current run. `training-model.mjs` generates synthetic target positions, fits a two-parameter linear aiming model, and evaluates it against a forward-facing baseline. `training-demo.mjs` connects that pure model to the form and results view. No training data or results leave the browser; the existing API, MuJoCo simulations, and local G1 learning workbench are separate.

| Component | Contract and expected variation | Extension / evidence | Verdict |
| --- | --- | --- | --- |
| Workspace navigation | Opens Training separately from the Workbench so the current run remains open; indicates the current page in the menu | Shared workspace menu wraps existing route links; browser navigation check | Pass |
| Dropdown controls | Presents Active video, Simulation speed, and First fire choices with one menu treatment while preserving native select contracts | `upgradeSelects(root)` enhances marked selects; options and disabled state sync from the native select; selection dispatches the normal bubbling `change`; frontend evidence and browser interaction checks | Pass |
| Workspace menu | Shows available workspace routes and marks the current page | `upgradeWorkspaceMenus(root)` enhances static links; route destinations and new-tab behavior remain on anchors | Pass |
| Demo model | Bounded case count and seed; deterministic numeric fit and held-out results | Pure function permits a separately tested replacement; Node contract tests | Pass for synthetic 2D scope |
| Demo view | Presents scope, inputs, computed metrics and replay of prefix fits | Browser-only G1 adapter interpolates authored visual poses; desktop/mobile and 2D fallback checked, model and packaged pose contracts tested | Pass for observed flow |
| Hosting | Serves static files using the existing Vercel gateway | No new worker, storage or provider calls; deployment smoke check required | Pending live verification |

The demo does not make robot performance or incident-footage claims. Costs for existing hosting traffic depend on the user's plan; it adds no new service.
