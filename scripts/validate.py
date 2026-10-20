"""Check every repo file against the schema and the directory rules. Exits non-zero on any problem.

Usage: python scripts/validate.py [FILE ...]   (no arguments checks every repo file)
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tomllib
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from directory import REPOS, ROOT, SLUG_RE, categories, load, repo_files, shard


LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

# Plain-English messages for fields whose rule is a pattern.
HINTS = {
    "repository": 'must be the full link to the code, like "https://github.com/owner/repo"',
    "website": 'must be a full link starting with "https://"',
    "docs": 'must be a full link starting with "https://"',
    "tags": 'tags are lowercase words joined by hyphens, like "speech-to-text"',
    "added": "must be a date written as YYYY-MM-DD, like 2026-10-20",
}


def message(err) -> str:
    field = str(err.path[0]) if err.path else ""
    if err.validator in ("pattern", "format") and field in HINTS:
        return HINTS[field]
    return err.message


def main(argv: list[str]) -> int:
    schema = json.loads((ROOT / "schema" / "repo.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cats = categories()
    problems: list[str] = []
    repos: dict[str, str] = {}
    today = dt.date.today().isoformat()

    stray = [p for p in REPOS.rglob("*") if p.is_file() and (p.suffix != ".toml" or p.parent.parent != REPOS)]
    for p in stray:
        problems.append(f"{p.relative_to(ROOT)}: files go in repos/<first character>/<slug>.toml")

    files = list(repo_files())
    only = {Path(a).resolve() for a in argv}
    for path in files:
        rel = path.relative_to(ROOT)
        slug = path.stem
        report = not only or path.resolve() in only
        try:
            data = load(path)
        except Exception as exc:  # noqa: BLE001 - report any TOML error
            problems.append(f"{rel}: not valid TOML ({exc})")
            continue
        if not isinstance(data, dict):
            problems.append(f"{rel}: must be a mapping of fields")
            continue

        repo = str(data.get("repository") or "").rstrip("/").lower()
        if repo:
            if repo in repos and (report or not only):
                problems.append(f"{rel}: {data['repository']} is already listed in {repos[repo]}")
            repos.setdefault(repo, str(rel))
        if not report:
            continue

        if not SLUG_RE.match(slug):
            problems.append(f"{rel}: file name must be lowercase letters, digits and hyphens")
        elif path.parent.name != shard(slug):
            problems.append(f"{rel}: move it to repos/{shard(slug)}/{slug}.toml")
        # `added = 2026-10-20` (no quotes) is a TOML date; the schema expects a string.
        if isinstance(data.get("added"), dt.date):
            data["added"] = data["added"].isoformat()
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in err.path) or "(top)"
            problems.append(f"{rel}: {where}: {message(err)}")
        if data.get("category") not in cats:
            problems.append(f"{rel}: category must be one of the ids in categories.toml: {', '.join(cats)}")
        if isinstance(data.get("added"), str) and data["added"] > today:
            problems.append(f"{rel}: added is in the future")

    try:
        with (ROOT / "opt-out.toml").open("rb") as fh:
            logins = tomllib.load(fh).get("logins")
        if not isinstance(logins, list) or not all(isinstance(x, str) and LOGIN_RE.match(x) for x in logins):
            problems.append('opt-out.toml: logins must be a list of GitHub logins, like ["octocat"]')
    except Exception as exc:  # noqa: BLE001 - report any TOML error
        problems.append(f"opt-out.toml: not valid TOML ({exc})")

    for p in problems:
        print(p)
    print(f"{len(only) or len(files)} repo(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
