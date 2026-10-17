"""Instruction/skill planner via W&B Inference (OpenAI-compatible), deterministic fallback."""
import json
import time

from . import config

PROMPT_ID = "plan_v1"


class PlanInvalid(Exception):
    pass


def _fallback(fire_id):
    return {"instruction": f"Aim the attached extinguisher at {fire_id}",
            "skill": {"name": "aim_spray_demo", "target_id": fire_id}}


@config.weave_op
def call_wandb(fire_id, zone, description, supported):
    from openai import OpenAI
    key = config.get("WANDB_API_KEY")
    if not key:
        raise RuntimeError("WANDB_API_KEY missing")
    client = OpenAI(base_url=config.WANDB_BASE, api_key=key, timeout=30,
                    default_headers={"OpenAI-Project": config.wandb_project()})
    prompt = (
        "You plan a robot action for a simulated warehouse fire response. Confirmed fire target: "
        f"id={fire_id}, zone={zone}, observed: {description or 'n/a'}. "
        "Image coordinates and visual relationships are evidence only. The confirmed zone uses an authored "
        "simulation anchor; metric distance, scale and robot pose are not measured from the clip. "
        f"Supported skills: {sorted(supported)}. "
        'Reply with ONLY JSON: {"instruction": "<one short imperative sentence for a fixed-base humanoid holding an attached extinguisher; name the fire id>", "skill": {"name": "<supported skill>", "target_id": "<fire id>"}}')
    last = None
    for model in config.PLANNER_MODELS:
        try:
            r = client.chat.completions.create(model=model, temperature=0,
                                               messages=[{"role": "user", "content": prompt}], max_tokens=300)
            text = r.choices[0].message.content or ""
            from .cosmos import _json_candidates
            for cand in _json_candidates(text):
                try:
                    obj = json.loads(cand)
                except ValueError:
                    continue
                if isinstance(obj, dict) and "skill" in obj:
                    return obj, model
            last = RuntimeError(f"{model}: no JSON plan in reply")
        except Exception as e:  # noqa: BLE001
            last = e
    raise last or RuntimeError("no planner model available")


def make_plan(fire_id, zone, description=""):
    """Returns (instruction_dict, skill_dict). instruction has source wandb|fallback."""
    from . import sim
    t0 = time.time()
    try:
        plan, model = call_wandb(fire_id, zone, description, sorted(sim.SUPPORTED_SKILLS))
        src, note = "wandb", None
    except Exception as e:  # noqa: BLE001
        plan, model, src, note = _fallback(fire_id), None, "fallback", f"{type(e).__name__}: {str(e)[:100]}"
    ins = {"text": str((plan or {}).get("instruction") or ""), "source": src, "model_id": model,
           "prompt_id": PROMPT_ID, "latency_s": round(time.time() - t0, 2)}
    if note:
        ins["fallback_reason"] = note
    skill = (plan or {}).get("skill")
    return ins, skill


def validate_plan(skill, fire_id, scene_obj):
    from . import scene as scene_mod, sim
    if not isinstance(skill, dict) or skill.get("name") not in sim.SUPPORTED_SKILLS:
        raise PlanInvalid(f"Planned skill {skill.get('name') if isinstance(skill, dict) else skill!r} is not supported "
                          f"(supported: {sorted(sim.SUPPORTED_SKILLS)})")
    if skill.get("target_id") != fire_id:
        raise PlanInvalid(f"Planned target {skill.get('target_id')!r} does not match confirmed fire {fire_id!r}")
    ok, why = scene_mod.check_reachable(scene_obj, fire_id)
    if not ok:
        raise PlanInvalid(f"Target not reachable: {why}")
    return {"name": skill["name"], "target_id": skill["target_id"]}
