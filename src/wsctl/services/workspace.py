from __future__ import annotations

from pathlib import Path
from typing import Any

from wsctl.core.errors import NotFoundError, ValidationError
from wsctl.core.models import contains_secret_key, slugify, utc_now
from wsctl.storage.documents import load_yaml, write_yaml_atomic

WORKSPACE_FILE = Path(".wsctl/workspace.yaml")
PROJECTS_DIR = Path(".wsctl/projects")


def init_workspace(root: Path, *, name: str | None = None, force: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    metadata_path = root / WORKSPACE_FILE
    if metadata_path.exists() and not force:
        raise ValidationError(f"workspace already initialized: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for relative in (
        ".wsctl/projects",
        ".wsctl/tasks",
        ".wsctl/knowledge",
        ".wsctl/decisions",
        ".wsctl/evidence",
        ".wsctl/templates",
        ".wsctl/.index",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema_version": 1,
        "id": slugify(name or root.name),
        "name": name or root.name,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "default_project": None,
    }
    write_yaml_atomic(metadata_path, metadata)
    (root / ".wsctl/.gitignore").write_text(".index/\n", encoding="utf-8")
    return {"ok": True, "root": str(root), "workspace": metadata}


def load_workspace(root: Path) -> dict[str, Any]:
    metadata_path = root.expanduser().resolve() / WORKSPACE_FILE
    if not metadata_path.is_file():
        raise NotFoundError(f"not a wsctl workspace: {root}")
    metadata = load_yaml(metadata_path)
    if not isinstance(metadata, dict):
        raise ValidationError("workspace.yaml must be a mapping")
    return metadata


def create_project(
    root: Path,
    *,
    project_id: str,
    name: str | None = None,
    status: str = "active",
    tags: list[str] | None = None,
    repos: list[str] | None = None,
    legacy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in {"active", "paused", "archived"}:
        raise ValidationError("project status must be active, paused, or archived")
    root = root.expanduser().resolve()
    load_workspace(root)
    path = root / PROJECTS_DIR / f"{project_id}.yaml"
    if path.exists():
        raise ValidationError(f"project already exists: {project_id}")
    project = {
        "id": project_id,
        "name": name or project_id,
        "status": status,
        "tags": tags or [],
        "repos": repos or [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    if legacy:
        project["legacy"] = legacy
    write_yaml_atomic(path, project)
    return project


def list_projects(root: Path) -> list[dict[str, Any]]:
    root = root.expanduser().resolve()
    load_workspace(root)
    projects: list[dict[str, Any]] = []
    for path in sorted((root / PROJECTS_DIR).glob("*.yaml")):
        data = load_yaml(path)
        if isinstance(data, dict):
            projects.append(data)
    return projects


def get_project(root: Path, project_id: str) -> dict[str, Any]:
    path = root.expanduser().resolve() / PROJECTS_DIR / f"{project_id}.yaml"
    if not path.is_file():
        raise NotFoundError(f"project not found: {project_id}")
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ValidationError(f"project must be a mapping: {path}")
    return data


def doctor(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    try:
        workspace = load_workspace(root)
        checks.append({"name": "workspace", "ok": True})
    except Exception as exc:
        return {
            "ok": False,
            "root": str(root),
            "checks": [{"name": "workspace", "ok": False}],
            "errors": [str(exc)],
            "warnings": [],
        }

    required = [
        ".wsctl/projects",
        ".wsctl/tasks",
        ".wsctl/knowledge",
        ".wsctl/decisions",
        ".wsctl/evidence",
    ]
    for relative in required:
        exists = (root / relative).is_dir()
        checks.append({"name": relative, "ok": exists})
        if not exists:
            errors.append(f"missing directory: {relative}")

    secret_findings = contains_secret_key(workspace)
    if secret_findings:
        errors.append("secret-like keys in workspace metadata: " + ", ".join(secret_findings))

    project_ids: set[str] = set()
    for path in sorted((root / PROJECTS_DIR).glob("*.yaml")):
        try:
            project = load_yaml(path)
            if not isinstance(project, dict) or not project.get("id"):
                raise ValidationError("project must be a mapping with id")
            project_id = str(project["id"])
            if project_id in project_ids:
                errors.append(f"duplicate project id: {project_id}")
            project_ids.add(project_id)
            checks.append({"name": f"project:{project_id}", "ok": True})
        except Exception as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")

    for kind, directory in (
        ("task", "tasks"),
        ("knowledge", "knowledge"),
        ("decision", "decisions"),
        ("evidence", "evidence"),
    ):
        from wsctl.storage.documents import load_document

        for path in sorted((root / ".wsctl" / directory).glob("*.md")):
            try:
                metadata, _ = load_document(path)
                if metadata.get("type") != kind:
                    errors.append(f"{path.relative_to(root)}: type must be {kind}")
                project = metadata.get("project")
                if project and project not in project_ids:
                    warnings.append(
                        f"{path.relative_to(root)}: references unknown project {project}"
                    )
                secret_findings = contains_secret_key(metadata)
                if secret_findings:
                    errors.append(
                        f"{path.relative_to(root)}: secret-like keys "
                        + ", ".join(secret_findings)
                    )
            except Exception as exc:
                errors.append(f"{path.relative_to(root)}: {exc}")

    return {
        "ok": not errors,
        "root": str(root),
        "workspace": workspace,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }

