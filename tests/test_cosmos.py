"""Regression tests for Cosmos observation coordinates and scene details."""

import pytest

from scene2real import cosmos


@pytest.fixture
def native_observation():
    return {
        "fire_sources": [{
            "id": "F1",
            "timestamps_s": [1, 2],
            "bbox_2d": [620, 250, 900, 750],
            "description": "Flames around stacked boxes",
            "location_description": "lower right, beside the rack",
            "burning_object": "cardboard boxes",
            "smoke_description": "dark smoke rising above the boxes",
            "nearby_objects": ["metal rack", "pallet"],
        }],
        "scene_description": "A warehouse aisle with storage racks",
        "cause": None,
        "scale": None,
        "depth_m": None,
        "unknowns": [],
    }


def test_native_bbox_and_scene_details_are_preserved(native_observation):
    observation = cosmos.validate(native_observation, duration_s=3)
    fire = observation["fire_sources"][0]

    assert fire["bbox_normalized"] == pytest.approx([0.62, 0.25, 0.9, 0.75])
    assert fire["bbox_source_scale"] == "0-1000"
    assert fire["image_center_normalized"] == pytest.approx([0.76, 0.5])
    assert fire["location_description"] == "lower right, beside the rack"
    assert fire["burning_object"] == "cardboard boxes"
    assert fire["smoke_description"] == "dark smoke rising above the boxes"
    assert fire["nearby_objects"] == ["metal rack", "pallet"]
    assert observation["scene_description"] == "A warehouse aisle with storage racks"


def test_legacy_normalized_bbox_without_optional_fields():
    observation = cosmos.validate({
        "fire_sources": [{"id": "F1", "timestamps_s": [1],
                          "bbox_normalized": [0.1, 0.2, 0.4, 0.8]}]
    }, duration_s=3)
    fire = observation["fire_sources"][0]
    assert fire["bbox_normalized"] == pytest.approx([0.1, 0.2, 0.4, 0.8])
    assert fire["bbox_source_scale"] == "0-1"
    assert fire["image_center_normalized"] == pytest.approx([0.25, 0.5])


@pytest.mark.parametrize("bbox", [
    [-1, 0, 100, 100], [0, 0, 1001, 100],
    [100, 0, 100, 100], [200, 0, 100, 100],
    [0, 500, 100, 400], [0, 0, 100], [0, 0, True, 100],
])
def test_invalid_native_bbox_rejected(native_observation, bbox):
    native_observation["fire_sources"][0]["bbox_2d"] = bbox
    with pytest.raises(cosmos.InvalidOutput):
        cosmos.validate(native_observation, duration_s=3)


@pytest.mark.parametrize("source_scale", [None, "0-1000"])
def test_mislabeled_thousand_scale_bbox_is_rejected(native_observation, source_scale):
    fire = native_observation["fire_sources"][0]
    fire["bbox_normalized"] = fire.pop("bbox_2d")
    fire["bbox_source_scale"] = source_scale
    with pytest.raises(cosmos.InvalidOutput):
        cosmos.validate(native_observation, duration_s=3)


def test_ambiguous_coordinate_fields_are_rejected(native_observation):
    native_observation["fire_sources"][0]["bbox_normalized"] = [0.1, 0.2, 0.4, 0.8]
    with pytest.raises(cosmos.InvalidOutput):
        cosmos.validate(native_observation, duration_s=3)


@pytest.mark.parametrize("field,value", [
    ("location_description", 12), ("burning_object", ["boxes"]),
    ("smoke_description", False), ("nearby_objects", "pallet"),
    ("nearby_objects", ["pallet", 12]),
])
def test_invalid_fire_detail_types_are_rejected(native_observation, field, value):
    native_observation["fire_sources"][0][field] = value
    with pytest.raises(cosmos.InvalidOutput):
        cosmos.validate(native_observation, duration_s=3)


def test_invalid_scene_description_type_is_rejected(native_observation):
    native_observation["scene_description"] = ["warehouse"]
    with pytest.raises(cosmos.InvalidOutput):
        cosmos.validate(native_observation, duration_s=3)


def test_uncalibrated_depth_is_discarded(native_observation):
    native_observation["depth_m"] = 12
    observation = cosmos.validate(native_observation, duration_s=3)
    assert observation["depth_m"] is None
    assert "depth" in observation["unknowns"] or "depth_m" in observation["unknowns"]
