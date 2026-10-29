"""The browser asset must remain derived from the pinned G1 visual poses."""
import json

import numpy as np

from scripts.build_training_g1_asset import OUTPUT, generate


def test_packaged_visual_matches_pinned_g1_generator():
    packaged = json.loads(OUTPUT.read_text(encoding="utf-8"))
    generated = generate()
    assert packaged["schema"] == generated["schema"]
    assert packaged["commit"] == generated["commit"]
    assert packaged["license"] == "/assets/unitree_g1/LICENSE"
    assert OUTPUT.stat().st_size < 1_200_000
    assert [item["id"] for item in packaged["geometries"]] == [item["id"] for item in generated["geometries"]]
    for name in ("left", "center", "right"):
        np.testing.assert_allclose(packaged["poses"][name]["geoms"], generated["poses"][name]["geoms"], atol=0.002)
        np.testing.assert_allclose(packaged["poses"][name]["nozzle"], generated["poses"][name]["nozzle"], atol=0.002)
    assert packaged["walk"]["leg_indices"] == generated["walk"]["leg_indices"]
    for name in ("short", "long"):
        source = generated["walk"]["profiles"][name]
        saved = packaged["walk"]["profiles"][name]
        assert saved["distance"] == source["distance"]
        for saved_frame, source_frame in zip(saved["frames"], source["frames"], strict=True):
            np.testing.assert_allclose(saved_frame["geoms"], source_frame["geoms"], atol=0.002)
            np.testing.assert_allclose(saved_frame["feet"], source_frame["feet"], atol=0.002)
            assert saved_frame["stance"] == source_frame["stance"]
    for geometry in packaged["geometries"]:
        if geometry["type"] == "mesh":
            mesh = packaged["meshes"][str(geometry["mesh"])]
            assert len(mesh["vertices"]) % 3 == 0
            assert len(mesh["indices"]) % 3 == 0
            assert min(mesh["indices"]) >= 0
            assert max(mesh["indices"]) < len(mesh["vertices"]) // 3
