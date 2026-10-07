from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from wsctl.core.errors import ValidationError


class LegacyAdapterError(ValidationError):
    """当前 Buildroot 工作区适配失败。"""


def _bridge_program(legacy_src: Path) -> str:
    return f"""\
import json
import sys
sys.path.insert(0, {str(legacy_src)!r})
import wsctl.io as io
io.dump_json = lambda data: json.dumps(
    data, ensure_ascii=False, indent=2, sort_keys=True, default=str
)
from wsctl.cli import main
raise SystemExit(main(sys.argv[1:]))
"""


def run_legacy_json(
    root: Path,
    args: list[str],
    *,
    timeout: int = 120,
) -> Any:
    root = root.expanduser().resolve()
    legacy_src = root / "tools" / "wsctl" / "src"
    if not legacy_src.is_dir():
        raise LegacyAdapterError(f"not a legacy wsctl workspace: {root}")
    completed = subprocess.run(
        [sys.executable, "-c", _bridge_program(legacy_src), *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    if not completed.stdout.strip():
        raise LegacyAdapterError(
            f"legacy command failed ({completed.returncode}) without JSON: "
            f"{' '.join(args)}\n{(completed.stderr or '').strip()}"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LegacyAdapterError(
            f"legacy command produced invalid JSON: {' '.join(args)}: {exc}\n"
            f"{completed.stdout[:1000]}"
        ) from exc
    if completed.returncode != 0 and isinstance(parsed, dict):
        parsed.setdefault("_legacy_exit_code", completed.returncode)
    return parsed


def legacy_doctor(root: Path) -> dict[str, Any]:
    return run_legacy_json(root, ["doctor", "--json"])


def legacy_project_list(root: Path) -> dict[str, Any]:
    return {"ok": True, "projects": run_legacy_json(root, ["projects", "list", "--json"])}


def legacy_project_context(
    root: Path,
    *,
    project: str,
    task: str,
    timeout: int = 120,
) -> dict[str, Any]:
    return run_legacy_json(
        root,
        ["context", project, "--task", task, "--json"],
        timeout=timeout,
    )


def legacy_source_status(root: Path, *, timeout: int = 300) -> dict[str, Any]:
    return run_legacy_json(root, ["verify", "sources", "--json"], timeout=timeout)


def legacy_branch_status(root: Path) -> dict[str, Any]:
    return run_legacy_json(root, ["branches", "list", "--json"])


def legacy_worktree_status(
    root: Path,
    *,
    project: str,
    component: str | None = None,
) -> dict[str, Any]:
    args = ["worktree", "status", project]
    if component:
        args.extend(["--component", component])
    args.append("--json")
    return run_legacy_json(root, args)


def legacy_history(
    root: Path,
    *,
    project: str,
    limit: int = 10,
) -> dict[str, Any]:
    return run_legacy_json(
        root,
        ["history", project, "--limit", str(limit), "--json"],
    )


def legacy_knowledge_list(
    root: Path,
    *,
    status: str | None = None,
) -> dict[str, Any]:
    args = ["knowledge", "list"]
    if status:
        args.extend(["--status", status])
    args.append("--json")
    return {"ok": True, "knowledge": run_legacy_json(root, args)}


def legacy_knowledge_verify(root: Path) -> dict[str, Any]:
    return run_legacy_json(root, ["knowledge", "verify", "--json"])


def legacy_agent_status(root: Path) -> dict[str, Any]:
    return run_legacy_json(root, ["agent", "ensure", "--json"])


def legacy_build_plan(
    root: Path,
    *,
    project: str,
    profile: str,
    stage: str = "configure",
) -> dict[str, Any]:
    return run_legacy_json(
        root,
        ["build", project, "--profile", profile, "--stage", stage, "--json"],
        timeout=300,
    )


def legacy_test_plan(
    root: Path,
    *,
    project: str,
    profile: str,
    tiers: str = "T0",
) -> dict[str, Any]:
    return run_legacy_json(
        root,
        ["test", project, "--profile", profile, "--tier", tiers, "--json"],
        timeout=300,
    )


def legacy_deploy_plan(
    root: Path,
    *,
    project: str,
    profile: str,
    slot: str = "a",
    board_device: str | None = None,
    bom: str | None = None,
) -> dict[str, Any]:
    args = [
        "deploy",
        "plan",
        project,
        "--profile",
        profile,
        "--slot",
        slot,
    ]
    if board_device:
        args.extend(["--board-device", board_device])
    if bom:
        args.extend(["--bom", bom])
    args.append("--json")
    # plan 本身不写板卡，但会只读探测运行槽，因此单独给较长超时。
    return run_legacy_json(root, args, timeout=300)


def legacy_release_show(root: Path, *, release_id: str) -> dict[str, Any]:
    return run_legacy_json(root, ["release", "show", release_id, "--json"])
