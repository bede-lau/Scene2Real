"""Live acceptance checks against a running Scene2Real server (real Cosmos / W&B / MuJoCo).

    python scripts/acceptance.py --base http://localhost:8090 --clip-id <id> [--zone right_rack] [--repeats 3]
    python scripts/acceptance.py --base http://localhost:8091 --clip-id <id> --expect-service-failure

Writes a JSON summary to stdout; exit code 0 only if every check passed.
"""
import argparse
import json
import sys
import time

import requests


def post(base, path, **kw):
    r = requests.post(base + path, timeout=600, **kw)
    if r.status_code >= 400:
        return {"_http": r.status_code, **(r.json() if r.headers.get("content-type", "").startswith("application/json") else {})}
    return r.json()


def new_run(base, clip_id):
    return post(base, "/api/runs", json={"clip_id": clip_id})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8090")
    ap.add_argument("--clip-id", required=True)
    ap.add_argument("--zone", default=None, help="zone to confirm (default: Cosmos suggested zone)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--expect-service-failure", action="store_true")
    a = ap.parse_args()
    b, checks = a.base.rstrip("/"), []

    def check(name, ok, **info):
        checks.append({"check": name, "pass": bool(ok), **info})
        print(("PASS " if ok else "FAIL ") + name, json.dumps(info)[:300], file=sys.stderr)

    if a.expect_service_failure:
        run = new_run(b, a.clip_id)
        run = post(b, f"/api/runs/{run['run_id']}/analyse")
        err = run.get("error") or {}
        check("service failure exposes retry", run.get("state") == "failed" and err.get("retryable") is True,
              state=run.get("state"), error=err)
        blocked = post(b, f"/api/runs/{run['run_id']}/scene")
        check("failed analysis blocks scene", blocked.get("_http") == 409, resp=blocked)
        print(json.dumps(checks, indent=2))
        sys.exit(0 if all(c["pass"] for c in checks) else 1)

    # 1. Real analysis -> confirm -> scene -> run, then reset/run repeats on the same scene.
    run = new_run(b, a.clip_id)
    rid = run["run_id"]
    t = time.time()
    run = post(b, f"/api/runs/{rid}/analyse")
    fires = (run.get("observations") or {}).get("fire_sources") or []
    check("real Cosmos analysis found fire", run.get("state") == "analysed" and fires and not run["analysis"].get("cached"),
          run_id=rid, model=run.get("model_id"), fires=fires, latency_s=round(time.time() - t, 2))
    if not fires:
        print(json.dumps(checks, indent=2)); sys.exit(1)
    fire = fires[0]
    zone = a.zone or fire.get("suggested_zone") or "aisle_center"
    run = post(b, f"/api/runs/{rid}/confirm", json={"fire_id": fire["id"], "zone": zone})
    check("target confirmed", run.get("state") == "confirmed", target=run.get("confirmed_target"))
    run = post(b, f"/api/runs/{rid}/scene")
    check("scene + plan ready", run.get("state") == "scene_ready", instruction=run.get("instruction"), skill=run.get("skill"))
    results = []
    for i in range(1 + a.repeats):
        if i:
            post(b, f"/api/runs/{rid}/reset")
        run = post(b, f"/api/runs/{rid}/run")
        m = run.get("metrics") or {}
        results.append(m)
        check(f"simulation run {i + 1} success", run.get("state") == "completed" and m.get("success") is True,
              angle_final=m.get("angle_error_deg_final"), hold_s=m.get("hold_s"), collisions=m.get("unintended_collision_count"))
    check("replay identical", all(r == results[0] for r in results))
    check("telemetry recorded", True, telemetry=run.get("telemetry"), timings=run.get("timings_s"))

    # 2. Unreachable target blocks execution.
    run2 = new_run(b, a.clip_id)
    rid2 = run2["run_id"]
    run2 = post(b, f"/api/runs/{rid2}/analyse")
    f2 = ((run2.get("observations") or {}).get("fire_sources") or [{}])[0]
    if run2.get("state") == "analysed":
        post(b, f"/api/runs/{rid2}/confirm", json={"fire_id": f2["id"], "zone": "behind_robot"})
        run2 = post(b, f"/api/runs/{rid2}/scene")
        check("unreachable target blocked", run2.get("state") == "blocked", error=run2.get("error"))
        r = post(b, f"/api/runs/{rid2}/run")
        check("blocked run refused", r.get("_http") == 409, resp=r)
    else:
        check("unreachable target blocked", False, note="second analysis did not return fire", state=run2.get("state"))

    print(json.dumps(checks, indent=2))
    sys.exit(0 if all(c["pass"] for c in checks) else 1)


if __name__ == "__main__":
    main()
