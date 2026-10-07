from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from wsctl.core.errors import ValidationError


def load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid YAML: {path}: {exc}") from exc


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_yaml_atomic(path: Path, data: Any) -> None:
    write_text_atomic(path, dump_yaml(data))


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise ValidationError("document must start with YAML frontmatter")
    marker = text.find("\n---\n", 4)
    if marker == -1:
        raise ValidationError("document frontmatter has no closing delimiter")
    raw = text[4:marker]
    body = text[marker + 5 :]
    try:
        metadata = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValidationError("document frontmatter must be a mapping")
    return metadata, body


def dump_frontmatter(metadata: dict[str, Any], body: str = "") -> str:
    return "---\n" + dump_yaml(metadata) + "---\n" + body


def load_document(path: Path) -> tuple[dict[str, Any], str]:
    try:
        return parse_frontmatter(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"document not found: {path}") from exc


def write_document(path: Path, metadata: dict[str, Any], body: str = "") -> None:
    write_text_atomic(path, dump_frontmatter(metadata, body))


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {path}: {exc}") from exc

