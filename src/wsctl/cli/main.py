from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from wsctl.core.errors import WsctlError
from wsctl.services.context import build_context
from wsctl.services.entities import (
    archive_entity,
    create_entity,
    get_entity,
    list_entities,
    purge_entity,
    update_entity,
)
from wsctl.services.legacy import preview_legacy
from wsctl.services.workspace import (
    create_project,
    doctor,
    get_project,
    init_workspace,
    list_projects,
)
from wsctl.storage.index import rebuild, search
from wsctl.storage.registry import (
    add_workspace,
    list_workspaces,
    registry_path,
    resolve_workspace,
)


def _dump(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if isinstance(data, dict):
        if data.get("ok") is False:
            print("FAILED")
        for key in (
            "ok",
            "root",
            "workspace",
            "project",
            "id",
            "title",
            "status",
            "priority",
            "kind",
            "count",
            "indexed",
            "out",
            "source",
        ):
            if key in data and data[key] is not None:
                print(f"{key}: {data[key]}")
        for error in data.get("errors", []):
            print(f"ERROR: {error}")
        for warning in data.get("warnings", []):
            print(f"WARNING: {warning}")
        return
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                ident = item.get("id", "<none>")
                title = item.get("title") or item.get("name") or ""
                status = item.get("status", "")
                print(f"- {ident} [{status}] {title}")
            else:
                print(item)
        return
    print(data)


def _resolve_root(args: argparse.Namespace) -> Path:
    if args.root:
        return Path(args.root).expanduser().resolve()
    return resolve_workspace(registry=registry_path(args.registry))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wsctl",
        description="通用 AI 开发工作区管理原型",
    )
    parser.add_argument("--root", help="工作区路径")
    parser.add_argument("--registry", help="多工作区注册表路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="初始化 .wsctl 工作区")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--name")
    init.add_argument("--force", action="store_true")

    workspace = subparsers.add_parser("workspace", help="多工作区注册表")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_add = workspace_sub.add_parser("add")
    workspace_add.add_argument("path")
    workspace_add.add_argument("--id")
    workspace_add.add_argument("--name")
    workspace_add.add_argument("--allow-write", action="store_true")
    workspace_sub.add_parser("list")

    subparsers.add_parser("doctor", help="检查当前工作区")

    projects = subparsers.add_parser("projects", help="项目")
    projects_sub = projects.add_subparsers(dest="projects_command", required=True)
    projects_sub.add_parser("list")
    project_show = projects_sub.add_parser("show")
    project_show.add_argument("project_id")
    project_create = projects_sub.add_parser("create")
    project_create.add_argument("project_id")
    project_create.add_argument("--name")
    project_create.add_argument("--tag", action="append", default=[])

    create = subparsers.add_parser("create", help="创建管理对象")
    create.add_argument("kind", choices=("task", "knowledge", "decision", "evidence"))
    create.add_argument("--title", required=True)
    create.add_argument("--body", default="")
    create.add_argument("--project")
    create.add_argument("--status")
    create.add_argument("--priority")
    create.add_argument("--tag", action="append", default=[])
    create.add_argument("--uri")

    list_command = subparsers.add_parser("list", help="列出管理对象")
    list_command.add_argument("kind", choices=("task", "knowledge", "decision", "evidence"))
    list_command.add_argument("--project")
    list_command.add_argument("--status")
    list_command.add_argument("--all", action="store_true")
    list_command.add_argument("--limit", type=int)

    show = subparsers.add_parser("show", help="查看管理对象")
    show.add_argument("kind", choices=("task", "knowledge", "decision", "evidence"))
    show.add_argument("entity_id")

    update = subparsers.add_parser("update", help="更新管理对象")
    update.add_argument("kind", choices=("task", "knowledge", "decision", "evidence"))
    update.add_argument("entity_id")
    update.add_argument("--title")
    update.add_argument("--body")
    update.add_argument("--project")
    update.add_argument("--status")
    update.add_argument("--priority")
    update.add_argument("--tag", action="append")
    update.add_argument("--uri")

    archive = subparsers.add_parser("archive", help="归档管理对象")
    archive.add_argument("kind", choices=("task", "knowledge", "decision", "evidence"))
    archive.add_argument("entity_id")

    purge = subparsers.add_parser("purge", help="彻底删除管理对象")
    purge.add_argument("kind", choices=("task", "knowledge", "decision", "evidence"))
    purge.add_argument("entity_id")
    purge.add_argument("--confirm", action="store_true")

    context = subparsers.add_parser("context", help="生成 Agent 有界上下文")
    context.add_argument("--project")
    context.add_argument("--task")
    context.add_argument("--query")
    context.add_argument("--limit", type=int, default=10)

    subparsers.add_parser("index", help="重建 SQLite/FTS5 索引")

    search_command = subparsers.add_parser("search", help="搜索管理对象")
    search_command.add_argument("query")
    search_command.add_argument("--limit", type=int, default=10)

    legacy = subparsers.add_parser("legacy", help="旧工作区适配")
    legacy_sub = legacy.add_subparsers(dest="legacy_command", required=True)
    legacy_preview = legacy_sub.add_parser("preview", help="把旧工作区映射为 .wsctl 预览")
    legacy_preview.add_argument("--source", required=True)
    legacy_preview.add_argument("--out", required=True)
    legacy_preview.add_argument("--project")
    legacy_preview.add_argument("--skip-knowledge", action="store_true")
    legacy_preview.add_argument("--skip-evidence", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init_workspace(Path(args.path), name=args.name, force=args.force)
        elif args.command == "workspace":
            if args.workspace_command == "add":
                result = add_workspace(
                    Path(args.path),
                    workspace_id=args.id,
                    name=args.name,
                    allow_write=args.allow_write,
                    registry=registry_path(args.registry),
                )
            else:
                result = list_workspaces(registry_path(args.registry))
        elif args.command == "legacy":
            result = preview_legacy(
                source=Path(args.source),
                out=Path(args.out),
                project_id=args.project,
                include_knowledge=not args.skip_knowledge,
                include_evidence=not args.skip_evidence,
            )
        else:
            root = _resolve_root(args)
            if args.command == "doctor":
                result = doctor(root)
            elif args.command == "projects":
                if args.projects_command == "list":
                    result = list_projects(root)
                elif args.projects_command == "show":
                    result = get_project(root, args.project_id)
                else:
                    result = create_project(
                        root,
                        project_id=args.project_id,
                        name=args.name,
                        tags=args.tag,
                    )
            elif args.command == "create":
                result = create_entity(
                    root,
                    args.kind,
                    title=args.title,
                    body=args.body,
                    project=args.project,
                    status=args.status,
                    priority=args.priority,
                    tags=args.tag,
                    uri=args.uri,
                )
            elif args.command == "list":
                result = list_entities(
                    root,
                    args.kind,
                    project=args.project,
                    status=args.status,
                    include_archived=args.all,
                    limit=args.limit,
                )
            elif args.command == "show":
                result = get_entity(root, args.kind, args.entity_id)
            elif args.command == "update":
                result = update_entity(
                    root,
                    args.kind,
                    args.entity_id,
                    title=args.title,
                    body=args.body,
                    project=args.project,
                    status=args.status,
                    priority=args.priority,
                    tags=args.tag,
                    uri=args.uri,
                )
            elif args.command == "archive":
                result = archive_entity(root, args.kind, args.entity_id)
            elif args.command == "purge":
                result = purge_entity(
                    root, args.kind, args.entity_id, confirm=args.confirm
                )
            elif args.command == "context":
                result = build_context(
                    root,
                    project=args.project,
                    task=args.task,
                    query=args.query,
                    limit=args.limit,
                )
            elif args.command == "index":
                result = rebuild(root)
            elif args.command == "search":
                result = search(root, args.query, limit=args.limit)
            else:
                parser.error(f"unsupported command: {args.command}")
        _dump(result, args.json)
        if isinstance(result, dict) and result.get("ok") is False:
            return 1
        return 0
    except WsctlError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

