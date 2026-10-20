"""Start a new repo file from a GitHub repository.

Usage: python scripts/add_repo.py https://github.com/owner/repo [--category coding]

Reads the repository's name, description, licence, language, website and topics from GitHub and
writes repos/<x>/<slug>.toml. Check the file, rewrite the description if it isn't clear, pick
the right category, then open a pull request. Works without a token for a handful of repos; set
GITHUB_TOKEN if you hit the rate limit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request

from directory import ROOT, SLUG_RE, categories, dumps, load, path_for, repo_files
from github_stats import parse, token


def repo_facts(owner: str, name: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{name}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "maavadao-open-source-ai-repos"},
    )
    if tok := token():
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--category", default="other")
    ap.add_argument("--slug")
    args = ap.parse_args()

    if args.category not in categories():
        print(f"category must be one of: {', '.join(categories())}")
        return 1
    pair = parse(args.url)
    if not pair:
        print("give a GitHub repository URL, like https://github.com/owner/repo")
        return 1
    repo = repo_facts(*pair)
    for existing in repo_files():
        if str(load(existing).get("repository", "")).rstrip("/").lower() == repo["html_url"].lower():
            print(f"{repo['full_name']} is already listed in {existing.relative_to(ROOT)}")
            return 1
    slug = args.slug or re.sub(r"[^a-z0-9]+", "-", repo["name"].lower()).strip("-")
    if not SLUG_RE.match(slug):
        print(f"can't make a slug from {repo['name']!r}; pass --slug")
        return 1
    path = path_for(slug)
    if path.exists():
        print(f"{path} already exists; pass --slug to pick another name")
        return 1

    data = {
        "name": repo["name"],
        "description": (repo.get("description") or "TODO: what it does and who it helps.").strip(),
        "category": args.category,
        "tags": [t for t in repo.get("topics", []) if re.match(r"^[a-z0-9][a-z0-9-]{0,39}$", t)][:8],
        "repository": repo["html_url"],
        "website": repo.get("homepage") or None,
        "license": (repo.get("license") or {}).get("spdx_id"),
        "language": repo.get("language"),
        "added": dt.date.today(),
    }
    data = {k: v for k, v in data.items() if v not in (None, [], "")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(data))
    print(f"wrote {path}. Check it, then run: python scripts/validate.py {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
