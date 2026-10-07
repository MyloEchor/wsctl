from __future__ import annotations

from pathlib import Path
from typing import Any

from wsctl.core.errors import NotFoundError, ValidationError
from wsctl.core.models import (
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    ENTITY_TYPES,
    TYPE_DIRS,
    new_id,
    normalize_tags,
    utc_now,
    validate_entity_metadata,
)
from wsctl.services.workspace import get_project, load_workspace
from wsctl.storage.documents import load_document, write_document


def entity_dir(root: Path, kind: str) -> Path:
    if kind not in ENTITY_TYPES:
        raise ValidationError(f"unsupported entity type: {kind}")
    return root.expanduser().resolve() / ".wsctl" / TYPE_DIRS[kind]


def entity_path(root: Path, kind: str, entity_id: str) -> Path:
    return entity_dir(root, kind) / f"{entity_id}.md"


def get_entity(root: Path, kind: str, entity_id: str) -> dict[str, Any]:
    path = entity_path(root, kind, entity_id)
    if not path.is_file():
        raise NotFoundError(f"{kind} not found: {entity_id}")
    metadata, body = load_document(path)
    return {"metadata": metadata, "body": body, "path": str(path.relative_to(root))}


def list_entities(
    root: Path,
    kind: str,
    *,
    project: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(entity_dir(root, kind).glob("*.md")):
        metadata, body = load_document(path)
        if project and metadata.get("project") != project:
            continue
        if status and metadata.get("status") != status:
            continue
        if not include_archived and (
            metadata.get("archived") is True or metadata.get("status") == "archived"
        ):
            continue
        items.append(
            {
                **metadata,
                "body": body,
                "path": str(path.relative_to(root)),
            }
        )
    items.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return items[:limit] if limit else items


def _validate_project(root: Path, value: str | None) -> None:
    if value:
        get_project(root, value)


def create_entity(
    root: Path,
    kind: str,
    *,
    title: str,
    body: str = "",
    project: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    related: list[str] | None = None,
    uri: str | None = None,
    source_id: str | None = None,
    legacy_path: str | None = None,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    load_workspace(root)
    _validate_project(root, project)
    entity_id = new_id(kind)
    now = utc_now()
    metadata: dict[str, Any] = {
        "id": entity_id,
        "type": kind,
        "title": title,
        "status": status or DEFAULT_STATUS[kind],
        "project": project,
        "tags": normalize_tags(tags),
        "related": related or [],
        "created_at": now,
        "updated_at": now,
        "archived": False,
    }
    if kind == "task":
        metadata["priority"] = priority or DEFAULT_PRIORITY
        metadata["owner"] = None
    if kind == "evidence":
        metadata["uri"] = uri
    if source_id:
        metadata["source_id"] = source_id
    if legacy_path:
        metadata["legacy_path"] = legacy_path
    validate_entity_metadata(kind, metadata)
    write_document(entity_path(root, kind, entity_id), metadata, body)
    return {"metadata": metadata, "body": body}


def update_entity(
    root: Path,
    kind: str,
    entity_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    project: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    related: list[str] | None = None,
    uri: str | None = None,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    path = entity_path(root, kind, entity_id)
    if not path.is_file():
        raise NotFoundError(f"{kind} not found: {entity_id}")
    metadata, current_body = load_document(path)
    if title is not None:
        metadata["title"] = title
    if project is not None:
        _validate_project(root, project)
        metadata["project"] = project
    if status is not None:
        metadata["status"] = status
    if priority is not None:
        metadata["priority"] = priority
    if tags is not None:
        metadata["tags"] = normalize_tags(tags)
    if related is not None:
        metadata["related"] = related
    if uri is not None and kind == "evidence":
        metadata["uri"] = uri
    metadata["updated_at"] = utc_now()
    validate_entity_metadata(kind, metadata)
    next_body = current_body if body is None else body
    write_document(path, metadata, next_body)
    return {"metadata": metadata, "body": next_body}


def archive_entity(root: Path, kind: str, entity_id: str) -> dict[str, Any]:
    root = root.expanduser().resolve()
    path = entity_path(root, kind, entity_id)
    if not path.is_file():
        raise NotFoundError(f"{kind} not found: {entity_id}")
    metadata, body = load_document(path)
    metadata["status"] = "archived"
    metadata["archived"] = True
    metadata["updated_at"] = utc_now()
    write_document(path, metadata, body)
    return {"metadata": metadata, "body": body}


def purge_entity(root: Path, kind: str, entity_id: str, *, confirm: bool) -> dict[str, Any]:
    if not confirm:
        raise ValidationError("purge requires confirm=True")
    path = entity_path(root, kind, entity_id)
    if not path.is_file():
        raise NotFoundError(f"{kind} not found: {entity_id}")
    path.unlink()
    return {"ok": True, "purged": entity_id, "kind": kind}

