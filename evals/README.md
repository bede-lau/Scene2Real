# Integration evaluation

Run from the repository root, using its existing `.venv`:

```sh
MUJOCO_GL=egl .venv/bin/python -m evals.runner --output output/reference-new
MUJOCO_GL=egl .venv/bin/python -m evals.runner --live --output output/campaign-new
```

The first command has zero network inference. The second permits at most 20
W&B and 20 Astra HTTP attempts, counting transient retries before transmission.
Missing credentials are recorded without substituting a provider. Automatic
retries are disabled for this evaluation. Existing output directories cannot be
reused, preventing accidental replacement of evidence. `--providers reference`
can verify Weave publication without paid model inference.

`datasets/integration_v1.json` is frozen by its adjacent SHA256 manifest: four
development incidents and eight locked test families, repeated twice. They are
new synthetic reviewed observations, not newly annotated real footage. Expected
outcomes remain outside the `case` passed to providers. Identical case hashes
allow comparisons between providers. Do not tune on the locked cases; future
tuning requires a new untouched dataset.

Each saved plan is validated, executed in Python MuJoCo, and replayed identically.
The independent audit reconstructs nozzle/range/occlusion/contact conditions from
saved qpos and checks continuous exposure. G1 controls separately measure its
ray-hit/intensity contract; their explicit fixture authorization is not model
inference. No model outcome is accepted as its own success label.

The 90% candidate gate also requires all 16 locked trials, no collisions, the
active baseline comparison, and separate rejection/staleness and browser checks.
The runner never promotes a model. Without the Astra credential, comparative
promotion remains unavailable even when candidate cases pass.

For independently annotated existing source videos, score saved observations:

```sh
.venv/bin/python -m evals.perception --runs runs/ID/run.json --output output/perception.json
```

This is scoring only: it checks annotation source hashes and exact timestamps,
reports cached provenance, and makes zero inference requests. Existing annotations
have no physical cross-view identity truth, so association accuracy is not
invented. Provider association rejection/abstention controls live in the existing
`tests/test_matching.py` suite. Historical campaigns in `Scene2Real-eval` are
documented in the dataset manifest and are not current merged-build results.

Actual browser acceptance:

```sh
BASE_URL=http://127.0.0.1:8094 PLAYWRIGHT_MODULE=/path/to/playwright \
  node scripts/integration_browser.cjs
```

It saves desktop/mobile screenshots, robot-camera evidence and an actual WebM
download. By default it calls no inference. An explicitly configured server with
`SCENE2REAL_LIVE_COSMOS=1` and browser `LIVE_COSMOS=1` permits exactly two real
robot-camera calls (visible fire and no fire). These are synthetic rendered
scenes. Manual previews and deterministic controls are clearly distinguished
from live inference. Full operator-reviewed video confirmation requires real
annotations and available baseline credentials; the browser does not fabricate
that evidence.
