from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from wsctl.core.errors import NotFoundError, ValidationError
from wsctl.storage.documents import load_yaml, write_yaml_atomic


def registry_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("WSCTL_REGISTRY")
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return (base / "wsctl" / "workspaces.yaml").resolve()


def load_registry(path: Path | None = None) -> dict[str, Any]:
    target = path or registry_path()
    if not target.is_file():
        return {"schema_version": 1, "workspaces": []}
    data = load_yaml(target)
    if not isinstance(data, dict):
        raise ValidationError("registry must be a mapping")
    if not isinstance(data.get("workspaces"), list):
        raise ValidationError("registry.workspaces must be a list")
    return data


def save_registry(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or registry_path()
    write_yaml_atomic(target, data)


def add_workspace(
    root: Path,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    allow_write: bool = False,
    registry: Path | None = None,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    metadata_path = root / ".wsctl" / "workspace.yaml"
    if not metadata_path.is_file():
        raise ValidationError(f"not a wsctl workspace: {root}")
    metadata = load_yaml(metadata_path)
    workspace_id = workspace_id or str(metadata.get("id") or root.name)
    data = load_registry(registry)
    entry = {
        "id": workspace_id,
        "name": name or str(metadata.get("name") or workspace_id),
        "root": str(root),
        "allow_write": bool(allow_write),
    }
    existing = {
        str(item.get("id")): item
        for item in data["workspaces"]
        if isinstance(item, dict)
    }
    existing[workspace_id] = entry
    data["workspaces"] = list(existing.values())
    save_registry(data, registry)
    return entry


def list_workspaces(registry: Path | None = None) -> list[dict[str, Any]]:
    return [
        item
        for item in load_registry(registry)["workspaces"]
        if isinstance(item, dict)
    ]


def resolve_workspace(
    selector: str | None = None,
    *,
    registry: Path | None = None,
    cwd: Path | None = None,
) -> Path:
    if selector:
        candidate = Path(selector).expanduser()
        if candidate.is_dir() and (candidate / ".wsctl" / "workspace.yaml").is_file():
            return candidate.resolve()
        for entry in list_workspaces(registry):
            if str(entry.get("id")) == selector:
                return Path(str(entry["root"])).resolve()
        raise NotFoundError(f"workspace not found: {selector}")

    current = (cwd or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".wsctl" / "workspace.yaml").is_file():
            return candidate

    entries = list_workspaces(registry)
    if len(entries) == 1:
        return Path(str(entries[0]["root"])).resolve()
    if not entries:
        raise NotFoundError("no workspace selected and registry is empty")
    raise ValidationError("multiple workspaces registered; pass workspace id or path")


def write_allowed(workspace: Path, *, registry: Path | None = None) -> bool:
    resolved = workspace.resolve()
    for entry in list_workspaces(registry):
        if Path(str(entry.get("root", ""))).expanduser().resolve() == resolved:
            return bool(entry.get("allow_write"))
    return False

