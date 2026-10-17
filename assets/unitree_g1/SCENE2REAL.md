# Scene2Real derivative notes

Source: Google DeepMind MuJoCo Menagerie, directory `unitree_g1`, commit
`62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35`.

The upstream model describes the **Unitree G1**, not R1. Original files here are
unmodified. `LICENSE` contains the complete BSD-3-Clause terms; `SOURCE.json`
records the pinned download paths and SHA-256 values. The upstream README notes
that this is a simplified MJCF description and that actuator tuning is needed.

`scene2real/live_model.py` creates the application derivative at load time:

- Retains all 29 actuated joints, SI metre scale, link masses/inertias, joint
  axes, transforms, limits, and per-joint actuator force bounds.
- Removes the pelvis free joint to give an explicitly fixed-base demonstration.
  Standing balance, locomotion, and hardware-ready control are not implemented.
- Uses finite position-servo gains, gravity, and a 2 ms MuJoCo timestep. Gains
  are demonstration parameters, not identified physical motor parameters.
- Adds a rigid 0.55 kg extinguisher/tool body to `right_wrist_yaw_link` with a
  `live_nozzle` site whose local +Z is its spray heading.
- Adds a torso-mounted `live_camera`, floor, warehouse shelving/crates,
  three target anchors, and movable fire/occluder proxies.
- Authors fixed left/center/right pose references once with deterministic IK.
  Runtime execution tracks those references through force-limited actuators.
  These motions are predefined and are not a trained robot policy.

Browser meshes under `static/assets/unitree_g1/mesh_*.json` contain MuJoCo's
compiled vertices and triangle indices. They use each compiled geom's local
frame; the corresponding live world geom transform is applied by Three.js.
The conversion does not rescale or simplify the source geometry. Joint/body
hierarchy, axes, limits, source and license metadata are exposed in the JSON
manifest. License and source metadata accompany the browser assets.

Fire collision is a 0.32 m radius sphere representing an authored spray target,
not a fire dynamics model. It has nonzero alpha because MuJoCo ray queries skip
fully transparent geometry; the browser hides the proxy in favour of fire FX.
Suppression is a simplified hit/exposure rule, not fluid or combustion physics.

Regenerate upstream downloads with `.venv/bin/python scripts/fetch_g1_assets.py`.
The first manifest request exports browser geometry. Mechanical provenance,
dynamic tracking, hits and occluder blocking are tested in
`tests/test_live_model.py`.
