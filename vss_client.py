"""Thin client for the NVIDIA VSS video-summarization API (Cosmos VLM).

Default base URL assumes an SSH tunnel to the team VM:
    ssh -N -L 38111:localhost:38111 team-vm
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("VSS_BASE_URL", "http://localhost:38111").rstrip("/")
HEADERS = {"Authorization": f"Bearer {os.getenv('VSS_API_KEY', '')}"} if os.getenv("VSS_API_KEY") else {}


def ready() -> bool:
    return requests.get(f"{BASE}/v1/ready", headers=HEADERS, timeout=10).ok


def models() -> list[str]:
    r = requests.get(f"{BASE}/models", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return [m["id"] for m in r.json()["data"]]


def summarize(url: str, prompt: str = "", scenario: str = "general", events: list[str] | None = None,
              chunk_duration: int = 30, model: str | None = None) -> str:
    body = {
        "model": model or models()[0],
        "scenario": scenario,
        "events": events or [],
        "url": url,
        "prompt": prompt,
        "chunk_duration": chunk_duration,
    }
    r = requests.post(f"{BASE}/v1/summarize", json=body, headers=HEADERS, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


if __name__ == "__main__":
    print("ready:", ready())
    print("models:", models())
