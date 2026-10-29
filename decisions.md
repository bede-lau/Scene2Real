# Decisions

## 1. Browser-only training proof of concept

The local G1 training worker approached the live backend's 1 GB limit in a constrained test, and the user requested no additional spending and approved a lightweight simulated demo. Use a pure browser model and a synthetic 2D teacher, clearly labelled as such. This avoids a new hosted worker and does not alter the existing recorded pipeline. The tradeoff is that the live demo cannot train the local G1 policy, use reviewed incidents, or save jobs. The full local learning workbench remains separate.

The model is a direct function rather than a plugin system because only one demo strategy is required. Its input/output contract forms the extension boundary if a different strategy is introduced. Verify using the model tests and browser flow; deployment health remains an operational check.

## 2. Explain the fit with replayable prefix models

Show a top-down synthetic target and the teacher and model aim using the existing 2D geometry. Each replay step is a genuine least-squares fit to the first N generated examples; the zero-example state is the forward baseline. This avoids inventing a learning curve or implying MuJoCo, G1 motion, or physical performance. Provide pause and manual scrubbing and do not autoplay for reduced-motion users. Keep existing final metrics and backend workflows unchanged.

## 3. Illustrate aiming with the G1 visual asset

Replace the primary diagram with a browser-only G1 visualization, as requested. A reproducible build step clusters the pinned BSD-licensed Menagerie meshes and records the existing authored aiming poses; the browser interpolates those poses and displays guide rays using the synthetic model's angular error. The asset is approximately 1 MB and rendering occurs only on change, with no server-side physics or training. Retain the previous diagram as a WebGL fallback. The pose mapping illustrates the model output and is not a trained joint policy or a physical nozzle trajectory.

## 4. Show synthetic fire and spray

Represent the target with small procedural flame meshes and the model aim with a translucent spray and bounded droplets. The spray uses the same angular error as the existing guide, and the fire never claims extinction. Animate only while playback is active and visible; retain static effects for paused and reduced-motion states. This remains a browser-only visualization, with no fluid or suppression simulation.
