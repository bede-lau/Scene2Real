# Decisions

## 1. Browser-only training proof of concept

The local G1 training worker approached the live backend's 1 GB limit in a constrained test, and the user requested no additional spending and approved a lightweight simulated demo. Use a pure browser model and a synthetic 2D teacher, clearly labelled as such. This avoids a new hosted worker and does not alter the existing recorded pipeline. The tradeoff is that the live demo cannot train the local G1 policy, use reviewed incidents, or save jobs. The full local learning workbench remains separate.

The model is a direct function rather than a plugin system because only one demo strategy is required. Its input/output contract forms the extension boundary if a different strategy is introduced. Verify using the model tests and browser flow; deployment health remains an operational check.

## 2. Explain the fit with replayable prefix models

Show a top-down synthetic target and the teacher and model aim using the existing 2D geometry. Each replay step is a genuine least-squares fit to the first N generated examples; the zero-example state is the forward baseline. This avoids inventing a learning curve or implying MuJoCo, G1 motion, or physical performance. Provide pause and manual scrubbing and do not autoplay for reduced-motion users. Keep existing final metrics and backend workflows unchanged.
