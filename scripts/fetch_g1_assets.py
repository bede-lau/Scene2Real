#!/usr/bin/env python3
"""Fetch only the pinned BSD-3-Clause Menagerie G1 model and its mesh dependencies."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

COMMIT = "62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35"
BASE = f"https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/{COMMIT}/unitree_g1/"
DEST = Path(__file__).resolve().parents[1] / "assets" / "unitree_g1"


def fetch(name: str) -> str:
    path = DEST / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        request = urllib.request.Request(BASE + name, headers={"User-Agent": "Scene2Real-asset-fetcher"})
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read()
        path.write_bytes(payload)
    return name


def main() -> None:
    fetch("g1.xml")
    root = ET.parse(DEST / "g1.xml").getroot()
    names = ["LICENSE", "README.md", "CHANGELOG.md"]
    names += ["assets/" + mesh.attrib["file"] for mesh in root.findall("asset/mesh")]
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch, names))
    hashes = {name: hashlib.sha256((DEST / name).read_bytes()).hexdigest() for name in ["g1.xml", *names]}
    (DEST / "SOURCE.json").write_text(json.dumps({
        "repository": "https://github.com/google-deepmind/mujoco_menagerie",
        "commit": COMMIT, "directory": "unitree_g1", "license": "BSD-3-Clause",
        "files_sha256": hashes,
    }, indent=2) + "\n")
    print(f"Pinned G1: {len(hashes)} files, {sum((DEST / n).stat().st_size for n in hashes):,} bytes")


if __name__ == "__main__":
    main()
