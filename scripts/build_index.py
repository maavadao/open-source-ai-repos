"""Build dist/index.json: every repo plus live GitHub facts (stars, last push, archived).

Usage: python scripts/build_index.py [--no-stats] [--out PATH]
Without GITHUB_TOKEN (or with --no-stats) the index is built from the repo files alone.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from directory import ROOT, categories, load, repo_files
from github_stats import fetch_stats, token

FIELDS = ("name", "description", "category", "tags", "repository", "website", "docs", "license",
          "language", "skill_level", "runs_locally", "added")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-stats", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "dist" / "index.json"))
    args = ap.parse_args()

    repos = []
    for path in repo_files():
        data = load(path)
        item = {"slug": path.stem}
        for key in FIELDS:
            value = data.get(key)
            if value is None or value == []:
                continue
            item[key] = value.isoformat() if isinstance(value, dt.date) else value
        repos.append(item)

    stats = {} if args.no_stats or not token() else fetch_stats([t["repository"] for t in repos])
    for item in repos:
        s = stats.get(item["repository"])
        if s:
            for key in ("stars", "forks", "open_issues", "watchers", "pushed_at", "created_at", "release"):
                if s.get(key) is not None:
                    item[key] = s[key]
            if s["archived"]:
                item["archived"] = True

    repos.sort(key=lambda t: (-t.get("stars", 0), t["slug"]))
    cats = categories()
    counts = {c: 0 for c in cats}
    for t in repos:
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    index = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "count": len(repos),
        "categories": {c: {**meta, "count": counts[c]} for c, meta in cats.items()},
        "repos": repos,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {out} with {len(repos)} repos ({len(stats)} with GitHub facts)")


if __name__ == "__main__":
    main()
