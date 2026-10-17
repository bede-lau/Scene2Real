# Demo clips (branch `clips/warehouse-fire-demo`)

NVIDIA PhysicalAI SDG `warehouse_fire` run `00023b5323028ab83e67_run_6_seed_1486583949`, five ceiling cameras (~9.2 s each).

- Source dataset: `nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes`
- Shard: `rgb/warehouse_fire/fire-rgb-00000.tar`
- **Primary for live acceptance:** `warehouse_fire_c01.mp4`

These files are gitignored on `main`. This branch exists only to ship demo MP4s. Checking out `clips/` from this branch does not change app code.

```bash
git fetch origin clips/warehouse-fire-demo
git checkout origin/clips/warehouse-fire-demo -- clips/
```
