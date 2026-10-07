from __future__ import annotations

import datetime as dt
import re
import secrets
from typing import Any

ID_PREFIXES = {
    "task": "TASK",
    "knowledge": "KN",
    "decision": "ADR",
    "evidence": "EVD",
}

ENTITY_TYPES = tuple(ID_PREFIXES)

TYPE_DIRS = {
    "task": "tasks",
    "knowledge": "knowledge",
    "decision": "decisions",
    "evidence": "evidence",
}

TYPE_STATUS = {
    "task": {"todo", "doing", "blocked", "review", "done", "archived"},
    "knowledge": {"draft", "verified", "stale", "deprecated", "archived"},
    "decision": {"proposed", "accepted", "rejected", "superseded", "archived"},
    "evidence": {"captured", "verified", "stale", "archived"},
}

REQUIRED_FIELDS = {
    "task": ("title", "status", "priority"),
    "knowledge": ("title", "status"),
    "decision": ("title", "status"),
    "evidence": ("title", "status", "uri"),
}

DEFAULT_STATUS = {
    "task": "todo",
    "knowledge": "draft",
    "decision": "proposed",
    "evidence": "captured",
}

DEFAULT_PRIORITY = "medium"

SECRET_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "private_key",
    "api_key",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def new_id(kind: str) -> str:
    if kind not in ID_PREFIXES:
        raise ValueError(f"unsupported entity type: {kind}")
    day = dt.datetime.now().strftime("%Y%m%d")
    return f"{ID_PREFIXES[kind]}-{day}-{secrets.token_hex(3).upper()}"


def normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("tags must be a string or list")


def contains_secret_key(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in SECRET_KEYS:
                findings.append(path)
            findings.extend(contains_secret_key(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(contains_secret_key(child, f"{prefix}[{index}]"))
    return findings


def validate_status(kind: str, status: str) -> None:
    if status not in TYPE_STATUS[kind]:
        allowed = ", ".join(sorted(TYPE_STATUS[kind]))
        raise ValueError(f"invalid {kind} status {status!r}; expected one of: {allowed}")


def validate_entity_metadata(kind: str, metadata: dict[str, Any]) -> None:
    if metadata.get("type") != kind:
        raise ValueError(f"metadata type must be {kind!r}")
    for field in REQUIRED_FIELDS[kind]:
        if not metadata.get(field):
            raise ValueError(f"{kind} metadata requires {field!r}")
    validate_status(kind, str(metadata["status"]))
    if kind == "task":
        if metadata.get("priority") not in {"low", "medium", "high", "critical"}:
            raise ValueError("task priority must be low, medium, high, or critical")

