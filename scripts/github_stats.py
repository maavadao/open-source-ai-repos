"""Fetch public GitHub facts for many repositories with batched GraphQL queries."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

GITHUB_RE = re.compile(r"^https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$")
FIELDS = """
  nameWithOwner name description homepageUrl stargazerCount isArchived pushedAt
  licenseInfo { spdxId }
  primaryLanguage { name }
  repositoryTopics(first: 20) { nodes { topic { name } } }
"""


def parse(url: str) -> tuple[str, str] | None:
    m = GITHUB_RE.match(url or "")
    return (m.group(1), m.group(2)) if m else None


def token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _query(tok: str, body: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": body}).encode(),
        headers={"Authorization": f"bearer {tok}", "User-Agent": "maavadao-open-source-ai-repos"},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except Exception:  # noqa: BLE001 - retry transient network errors
            if attempt == 4:
                raise
            time.sleep(3 * 2 ** attempt)
    return {}


LIGHT = "stargazerCount isArchived pushedAt"


def fetch_stats(urls: list[str], tok: str | None = None, batch: int = 100) -> dict[str, dict]:
    """Map each GitHub URL to its stars, last push and archived flag. Cheap enough for daily builds."""
    tok = tok or token()
    if not tok:
        raise SystemExit("Set GITHUB_TOKEN to fetch repository stats")
    wanted = [(u, p) for u in urls if (p := parse(u))]
    out: dict[str, dict] = {}
    for i in range(0, len(wanted), batch):
        chunk = wanted[i : i + batch]
        parts = [
            f"r{n}: repository(owner: {json.dumps(o)}, name: {json.dumps(r)}) {{ {LIGHT} }}"
            for n, (_, (o, r)) in enumerate(chunk)
        ]
        data = _query(tok, "query {" + "\n".join(parts) + "}").get("data") or {}
        for n, (url, _) in enumerate(chunk):
            if repo := data.get(f"r{n}"):
                out[url] = {"stars": repo["stargazerCount"], "archived": repo["isArchived"], "pushed_at": repo["pushedAt"]}
    return out


def fetch(urls: list[str], tok: str | None = None, batch: int = 60) -> dict[str, dict]:
    """Map each GitHub URL to its facts. Missing or private repositories are left out."""
    tok = tok or token()
    if not tok:
        raise SystemExit("Set GITHUB_TOKEN to fetch repository facts")
    wanted = [(u, p) for u in urls if (p := parse(u))]
    out: dict[str, dict] = {}
    for i in range(0, len(wanted), batch):
        chunk = wanted[i : i + batch]
        parts = [
            f"r{n}: repository(owner: {json.dumps(o)}, name: {json.dumps(r)}) {{ {FIELDS} }}"
            for n, (_, (o, r)) in enumerate(chunk)
        ]
        data = _query(tok, "query {" + "\n".join(parts) + "}").get("data") or {}
        for n, (url, _) in enumerate(chunk):
            repo = data.get(f"r{n}")
            if not repo:
                continue
            out[url] = {
                "full_name": repo["nameWithOwner"],
                "name": repo["name"],
                "description": repo["description"],
                "homepage": repo["homepageUrl"] or None,
                "stars": repo["stargazerCount"],
                "archived": repo["isArchived"],
                "pushed_at": repo["pushedAt"],
                "license": (repo["licenseInfo"] or {}).get("spdxId"),
                "language": (repo["primaryLanguage"] or {}).get("name"),
                "topics": [t["topic"]["name"] for t in repo["repositoryTopics"]["nodes"]],
            }
    return out
