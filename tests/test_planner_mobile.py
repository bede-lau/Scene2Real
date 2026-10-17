"""Astra attribution, exact target coverage, bounded settings and failure handling."""
import copy
import json

import pytest

from scene2real import planner


TARGETS = [{"fire_id": "T1", "zone": "left_rack", "slot": 0},
           {"fire_id": "T2", "zone": "right_rack", "slot": 0}]
PLAN = {"instruction": "Leave the charging station and spray T1, then T2.",
        "skill": {"name": "mobile_suppress_demo", "target_ids": ["T1", "T2"]},
        "scene_settings": {"template_id": "wh_mobile_v1", "route_profile": "aisle_safe",
                           "walk_speed_m_s": 0.6, "spray_profile": "water_demo", "spray_duration_s": 4.0}}


@pytest.mark.parametrize("ids", [[], ["T1"], ["T1", "T1"], ["T1", "T9"], ["T1", "T2", "T3"]])
def test_astra_plan_requires_every_target_exactly_once(ids):
    plan = copy.deepcopy(PLAN)
    plan["skill"]["target_ids"] = ids
    with pytest.raises(planner.PlanInvalid, match="exactly once"):
        planner.validate_mobile_payload(plan, TARGETS)


@pytest.mark.parametrize("key,value", [("walk_speed_m_s", float("nan")), ("walk_speed_m_s", True),
                                       ("walk_speed_m_s", 9), ("spray_duration_s", 0),
                                       ("route_profile", "teleport")])
def test_astra_plan_rejects_unsafe_scene_settings(key, value):
    plan = copy.deepcopy(PLAN)
    plan["scene_settings"][key] = value
    with pytest.raises(planner.PlanInvalid):
        planner.validate_mobile_payload(plan, TARGETS)


def test_live_provider_boundary_has_model_provenance_and_no_fixture_truth(monkeypatch):
    import requests
    captured = {}
    monkeypatch.setattr(planner.config, "get", lambda key: "test-key")

    class Response:
        status_code = 200

        def json(self):
            return {"status": "completed", "model": "gpt-6-astra",
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(PLAN)}]}]}

    def provider(url, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr(requests, "post", provider)
    evidence = {"scene_description": "warehouse aisle", "fire_sources": [{"id": "V1:F1", "view_id": "V1",
                "description": "flames beside a rack", "ground_truth": "must not enter inference"}],
                "expected_fire_count": 999, "seed": 123, "world_positions": [[1, 2, 3]]}
    evidence["fire_sources"].append({"id": "V1:F9", "description": "excluded false positive"})
    targets = copy.deepcopy(TARGETS)
    targets[0].update(members=["V1:F1"], image_evidence=[evidence["fire_sources"][0]])
    targets[1].update(members=["V2:F1"], image_evidence=[])
    instruction, skill, settings = planner.make_mobile_plan(targets, evidence)
    assert captured["model"] == "gpt-6-astra"
    assert captured["text"]["format"]["strict"] is True
    assert "Unitree R1" in captured["instructions"] and "26" in captured["instructions"]
    assert "reduced-control scripted proxy" in captured["instructions"]
    assert instruction["source"] == "openai" and instruction["model_id"] == "gpt-6-astra"
    assert instruction["raw_plan"] == PLAN
    assert skill == PLAN["skill"] and settings["walk_speed_m_s"] == 0.6
    assert "ground_truth" not in captured["input"] and "expected_fire_count" not in captured["input"]
    assert "world_positions" not in captured["input"] and '"seed"' not in captured["input"]
    payload = json.loads(captured["input"])
    assert payload["confirmed_targets"][0]["members"] == ["V1:F1"]
    assert payload["confirmed_targets"][0]["image_evidence"][0]["id"] == "V1:F1"
    assert "excluded false positive" not in captured["input"] and "V1:F9" not in captured["input"]


@pytest.mark.parametrize("status", [401, 429, 500])
def test_astra_failure_has_no_fallback_or_provider_secret(monkeypatch, status):
    import requests
    monkeypatch.setattr(planner.config, "get", lambda key: "test-key")

    class Response:
        status_code = status
        text = "do not disclose provider request headers or credentials"

    monkeypatch.setattr(requests, "post", lambda *a, **kw: Response())
    with pytest.raises(planner.PlannerUnavailable, match=f"HTTP {status}") as failure:
        planner.make_mobile_plan(TARGETS, {})
    assert "test-key" not in str(failure.value) and Response.text not in str(failure.value)


def test_blank_astra_instruction_is_not_executable():
    plan = copy.deepcopy(PLAN)
    plan["instruction"] = "  "
    with pytest.raises(planner.PlanInvalid, match="nonempty"):
        planner.validate_mobile_payload(plan, TARGETS)


def test_astra_payload_includes_reviewed_view_uncertainty_without_excluded_sources(monkeypatch):
    import requests
    captured = {}
    monkeypatch.setattr(planner.config, "get", lambda key: "test-key")
    class Response:
        status_code = 200
        def json(self):
            return {"status": "completed", "model": "gpt-6-astra", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(PLAN)}]}]}
    def provider(url, **kwargs):
        captured.update(kwargs["json"])
        return Response()
    monkeypatch.setattr(requests, "post", provider)
    reviewed_fire = {"id": "V2:F1", "view_id": "V2", "description": "partly occluded fire"}
    evidence = {"fire_sources": [reviewed_fire, {"id": "V1:F9", "view_id": "V1", "description": "excluded false positive"}],
                "unknowns": ["unrelated V1 uncertainty", "fire identity"],
                "view_unknowns": [{"view_id": "V1", "unknowns": ["unrelated V1 uncertainty"]},
                                  {"view_id": "V2", "unknowns": ["occluded", "fire identity"]}]}
    targets = copy.deepcopy(TARGETS)
    targets[0].update(members=["V2:F1"], image_evidence=[reviewed_fire])
    targets[1].update(members=[], image_evidence=[])
    planner.make_mobile_plan(targets, evidence)
    payload = json.loads(captured["input"])
    assert payload["confirmed_targets"][0]["view_unknowns"] == [{"view_id": "V2", "unknowns": ["occluded", "fire identity"]}]
    assert payload["visual_evidence"]["view_unknowns"] == [{"view_id": "V2", "unknowns": ["occluded", "fire identity"]}]
    assert "fire identity" in payload["visual_evidence"]["unknowns"]
    assert "V1:F9" not in captured["input"] and "excluded false positive" not in captured["input"]
    assert "unrelated V1 uncertainty" not in captured["input"]
