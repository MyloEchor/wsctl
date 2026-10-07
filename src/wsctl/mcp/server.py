from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from wsctl.adapters import legacy_workspace as legacy
from wsctl.core.errors import ValidationError, WriteDeniedError
from wsctl.services.context import build_context
from wsctl.services.entities import (
    archive_entity,
    create_entity,
    list_entities,
    update_entity,
)
from wsctl.services.workspace import doctor, list_projects
from wsctl.storage.index import search
from wsctl.storage.registry import (
    list_workspaces,
    registry_path,
    resolve_workspace,
    write_allowed,
)


def _root(
    selector: str | None,
    *,
    default_workspace: str | None,
    registry: Path,
) -> Path:
    return resolve_workspace(
        selector or default_workspace,
        registry=registry,
    )


def _write_root(
    selector: str | None,
    *,
    default_workspace: str | None,
    registry: Path,
) -> Path:
    root = _root(selector, default_workspace=default_workspace, registry=registry)
    if not write_allowed(root, registry=registry):
        raise WriteDeniedError(
            f"workspace write is disabled: {root} "
            "(run `wsctl workspace add <path> --allow-write`)"
        )
    return root


def build_server(
    *,
    default_workspace: str | None = None,
    registry: Path | None = None,
    legacy_workspace: Path | None = None,
) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MCP support is not installed; install with `pip install 'wsctl[mcp]'`"
        ) from exc

    registry_file = registry or registry_path()
    server = FastMCP(
        "wsctl",
        instructions=(
            "通用 AI 开发工作区管理工具。默认读取多个已登记 workspace；"
            "写入前必须通过 `wsctl workspace add --allow-write` 显式授权。"
        ),
    )

    @server.tool()
    def registry_list() -> list[dict[str, Any]]:
        """列出本机已登记的 wsctl 工作区。"""
        return list_workspaces(registry_file)

    @server.tool()
    def workspace_info(workspace: str | None = None) -> dict[str, Any]:
        """返回指定工作区的元数据、状态和项目列表。"""
        root = _root(workspace, default_workspace=default_workspace, registry=registry_file)
        return {
            "root": str(root),
            "doctor": doctor(root),
            "projects": list_projects(root),
            "allow_write": write_allowed(root, registry=registry_file),
        }

    @server.tool()
    def project_list(workspace: str | None = None) -> list[dict[str, Any]]:
        """列出工作区中的项目。"""
        return list_projects(
            _root(workspace, default_workspace=default_workspace, registry=registry_file)
        )

    @server.tool()
    def task_list(
        workspace: str | None = None,
        project: str | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        """列出任务。"""
        root = _root(workspace, default_workspace=default_workspace, registry=registry_file)
        return list_entities(
            root,
            "task",
            project=project,
            include_archived=include_archived,
        )

    @server.tool()
    def knowledge_list(
        workspace: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出知识条目。"""
        root = _root(workspace, default_workspace=default_workspace, registry=registry_file)
        return list_entities(
            root,
            "knowledge",
            project=project,
            include_archived=False,
        )

    @server.tool()
    def decision_list(
        workspace: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出决策记录。"""
        root = _root(workspace, default_workspace=default_workspace, registry=registry_file)
        return list_entities(
            root,
            "decision",
            project=project,
            include_archived=False,
        )

    @server.tool()
    def evidence_list(
        workspace: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出证据记录。"""
        root = _root(workspace, default_workspace=default_workspace, registry=registry_file)
        return list_entities(
            root,
            "evidence",
            project=project,
            include_archived=False,
        )

    @server.tool()
    def get_context(
        workspace: str | None = None,
        project: str | None = None,
        task: str | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """生成供 Agent 使用的项目、任务、知识、决策和证据上下文。"""
        root = _root(workspace, default_workspace=default_workspace, registry=registry_file)
        return build_context(
            root,
            project=project,
            task=task,
            query=query,
            limit=limit,
        )

    @server.tool()
    def workspace_search(
        query: str,
        workspace: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """在工作区管理数据中执行全文检索。"""
        root = _root(workspace, default_workspace=default_workspace, registry=registry_file)
        return search(root, query, limit=limit)

    @server.tool()
    def create_task(
        title: str,
        workspace: str | None = None,
        project: str | None = None,
        status: str = "todo",
        priority: str = "medium",
        tags: list[str] | None = None,
        body: str = "",
    ) -> dict[str, Any]:
        """创建任务；工作区必须已显式开启 allow-write。"""
        root = _write_root(
            workspace, default_workspace=default_workspace, registry=registry_file
        )
        return create_entity(
            root,
            "task",
            title=title,
            body=body,
            project=project,
            status=status,
            priority=priority,
            tags=tags,
        )

    @server.tool()
    def update_task(
        entity_id: str,
        workspace: str | None = None,
        title: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        """更新任务；工作区必须已显式开启 allow-write。"""
        root = _write_root(
            workspace, default_workspace=default_workspace, registry=registry_file
        )
        return update_entity(
            root,
            "task",
            entity_id,
            title=title,
            body=body,
            project=project,
            status=status,
            priority=priority,
            tags=tags,
        )

    @server.tool()
    def archive_task(
        entity_id: str,
        workspace: str | None = None,
    ) -> dict[str, Any]:
        """归档任务；工作区必须已显式开启 allow-write。"""
        root = _write_root(
            workspace, default_workspace=default_workspace, registry=registry_file
        )
        return archive_entity(root, "task", entity_id)

    @server.tool()
    def create_knowledge(
        title: str,
        workspace: str | None = None,
        project: str | None = None,
        status: str = "draft",
        tags: list[str] | None = None,
        body: str = "",
    ) -> dict[str, Any]:
        """创建知识条目；工作区必须已显式开启 allow-write。"""
        root = _write_root(
            workspace, default_workspace=default_workspace, registry=registry_file
        )
        return create_entity(
            root,
            "knowledge",
            title=title,
            body=body,
            project=project,
            status=status,
            tags=tags,
        )

    @server.tool()
    def create_decision(
        title: str,
        workspace: str | None = None,
        project: str | None = None,
        status: str = "proposed",
        tags: list[str] | None = None,
        body: str = "",
    ) -> dict[str, Any]:
        """创建决策记录；工作区必须已显式开启 allow-write。"""
        root = _write_root(
            workspace, default_workspace=default_workspace, registry=registry_file
        )
        return create_entity(
            root,
            "decision",
            title=title,
            body=body,
            project=project,
            status=status,
            tags=tags,
        )

    @server.tool()
    def create_evidence(
        title: str,
        uri: str,
        workspace: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        body: str = "",
    ) -> dict[str, Any]:
        """创建证据记录；工作区必须已显式开启 allow-write。"""
        root = _write_root(
            workspace, default_workspace=default_workspace, registry=registry_file
        )
        return create_entity(
            root,
            "evidence",
            title=title,
            body=body,
            project=project,
            status="captured",
            tags=tags,
            uri=uri,
        )

    if legacy_workspace is not None:
        legacy_root = legacy_workspace.expanduser().resolve()

        @server.tool()
        def legacy_doctor() -> dict[str, Any]:
            """检查当前 Buildroot 工作区元数据；只读。"""
            return legacy.legacy_doctor(legacy_root)

        @server.tool()
        def legacy_project_list() -> dict[str, Any]:
            """列出当前 Buildroot 工作区的项目；只读。"""
            return legacy.legacy_project_list(legacy_root)

        @server.tool()
        def legacy_project_context(project: str, task: str) -> dict[str, Any]:
            """生成当前 Buildroot 项目的 Agent 上下文；只读。"""
            return legacy.legacy_project_context(
                legacy_root,
                project=project,
                task=task,
            )

        @server.tool()
        def legacy_source_status() -> dict[str, Any]:
            """核对 west.yml 与磁盘源码身份；只读。"""
            return legacy.legacy_source_status(legacy_root)

        @server.tool()
        def legacy_branch_status() -> dict[str, Any]:
            """查看长期开发线状态；只读。"""
            return legacy.legacy_branch_status(legacy_root)

        @server.tool()
        def legacy_worktree_status(
            project: str,
            component: str | None = None,
        ) -> dict[str, Any]:
            """查看项目工作树状态；只读。"""
            return legacy.legacy_worktree_status(
                legacy_root,
                project=project,
                component=component,
            )

        @server.tool()
        def legacy_history(project: str, limit: int = 10) -> dict[str, Any]:
            """查看项目历史来源；只读。"""
            return legacy.legacy_history(
                legacy_root,
                project=project,
                limit=limit,
            )

        @server.tool()
        def legacy_knowledge_list(status: str | None = None) -> dict[str, Any]:
            """列出当前工作区知识；只读。"""
            return legacy.legacy_knowledge_list(legacy_root, status=status)

        @server.tool()
        def legacy_knowledge_verify() -> dict[str, Any]:
            """验证知识元信息和状态；只读。"""
            return legacy.legacy_knowledge_verify(legacy_root)

        @server.tool()
        def legacy_agent_status() -> dict[str, Any]:
            """检查当前机器上的 Agent 工具链；只读。"""
            return legacy.legacy_agent_status(legacy_root)

        @server.tool()
        def legacy_build_plan(
            project: str,
            profile: str,
            stage: str = "configure",
        ) -> dict[str, Any]:
            """生成 Buildroot 构建计划；不执行构建。"""
            return legacy.legacy_build_plan(
                legacy_root,
                project=project,
                profile=profile,
                stage=stage,
            )

        @server.tool()
        def legacy_test_plan(
            project: str,
            profile: str,
            tiers: str = "T0",
        ) -> dict[str, Any]:
            """生成测试计划；不执行测试。"""
            return legacy.legacy_test_plan(
                legacy_root,
                project=project,
                profile=profile,
                tiers=tiers,
            )

        @server.tool()
        def legacy_deploy_plan(
            project: str,
            profile: str,
            slot: str = "a",
            board_device: str | None = None,
            bom: str | None = None,
        ) -> dict[str, Any]:
            """生成烧写计划；不执行烧写，但会只读探测板卡运行槽。"""
            return legacy.legacy_deploy_plan(
                legacy_root,
                project=project,
                profile=profile,
                slot=slot,
                board_device=board_device,
                bom=bom,
            )

        @server.tool()
        def legacy_release_show(release_id: str) -> dict[str, Any]:
            """读取交付记录；只读。"""
            return legacy.legacy_release_show(legacy_root, release_id=release_id)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wsctl-mcp")
    parser.add_argument("--registry", help="多工作区注册表路径")
    parser.add_argument("--workspace", help="默认工作区 id 或路径")
    parser.add_argument(
        "--legacy-workspace",
        help="增加当前 Buildroot 工作区的只读 MCP 适配器",
    )
    parser.add_argument("--list-tools", action="store_true")
    args = parser.parse_args(argv)
    server = build_server(
        default_workspace=args.workspace,
        registry=Path(args.registry).expanduser().resolve() if args.registry else None,
        legacy_workspace=(
            Path(args.legacy_workspace).expanduser().resolve()
            if args.legacy_workspace
            else None
        ),
    )
    if args.list_tools:
        tools = asyncio.run(server.list_tools())
        print(
            json.dumps(
                [
                    {"name": tool.name, "description": tool.description}
                    for tool in tools
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
