# Browser Training demo architecture

The existing workbench links to a standalone browser page. `training-model.mjs` generates synthetic target positions, fits a two-parameter linear aiming model, and evaluates it against a forward-facing baseline. `training-demo.mjs` connects that pure model to the form and results view. No training data or results leave the browser; the existing API, MuJoCo simulations, and local G1 learning workbench are separate.

| Component | Contract and expected variation | Extension / evidence | Verdict |
| --- | --- | --- | --- |
| Workbench navigation | Opens the demo separately so the current run remains open | Additive link; browser navigation check | Pass |
| Demo model | Bounded case count and seed; deterministic numeric fit and held-out results | Pure function permits a separately tested replacement; Node contract tests | Pass for synthetic 2D scope |
| Demo view | Presents scope, inputs, computed metrics and replay of prefix fits | Uses additive model history contract; browser playback, pause, scrubbing and target selection checked; reduced-motion behavior covered by unit test | Pass for observed flow |
| Hosting | Serves static files using the existing Vercel gateway | No new worker, storage or provider calls; deployment smoke check required | Pending live verification |

The demo does not make robot performance or incident-footage claims. Costs for existing hosting traffic depend on the user's plan; it adds no new service.
