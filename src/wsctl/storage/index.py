from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from wsctl.core.models import TYPE_DIRS
from wsctl.storage.documents import load_document


def index_path(root: Path) -> Path:
    return root / ".wsctl" / ".index" / "wsctl.sqlite"


def _connect(root: Path) -> sqlite3.Connection:
    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
          id UNINDEXED,
          kind UNINDEXED,
          title,
          body,
          tags,
          status UNINDEXED,
          project UNINDEXED,
          path UNINDEXED
        )
        """
    )
    return connection


def rebuild(root: Path) -> dict[str, Any]:
    connection = _connect(root)
    try:
        connection.execute("DELETE FROM docs")
        count = 0
        for kind, directory in TYPE_DIRS.items():
            for path in sorted((root / ".wsctl" / directory).glob("*.md")):
                metadata, body = load_document(path)
                connection.execute(
                    "INSERT INTO docs(id, kind, title, body, tags, status, project, path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(metadata.get("id", path.stem)),
                        kind,
                        str(metadata.get("title", "")),
                        body,
                        " ".join(str(item) for item in metadata.get("tags", [])),
                        str(metadata.get("status", "")),
                        str(metadata.get("project") or ""),
                        str(path.relative_to(root)),
                    ),
                )
                count += 1
        connection.commit()
        return {"ok": True, "indexed": count, "path": str(index_path(root))}
    finally:
        connection.close()


def search(root: Path, query: str, limit: int = 10) -> list[dict[str, Any]]:
    rebuild(root)
    connection = _connect(root)
    try:
        rows = connection.execute(
            "SELECT id, kind, title, status, project, path, "
            "snippet(docs, 3, '[', ']', '…', 16) "
            "FROM docs WHERE docs MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
    finally:
        connection.close()
    results = [
        {
            "id": row[0],
            "kind": row[1],
            "title": row[2],
            "status": row[3],
            "project": row[4],
            "path": row[5],
            "snippet": row[6],
        }
        for row in rows
    ]
    if results:
        return results

    # FTS5 的 unicode61 对无空格中文分词不理想；原型保留一个可预测的
    # 子串回退，保证中文标题和正文至少可以被检索到。
    needle = query.lower()
    fallback: list[dict[str, Any]] = []
    for kind, directory in TYPE_DIRS.items():
        for path in sorted((root / ".wsctl" / directory).glob("*.md")):
            metadata, body = load_document(path)
            haystack = " ".join(
                [
                    str(metadata.get("title", "")),
                    body,
                    " ".join(str(item) for item in metadata.get("tags", [])),
                ]
            ).lower()
            if needle not in haystack:
                continue
            index = haystack.find(needle)
            start = max(0, index - 30)
            end = min(len(haystack), index + len(needle) + 60)
            fallback.append(
                {
                    "id": str(metadata.get("id", path.stem)),
                    "kind": kind,
                    "title": str(metadata.get("title", "")),
                    "status": str(metadata.get("status", "")),
                    "project": str(metadata.get("project") or ""),
                    "path": str(path.relative_to(root)),
                    "snippet": haystack[start:end],
                }
            )
            if len(fallback) >= limit:
                return fallback
    return fallback
