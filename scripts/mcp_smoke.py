#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from wsctl.services.legacy import preview_legacy
from wsctl.storage.registry import add_workspace


def payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    content = getattr(result, "content", None) or []
    if len(content) == 1 and getattr(content[0], "type", "") == "text":
        text = getattr(content[0], "text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    parsed_content: list[Any] = []
    for item in content:
        if getattr(item, "type", "") != "text":
            parsed_content = []
            break
        try:
            parsed_content.append(json.loads(getattr(item, "text", "")))
        except json.JSONDecodeError:
            parsed_content = []
            break
    if parsed_content:
        return parsed_content
    return [
        getattr(item, "model_dump", lambda: str(item))()
        for item in content
    ]


async def run_smoke(legacy_root: Path, project: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="wsctl-mcp-smoke-") as temporary:
        base = Path(temporary)
        workspace = base / "preview"
        registry = base / "registry.yaml"
        preview = preview_legacy(
            source=legacy_root,
            out=workspace,
            project_id=project,
        )
        entry = add_workspace(
            workspace,
            name="mcp-smoke",
            allow_write=True,
            registry=registry,
        )
        server = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "wsctl.mcp.server",
                "--registry",
                str(registry),
                "--workspace",
                str(entry["id"]),
                "--legacy-workspace",
                str(legacy_root),
            ],
        )
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                listed = await session.list_tools()
                tool_names = [tool.name for tool in listed.tools]

                legacy_projects = payload(
                    await session.call_tool("legacy_project_list", {})
                )
                if len(legacy_projects.get("projects", [])) < 1:
                    raise RuntimeError("legacy_project_list returned no projects")

                source_status = payload(
                    await session.call_tool("legacy_source_status", {})
                )
                if source_status.get("summary", {}).get("error", 0):
                    raise RuntimeError("legacy_source_status returned errors")

                created = payload(
                    await session.call_tool(
                        "create_task",
                        {
                            "title": "MCP 闭环验证任务",
                            "project": project,
                            "tags": ["mcp", "smoke"],
                            "body": "验证 stdio MCP 能创建任务并在随后读回。",
                        },
                    )
                )
                created_id = created["metadata"]["id"]

                tasks = payload(
                    await session.call_tool("task_list", {"project": project})
                )
                if created_id not in {item["id"] for item in tasks}:
                    raise RuntimeError("created task was not returned by task_list")

                context = payload(
                    await session.call_tool(
                        "get_context",
                        {
                            "project": project,
                            "task": created_id,
                            "query": "AB 槽位",
                            "limit": 3,
                        },
                    )
                )
                if context.get("task", {}).get("metadata", {}).get("id") != created_id:
                    raise RuntimeError("get_context did not return the created task")

                return {
                    "ok": True,
                    "server": initialized.serverInfo.model_dump(),
                    "tool_count": len(tool_names),
                    "legacy_tools": sorted(
                        name for name in tool_names if name.startswith("legacy_")
                    ),
                    "legacy_project_count": len(legacy_projects["projects"]),
                    "source_summary": source_status["summary"],
                    "created_task": created_id,
                    "task_count": len(tasks),
                    "context_counts": {
                        "knowledge": len(context.get("knowledge", [])),
                        "decisions": len(context.get("decisions", [])),
                        "evidence": len(context.get("evidence", [])),
                    },
                    "preview_indexed": preview["index"]["indexed"],
                }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-root", required=True)
    parser.add_argument("--project", default="echolife-rk3576")
    args = parser.parse_args()
    result = asyncio.run(run_smoke(Path(args.legacy_root).resolve(), args.project))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
