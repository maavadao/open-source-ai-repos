"""Shared helpers for reading and writing repo files and categories."""
from __future__ import annotations

import datetime as dt
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT / "repos"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# The order fields are written in, so every file reads the same way.
FIELD_ORDER = ("name", "description", "category", "tags", "repository", "website", "docs", "license",
               "language", "skill_level", "runs_locally", "added")


def categories() -> dict[str, dict]:
    with (ROOT / "categories.toml").open("rb") as fh:
        return tomllib.load(fh)


def shard(slug: str) -> str:
    """The folder a slug lives in: its first character (a–z or 0-9)."""
    return slug[0] if slug[0].isalpha() else "0-9"


def path_for(slug: str) -> Path:
    return REPOS / shard(slug) / f"{slug}.toml"


def repo_files():
    yield from sorted(REPOS.glob("*/*.toml"))


def load(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)  # a JSON string is a valid TOML basic string


def dumps(data: dict) -> str:
    """One `key = value` line per field, in FIELD_ORDER."""
    keys = [k for k in FIELD_ORDER if k in data] + [k for k in data if k not in FIELD_ORDER]
    return "".join(f"{k} = {_value(data[k])}\n" for k in keys if data[k] not in (None, [], ""))
