from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from wsctl.core.errors import ValidationError
from wsctl.services.entities import create_entity
from wsctl.services.workspace import create_project, init_workspace
from wsctl.storage.documents import load_yaml, parse_frontmatter
from wsctl.storage.index import rebuild


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("\0".join(parts).encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-LEGACY-{digest}"


def _frontmatter_or_text(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        try:
            return parse_frontmatter(text)
        except Exception:
            pass
    return {}, text


def _legacy_status(value: Any, allowed: set[str], default: str) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in allowed else default


def preview_legacy(
    *,
    source: Path,
    out: Path,
    project_id: str | None = None,
    include_knowledge: bool = True,
    include_evidence: bool = True,
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    out = out.expanduser().resolve()
    projects_path = source / "management" / "projects.yaml"
    if not projects_path.is_file():
        raise ValidationError(f"legacy workspace has no management/projects.yaml: {source}")

    init_workspace(out, name=f"legacy-preview-{source.name}", force=True)
    registry = load_yaml(projects_path)
    entries = registry.get("projects", [])
    if not isinstance(entries, list):
        raise ValidationError("management/projects.yaml projects must be a list")

    mapped_projects: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        current_id = str(entry.get("id") or "")
        if project_id and current_id != project_id:
            continue
        manifest_path = source / str(entry.get("manifest", ""))
        manifest = load_yaml(manifest_path)
        if not isinstance(manifest, dict):
            continue
        platforms = manifest.get("platforms", {})
        platform_ids = list(platforms) if isinstance(platforms, dict) else []
        project = create_project(
            out,
            project_id=current_id,
            name=str(manifest.get("name") or current_id),
            status=str(manifest.get("status") or "active"),
            tags=[str(manifest.get("line"))] if manifest.get("line") else [],
            legacy={
                "source_root": str(source),
                "manifest": str(manifest_path.relative_to(source)),
                "platforms": platform_ids,
                "profiles": manifest.get("profiles", []),
                "test_tiers": manifest.get("test_tiers", []),
                "board_profile": manifest.get("board_profile"),
                "docs": manifest.get("docs", []),
            },
        )
        mapped_projects.append(project)

    knowledge_count = 0
    decision_count = 0
    evidence_count = 0
    if include_knowledge:
        for path in sorted((source / "knowledge").rglob("*.md")):
            if path.name.lower() == "readme.md" or "adr" in path.parts:
                continue
            metadata, body = _frontmatter_or_text(path)
            relative = str(path.relative_to(source))
            entity = create_entity(
                out,
                "knowledge",
                title=str(metadata.get("title") or path.stem),
                body=body,
                status=_legacy_status(
                    metadata.get("status"), {"draft", "verified", "stale", "deprecated"}, "draft"
                ),
                tags=metadata.get("tags") if isinstance(metadata.get("tags"), list) else [],
                source_id=str(metadata.get("id") or path.stem),
                legacy_path=relative,
            )
            knowledge_count += 1

        for path in sorted((source / "knowledge" / "adr").glob("ADR-*.md")):
            metadata, body = _frontmatter_or_text(path)
            create_entity(
                out,
                "decision",
                title=str(metadata.get("title") or path.stem),
                body=body,
                status=_legacy_status(
                    metadata.get("decision_status"),
                    {"proposed", "accepted", "rejected", "superseded"},
                    "accepted" if metadata.get("decision_status") == "accepted" else "proposed",
                ),
                tags=metadata.get("tags") if isinstance(metadata.get("tags"), list) else [],
                source_id=str(metadata.get("id") or path.stem),
                legacy_path=str(path.relative_to(source)),
            )
            decision_count += 1

    if include_evidence:
        for project in mapped_projects:
            current_id = str(project["id"])
            evidence_dir = source / "products" / current_id / "evidence"
            if not evidence_dir.is_dir():
                continue
            for path in sorted(evidence_dir.glob("*.md")):
                metadata, body = _frontmatter_or_text(path)
                create_entity(
                    out,
                    "evidence",
                    title=str(metadata.get("title") or path.stem),
                    body=body,
                    project=current_id,
                    status="captured",
                    tags=["legacy-evidence"],
                    uri=str(path.relative_to(source)),
                    source_id=str(metadata.get("id") or path.stem),
                    legacy_path=str(path.relative_to(source)),
                )
                evidence_count += 1

        for project in mapped_projects:
            create_entity(
                out,
                "task",
                title=f"预演：将 {project['id']} 工作流迁入通用 wsctl 管理面",
                body=(
                    "这是由 legacy preview 生成的演示任务。\n\n"
                    "验收标准：\n"
                    "- 能在 `.wsctl/` 中读取项目、知识、决策和证据；\n"
                    "- 能通过 CLI 和 MCP 生成任务上下文；\n"
                    "- 不修改原始工作区。\n"
                ),
                project=str(project["id"]),
                status="todo",
                priority="medium",
                tags=["preview", "migration"],
            )

    index_result = rebuild(out)
    return {
        "ok": True,
        "source": str(source),
        "out": str(out),
        "projects": len(mapped_projects),
        "knowledge": knowledge_count,
        "decisions": decision_count,
        "evidence": evidence_count,
        "index": index_result,
    }
