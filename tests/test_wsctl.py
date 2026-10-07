from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wsctl.services.context import build_context
from wsctl.services.entities import create_entity, list_entities
from wsctl.services.legacy import preview_legacy
from wsctl.services.workspace import create_project, doctor, init_workspace
from wsctl.storage.index import search


class WorkspaceLifecycleTest(unittest.TestCase):
    def test_workspace_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_workspace(root, name="demo")
            create_project(root, project_id="demo-project", name="Demo Project")
            task = create_entity(
                root,
                "task",
                title="验证通用任务上下文",
                project="demo-project",
                tags=["preview"],
                body="验收标准：任务可检索，并进入 context。",
            )
            task_id = task["metadata"]["id"]
            self.assertEqual(1, len(list_entities(root, "task", project="demo-project")))
            self.assertTrue(doctor(root)["ok"])
            self.assertEqual(task_id, search(root, "验收")[0]["id"])
            context = build_context(
                root,
                project="demo-project",
                task=task_id,
                query="验收",
            )
            self.assertEqual("Demo Project", context["project"]["name"])
            self.assertEqual(task_id, context["task"]["metadata"]["id"])


class LegacyPreviewTest(unittest.TestCase):
    def test_legacy_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            out = base / "preview"
            (source / "management").mkdir(parents=True)
            (source / "products" / "demo" / "evidence").mkdir(parents=True)
            (source / "knowledge" / "adr").mkdir(parents=True)
            (source / "management" / "projects.yaml").write_text(
                "projects:\n  - id: demo\n    manifest: products/demo/project.yaml\n",
                encoding="utf-8",
            )
            (source / "products" / "demo" / "project.yaml").write_text(
                "id: demo\nname: Demo\nplatforms:\n  generic: {}\n"
                "profiles: [default]\ntest_tiers: [T0]\nstatus: active\n",
                encoding="utf-8",
            )
            (source / "knowledge" / "note.md").write_text(
                "---\nid: KN-1\ntitle: 一条知识\nstatus: verified\n---\n\n正文\n",
                encoding="utf-8",
            )
            (source / "knowledge" / "adr" / "ADR-1.md").write_text(
                "---\nid: ADR-1\ntitle: 一个决策\n"
                "decision_status: accepted\n---\n\n决策正文\n",
                encoding="utf-8",
            )
            (source / "products" / "demo" / "evidence" / "T0.md").write_text(
                "---\nid: T0\n---\n\n证据正文\n",
                encoding="utf-8",
            )
            result = preview_legacy(source=source, out=out, project_id="demo")
            self.assertTrue(result["ok"])
            self.assertEqual(1, result["projects"])
            self.assertEqual(1, result["knowledge"])
            self.assertEqual(1, result["decisions"])
            self.assertEqual(1, result["evidence"])
            self.assertTrue(doctor(out)["ok"])


if __name__ == "__main__":
    unittest.main()

