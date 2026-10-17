#!/usr/bin/env python3
"""Read and verify the commit-pinned upstream bundle without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = SKILL_ROOT / "sources.lock.json"


class BundleError(Exception):
    """A malformed bundle or failed verification."""


def load_lock(root: Path) -> dict[str, Any]:
    try:
        lock = json.loads((root / "sources.lock.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BundleError(f"cannot read sources.lock.json: {error}") from error
    if lock.get("schema_version") != 1 or not isinstance(lock.get("sources"), list):
        raise BundleError("unsupported or malformed sources.lock.json")
    return lock


def bundle_file(root: Path, bundled_path: str) -> Path:
    relative = PurePosixPath(bundled_path)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or relative.parts[0] != "references"
        or len(relative.parts) < 3
        or relative.parts[1] != "upstream"
    ):
        raise BundleError(f"unsafe bundled path in lock: {bundled_path!r}")
    bundle_root = (root / "references" / "upstream").resolve()
    candidate = (root / Path(*relative.parts)).resolve()
    if bundle_root not in candidate.parents:
        raise BundleError(f"bundled path escapes upstream directory: {bundled_path!r}")
    return candidate


def selected_source(lock: dict[str, Any], source_id: str) -> dict[str, Any]:
    matches = [source for source in lock["sources"] if source.get("id") == source_id]
    if len(matches) != 1:
        raise BundleError(f"unknown source: {source_id}")
    return matches[0]


def verify_file(root: Path, file: dict[str, Any]) -> Path:
    path = bundle_file(root, str(file.get("bundled_path", "")))
    if not path.is_file():
        raise BundleError(f"missing: {path}")
    content = path.read_bytes()
    if len(content) != file.get("bytes"):
        raise BundleError(f"size mismatch: {path}")
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != file.get("sha256"):
        raise BundleError(f"sha256 mismatch: {path}")
    return path


def command_list(args: argparse.Namespace, root: Path) -> int:
    lock = load_lock(root)
    sources = [selected_source(lock, args.source)] if args.source else lock["sources"]
    for source in sources:
        for file in source.get("files", []):
            path = bundle_file(root, str(file.get("bundled_path", "")))
            # A bounded, root-relative path is safe to display even for unverified files.
            print(f"{source['id']}\t{file['path']}\t{path.relative_to(root).as_posix()}")
    return 0


def command_locate(args: argparse.Namespace, root: Path) -> int:
    source = selected_source(load_lock(root), args.source)
    matches = [file for file in source.get("files", []) if file.get("path") == args.path]
    if len(matches) != 1:
        raise BundleError(f"unknown path for {args.source}: {args.path}")
    print(verify_file(root, matches[0]))
    return 0


def command_verify(_: argparse.Namespace, root: Path) -> int:
    lock = load_lock(root)
    count = 0
    for source in lock["sources"]:
        if not isinstance(source.get("files"), list):
            raise BundleError(f"malformed files list for {source.get('id')!r}")
        for file in source["files"]:
            verify_file(root, file)
            count += 1
    print(f"verified {count} bundled files")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)
    list_parser = subcommands.add_parser("list", help="list bounded, root-relative bundled paths")
    list_parser.add_argument("--source", help="limit output to one source ID")
    list_parser.set_defaults(handler=command_list)
    locate_parser = subcommands.add_parser("locate", help="verify and print one absolute bundled path")
    locate_parser.add_argument("source", help="source ID")
    locate_parser.add_argument("path", help="original upstream repository path")
    locate_parser.set_defaults(handler=command_locate)
    verify_parser = subcommands.add_parser("verify", help="verify every bundled file against the lock")
    verify_parser.set_defaults(handler=command_verify)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args, SKILL_ROOT)
    except BundleError as error:
        print(f"sources: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
