#!/usr/bin/env python3
"""Artifact-only approval gates for the prd-to-production skill.

This tool deliberately validates files and recorded approvals only.  It cannot
determine whether a design or build is correct, and it never creates an
approval unless an agent supplies text explicitly received from the user.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Iterable


RUNTIME_NAME = ".prd-to-production"
STATE_NAME = "state.json"
CHECKPOINT_NAME = "checkpoint.md"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class WorkflowError(Exception):
    """An expected invalid workflow input or artifact."""


def error(message: str) -> None:
    raise WorkflowError(message)


def project_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        error(f"project root does not exist or is not a directory: {root}")
    return root


def runtime_dir(root: Path) -> Path:
    runtime = root / RUNTIME_NAME
    if runtime.exists() and runtime.is_symlink():
        error(f"runtime directory may not be a symlink: {runtime}")
    return runtime


def state_path(root: Path) -> Path:
    return runtime_dir(root) / STATE_NAME


def artifact_root(root: Path) -> Path:
    """Return the project-local directory that owns workflow artifacts."""
    return runtime_dir(root)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        error(f"missing {label}: {path}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        error(f"invalid JSON in {label}: {exc}")


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        error(f"{label} must be a JSON object")
    return value


def require_string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        error(f"{label} must be a string")
    if nonempty and not value.strip():
        error(f"{label} must not be empty")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        error(f"{label} must be a list")
    return value


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def validate_scalar(value: Any, label: str) -> None:
    if not is_scalar(value):
        error(f"{label} must be a JSON scalar")


def safe_relative_file(root: Path, raw_path: str, label: str) -> Path:
    """Return an existing regular artifact file entirely below root.

    Refusing symlinks (including in parent components) keeps an artifact
    snapshot from reaching outside the selected project root.
    """
    require_string(raw_path, label)
    posix = PurePosixPath(raw_path)
    windows = PureWindowsPath(raw_path)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        error(f"{label} must be a relative path")
    if "\\" in raw_path or any(part in ("", ".", "..") for part in posix.parts):
        error(f"{label} is not a safe relative path")
    candidate = root
    for part in posix.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            error(f"{label} may not use a symlink: {raw_path}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        error(f"{label} does not exist: {raw_path} ({exc})")
    try:
        resolved.relative_to(root)
    except ValueError:
        error(f"{label} escapes the project root: {raw_path}")
    if not resolved.is_file():
        error(f"{label} must name a regular file: {raw_path}")
    return resolved


def safe_design_files(root: Path) -> list[Path]:
    design = root / "design"
    if design.is_symlink():
        error("design directory may not be a symlink")
    if not design.is_dir():
        error("missing design directory")
    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(design, followlinks=False):
        current = Path(directory)
        for name in dirnames:
            if (current / name).is_symlink():
                error(f"design contains a symlink: {(current / name).relative_to(root)}")
        for name in filenames:
            path = current / name
            if path.is_symlink():
                error(f"design contains a symlink: {path.relative_to(root)}")
            if not path.is_file():
                error(f"design contains a non-regular file: {path.relative_to(root)}")
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def snapshot(root: Path, paths: Iterable[Path]) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
    }


def validate_brief(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    brief = safe_relative_file(root, "brief.md", "brief.md")
    try:
        brief_text = brief.read_text(encoding="utf-8")
        if not brief_text.strip():
            error("brief.md must not be empty")
    except UnicodeDecodeError as exc:
        error(f"brief.md must be UTF-8 text: {exc}")

    inventory_path = safe_relative_file(root, "inventory.json", "inventory.json")
    inventory = require_object(read_json(inventory_path, "inventory.json"), "inventory.json")
    if "brief_revision" not in inventory:
        error("inventory.json is missing brief_revision")
    validate_scalar(inventory["brief_revision"], "inventory.json brief_revision")

    requirement_ids = require_list(inventory.get("requirement_ids"), "inventory.json requirement_ids")
    known_ids: set[str] = set()
    for index, requirement_id in enumerate(requirement_ids):
        value = require_string(requirement_id, f"inventory.json requirement_ids[{index}]")
        if value in known_ids:
            error(f"inventory.json has duplicate requirement id: {value}")
        if not re.search(r"(?<![\w-])" + re.escape(value) + r"(?![\w-])", brief_text):
            error(f"brief.md is missing declared requirement id: {value}")
        known_ids.add(value)

    screens = require_list(inventory.get("screens"), "inventory.json screens")
    if not screens:
        error("inventory.json screens must not be empty")
    screen_ids: set[str] = set()
    for index, raw_screen in enumerate(screens):
        screen = require_object(raw_screen, f"inventory.json screens[{index}]")
        screen_id = require_string(screen.get("id"), f"inventory.json screens[{index}].id")
        if screen_id in screen_ids:
            error(f"inventory.json has duplicate screen id: {screen_id}")
        screen_ids.add(screen_id)
        require_string(screen.get("route"), f"inventory.json screens[{index}].route")
        tab = screen.get("tab")
        if tab is not None:
            require_string(tab, f"inventory.json screens[{index}].tab")
        roles = require_list(screen.get("roles"), f"inventory.json screens[{index}].roles")
        for role_index, role in enumerate(roles):
            require_string(role, f"inventory.json screens[{index}].roles[{role_index}]")
        requirements = require_list(
            screen.get("requirements"), f"inventory.json screens[{index}].requirements"
        )
        for requirement_index, requirement in enumerate(requirements):
            requirement_id = require_string(
                requirement,
                f"inventory.json screens[{index}].requirements[{requirement_index}]",
            )
            if requirement_id not in known_ids:
                error(
                    f"inventory.json screen {screen_id} references unknown requirement id: "
                    f"{requirement_id}"
                )
    return inventory, snapshot(root, [brief, inventory_path])


def validate_png(root: Path, raw_path: Any, label: str) -> Path:
    raw_path = require_string(raw_path, label)
    path = safe_relative_file(root, raw_path, label)
    design = root / "design"
    try:
        path.relative_to(design)
    except ValueError:
        error(f"{label} must be stored under design/: {raw_path}")
    try:
        with path.open("rb") as handle:
            magic = handle.read(len(PNG_MAGIC))
    except OSError as exc:
        error(f"cannot read {label}: {exc}")
    if magic != PNG_MAGIC:
        error(f"{label} must be a PNG file: {raw_path}")
    return path


def validate_design(root: Path, inventory: dict[str, Any]) -> dict[str, str]:
    spec = safe_relative_file(root, "design/spec.md", "design/spec.md")
    try:
        if not spec.read_text(encoding="utf-8").strip():
            error("design/spec.md must not be empty")
    except UnicodeDecodeError as exc:
        error(f"design/spec.md must be UTF-8 text: {exc}")
    safe_relative_file(root, "design/index.md", "design/index.md")
    screens_path = safe_relative_file(root, "design/screens.json", "design/screens.json")
    design_data = require_object(read_json(screens_path, "design/screens.json"), "design/screens.json")
    if "revision" not in design_data:
        error("design/screens.json is missing revision")
    validate_scalar(design_data["revision"], "design/screens.json revision")
    design_screens = require_list(design_data.get("screens"), "design/screens.json screens")

    expected_ids = {screen["id"] for screen in inventory["screens"]}
    seen_ids: set[str] = set()
    primary_images: dict[str, str] = {}
    for index, raw_screen in enumerate(design_screens):
        screen = require_object(raw_screen, f"design/screens.json screens[{index}]")
        screen_id = require_string(screen.get("id"), f"design/screens.json screens[{index}].id")
        if screen_id in seen_ids:
            error(f"design/screens.json has duplicate screen id: {screen_id}")
        seen_ids.add(screen_id)
        desktop = require_string(screen.get("desktop"), f"design/screens.json screens[{index}].desktop")
        mobile = require_string(screen.get("mobile"), f"design/screens.json screens[{index}].mobile")
        if desktop == mobile:
            error(f"design/screens.json screen {screen_id} uses the same desktop and mobile image")
        states = require_list(screen.get("states"), f"design/screens.json screens[{index}].states")
        for image_path in (desktop, mobile):
            other_screen = primary_images.get(image_path)
            if other_screen is not None:
                error(
                    "design/screens.json reuses a desktop/mobile image across screens: "
                    f"{image_path} ({other_screen}, {screen_id})"
                )
            primary_images[image_path] = screen_id
        validate_png(root, desktop, f"design/screens.json screen {screen_id} desktop")
        validate_png(root, mobile, f"design/screens.json screen {screen_id} mobile")
        for state_index, state_path in enumerate(states):
            validate_png(
                root,
                state_path,
                f"design/screens.json screen {screen_id} states[{state_index}]",
            )
    if seen_ids != expected_ids:
        missing = sorted(expected_ids - seen_ids)
        unexpected = sorted(seen_ids - expected_ids)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("unknown: " + ", ".join(unexpected))
        error("design/screens.json must represent every inventory screen exactly once (" + "; ".join(details) + ")")
    return snapshot(root, safe_design_files(root))


def default_state() -> dict[str, Any]:
    return {"version": 1, "approvals": {}}


def load_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    state = require_object(read_json(path, "workflow state"), "workflow state")
    approvals = state.get("approvals")
    if not isinstance(approvals, dict):
        error("workflow state approvals must be an object")
    return state


def write_state(root: Path, state: dict[str, Any]) -> None:
    runtime = runtime_dir(root)
    runtime.mkdir(mode=0o700, exist_ok=True)
    if runtime.is_symlink():
        error(f"runtime directory may not be a symlink: {runtime}")
    destination = state_path(root)
    if destination.exists() and destination.is_symlink():
        error(f"workflow state may not be a symlink: {destination}")
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=runtime)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def init(root: Path) -> None:
    runtime = runtime_dir(root)
    runtime.mkdir(mode=0o700, exist_ok=True)
    if runtime.is_symlink():
        error(f"runtime directory may not be a symlink: {runtime}")
    state = runtime / STATE_NAME
    checkpoint = runtime / CHECKPOINT_NAME
    if not state.exists():
        write_state(root, default_state())
    if not checkpoint.exists():
        checkpoint.touch(exist_ok=False)
    print(f"initialized {RUNTIME_NAME} in {root}")


def approval_record(message: str, files: dict[str, str]) -> dict[str, Any]:
    return {
        "approved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "message": message,
        "files": files,
    }


def approval_is_current(
    state: dict[str, Any], stage: str, current_files: dict[str, str]
) -> tuple[bool, str]:
    approval = state.get("approvals", {}).get(stage)
    if not isinstance(approval, dict):
        return False, f"{stage} approval is missing"
    stored_files = approval.get("files")
    if not isinstance(stored_files, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in stored_files.items()
    ):
        return False, f"{stage} approval record is malformed"
    if stored_files == current_files:
        return True, f"{stage} approval is current"
    changed = sorted(set(stored_files) ^ set(current_files))
    changed.extend(
        path for path in sorted(set(stored_files) & set(current_files))
        if stored_files[path] != current_files[path]
    )
    suffix = ", ".join(changed[:3])
    if len(changed) > 3:
        suffix += ", ..."
    return False, f"{stage} approval is stale" + (f" ({suffix})" if suffix else "")


def approve(root: Path, stage: str, message: str) -> None:
    state = load_state(root)
    artifacts = artifact_root(root)
    inventory, brief_files = validate_brief(artifacts)
    if stage == "brief":
        state["approvals"]["brief"] = approval_record(message, brief_files)
        # A brief approval is the design gate. Re-approval intentionally starts
        # that downstream gate again, even when the source files are unchanged.
        state["approvals"].pop("design", None)
    else:
        brief_current, brief_reason = approval_is_current(state, "brief", brief_files)
        if not brief_current:
            error(f"cannot approve design: {brief_reason}")
        design_files = validate_design(artifacts, inventory)
        state["approvals"]["design"] = approval_record(message, design_files)
    write_state(root, state)
    print(f"recorded {stage} approval")


def approval_message(message: str | None, message_file: str | None) -> str:
    if message is not None:
        return require_string(message, "approval message")
    if message_file is None:  # argparse enforces this, but keep the API defensive.
        error("an approval message is required")
    try:
        return require_string(Path(message_file).read_text(encoding="utf-8"), "approval message")
    except (OSError, UnicodeDecodeError) as exc:
        error(f"cannot read approval message file: {exc}")


def artifact_status(root: Path) -> tuple[dict[str, Any] | None, dict[str, str] | None, str | None, dict[str, str] | None, str | None]:
    artifacts = artifact_root(root)
    try:
        inventory, brief_files = validate_brief(artifacts)
        brief_error = None
    except WorkflowError as exc:
        inventory = None
        brief_files = None
        brief_error = str(exc)
    try:
        if inventory is None:
            design_files = None
            design_error = "brief artifacts are invalid"
        else:
            design_files = validate_design(artifacts, inventory)
            design_error = None
    except WorkflowError as exc:
        design_files = None
        design_error = str(exc)
    return inventory, brief_files, brief_error, design_files, design_error


def read_status_state(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return load_state(root), None
    except WorkflowError as exc:
        return None, str(exc)


def check(root: Path, stage: str) -> None:
    if stage == "brief":
        validate_brief(artifact_root(root))
        print("brief artifacts check passed")
        return
    state, state_error = read_status_state(root)
    artifacts = artifact_root(root)
    reasons: list[str] = []
    if state_error:
        reasons.append(state_error)
    try:
        inventory, brief_files = validate_brief(artifacts)
    except WorkflowError as exc:
        inventory = None
        brief_files = None
        reasons.append(str(exc))
    if state is not None and brief_files is not None:
        brief_current, reason = approval_is_current(state, "brief", brief_files)
        if not brief_current:
            reasons.append(reason)
    if stage == "build":
        if inventory is None:
            reasons.append("design artifacts cannot be validated without a valid brief")
        else:
            try:
                design_files = validate_design(artifacts, inventory)
            except WorkflowError as exc:
                design_files = None
                reasons.append(str(exc))
            if state is not None and design_files is not None:
                design_current, reason = approval_is_current(state, "design", design_files)
                if not design_current:
                    reasons.append(reason)
    if reasons:
        error(f"{stage} check failed: " + "; ".join(reasons))
    print(f"{stage} check passed")


def status(root: Path) -> None:
    state, state_error = read_status_state(root)
    _inventory, brief_files, brief_error, design_files, design_error = artifact_status(root)
    lines: list[str] = []
    if state_error:
        lines.append(f"state: blocked — {state_error}")

    if brief_error:
        lines.append(f"brief: blocked — {brief_error}")
        brief_current = False
    elif state is None:
        lines.append("brief: ready for approval (state is unavailable)")
        brief_current = False
    else:
        brief_current, brief_reason = approval_is_current(state, "brief", brief_files or {})
        lines.append("brief: approved" if brief_current else f"brief: ready for approval — {brief_reason}")

    if design_error:
        lines.append(f"design: blocked — {design_error}")
        design_current = False
    elif not brief_current:
        lines.append("design: blocked — current brief approval is required")
        design_current = False
    elif state is None:
        lines.append("design: ready for approval (state is unavailable)")
        design_current = False
    else:
        design_current, design_reason = approval_is_current(state, "design", design_files or {})
        lines.append("design: approved" if design_current else f"design: ready for approval — {design_reason}")

    if brief_current and design_current:
        lines.append("build: ready")
    else:
        blockers = []
        if not brief_current:
            blockers.append("current brief approval")
        if not design_current:
            blockers.append("current design approval")
        lines.append("build: blocked — requires " + " and ".join(blockers))
    print("\n".join(lines))


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__)
    commands = command_parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status"):
        subparser = commands.add_parser(name)
        subparser.add_argument("--root", required=True, help="project root")
    approve_parser = commands.add_parser("approve")
    approve_parser.add_argument("--root", required=True, help="project root")
    approve_parser.add_argument("--stage", choices=("brief", "design"), required=True)
    message_group = approve_parser.add_mutually_exclusive_group(required=True)
    message_group.add_argument(
        "--message",
        help="exact user approval text actually received; never inferred by this tool",
    )
    message_group.add_argument(
        "--message-file",
        help="UTF-8 file containing the exact user approval text actually received",
    )
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--root", required=True, help="project root")
    check_parser.add_argument("--stage", choices=("brief", "design", "build"), required=True)
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = project_root(args.root)
        if args.command == "init":
            init(root)
        elif args.command == "status":
            status(root)
        elif args.command == "approve":
            approve(root, args.stage, approval_message(args.message, args.message_file))
        elif args.command == "check":
            check(root, args.stage)
        else:  # argparse makes this unreachable.
            error(f"unknown command: {args.command}")
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        # Filesystem races and malformed user files should remain actionable,
        # rather than exposing an implementation traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
