from __future__ import annotations

from pathlib import Path
from typing import Any

from wsctl.services.entities import get_entity, list_entities
from wsctl.services.workspace import get_project, load_workspace
from wsctl.storage.index import search


def _summarize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summarized: list[dict[str, Any]] = []
    for item in items:
        current = dict(item)
        body = str(current.pop("body", ""))
        current["excerpt"] = body[:240].strip()
        summarized.append(current)
    return summarized


def _matches_project(item: dict[str, Any], project: str | None) -> bool:
    if not project:
        return True
    item_project = item.get("project")
    return item_project in (None, "", project)


def build_context(
    root: Path,
    *,
    project: str | None = None,
    task: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    workspace = load_workspace(root)
    warnings: list[str] = []
    project_data = get_project(root, project) if project else None
    task_data = get_entity(root, "task", task) if task else None

    knowledge = [
        item
        for item in list_entities(root, "knowledge", include_archived=False)
        if _matches_project(item, project)
    ][:limit]
    decisions = [
        item
        for item in list_entities(root, "decision", include_archived=False)
        if _matches_project(item, project)
    ][:limit]
    evidence = [
        item
        for item in list_entities(root, "evidence", include_archived=False)
        if _matches_project(item, project)
    ][:limit]
    matches = search(root, query, limit=limit) if query else []
    if not knowledge:
        warnings.append("no knowledge entries matched the context request")
    if not decisions:
        warnings.append("no decision records matched the context request")
    return {
        "workspace": workspace,
        "project": project_data,
        "task": task_data,
        "knowledge": _summarize(knowledge),
        "decisions": _summarize(decisions),
        "evidence": _summarize(evidence),
        "search": matches,
        "warnings": warnings,
    }
