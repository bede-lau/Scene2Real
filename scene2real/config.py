"""Configuration: env vars first, then /config/team-28.config (VM). Secrets never leave the server."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(os.environ.get("SCENE2REAL_RUNS_DIR", ROOT / "runs"))
CLIPS_DIR = ROOT / "clips"
STATIC_DIR = ROOT / "static"
CACHE_DIR = ROOT / "cache"
CONFIG_FILE = Path(os.environ.get("TEAM_CONFIG", "/config/team-28.config"))

COSMOS_URL = os.environ.get("COSMOS_URL", "http://166.19.38.112:8001")
YOLO_URL = os.environ.get("YOLO_URL", "http://166.19.38.112:8002")
COSMOS_MODEL = "nvidia/cosmos3-nano-reasoner"
WANDB_BASE = "https://api.inference.wandb.ai/v1"
# small, fast instruct models; first one that responds wins
PLANNER_MODELS = ["meta-llama/Llama-3.1-8B-Instruct", "openai/gpt-oss-20b", "ibm-granite/granite-4.2-8b"]

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MIN_DURATION_S, MAX_DURATION_S = 1.0, 120.0
N_FRAMES = 5  # Cosmos endpoint accepts at most 5 images per prompt
COSMOS_TIMEOUT_S = float(os.environ.get("COSMOS_TIMEOUT_S", "180"))


def _parse_file(path: Path) -> dict:
    out = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


_FILE = _parse_file(CONFIG_FILE)


def get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or _FILE.get(key) or default


def use_cache() -> bool:
    return os.environ.get("SCENE2REAL_USE_CACHE") == "1"


def wandb_project() -> str:
    team, proj = get("WANDB_TEAM"), get("WANDB_PROJECT")
    return f"{team}/{proj}" if team and proj else "vastdata/team-28"


# process-wide telemetry state (set at startup)
TELEMETRY = {"weave": "skipped: not initialised"}


def init_weave() -> str:
    try:
        import weave
        key = get("WANDB_API_KEY")
        if not key:
            raise RuntimeError("WANDB_API_KEY missing")
        os.environ.setdefault("WANDB_API_KEY", key)
        weave.init(wandb_project())
        TELEMETRY["weave"] = "ok"
    except Exception as e:  # noqa: BLE001
        TELEMETRY["weave"] = f"skipped: {type(e).__name__}: {str(e)[:120]}"
    return TELEMETRY["weave"]


def weave_op(fn):
    """@weave.op if weave is importable, else passthrough."""
    try:
        import weave
        return weave.op()(fn)
    except Exception:  # noqa: BLE001
        return fn
