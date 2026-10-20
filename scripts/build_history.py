"""Build dist/history/<shard>.json: star history for every repo, one file per first character.

Usage: python scripts/build_history.py [--previous URL] [--out dist/history]

Each run adds today's star count (from dist/index.json) to every repo's history. History is
kept by downloading the last published files from --previous, so nothing is lost between runs.
GitHub no longer lists who starred a repo and when, so history starts on the day a repo is first
tracked here (20 October 2026 for the first set).

Points are [day, stars], where day counts days since 1970-01-01. Recent points are daily; older
ones are thinned to one a week, and one a month after two years.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

from directory import ROOT

SHARDS = [chr(c) for c in range(ord("a"), ord("z") + 1)] + ["0-9"]


def shard_of(slug: str) -> str:
    return slug[0] if slug[0].isalpha() else "0-9"


def load_previous(base: str | None) -> dict[str, dict] | None:
    """All published history, or None if nothing is published yet. Any other error stops the build."""
    if not base:
        return None
    repos: dict[str, dict] = {}
    found = False
    for shard in SHARDS:
        try:
            with urllib.request.urlopen(f"{base.rstrip('/')}/history/{shard}.json", timeout=60) as resp:
                repos.update(json.load(resp)["repos"])
                found = True
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    return repos if found else None


def thin(points: list[list[int]], today: int) -> list[list[int]]:
    """Daily for 60 days, weekly to two years, monthly before that; the last point per bucket wins."""
    buckets: dict[tuple[int, int], list[int]] = {}
    for day, stars in sorted(points):
        age = today - day
        size = 1 if age <= 60 else 7 if age <= 730 else 30
        buckets[(size, day // size)] = [day, stars]
    return sorted(buckets.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous")
    ap.add_argument("--index", default=str(ROOT / "dist" / "index.json"))
    ap.add_argument("--out", default=str(ROOT / "dist" / "history"))
    args = ap.parse_args()

    index = json.loads(Path(args.index).read_text())
    history = load_previous(args.previous) or {}
    print(f"starting from published history for {len(history)} repos")

    today = (dt.datetime.now(dt.timezone.utc).date() - dt.date(1970, 1, 1)).days
    live = {r["slug"]: r for r in index["repos"]}
    history = {slug: h for slug, h in history.items() if slug in live}

    for slug, repo in live.items():
        if repo.get("stars") is None:
            continue
        h = history.setdefault(slug, {"p": []})
        h["p"] = thin([p for p in h["p"] if p[0] != today] + [[today, repo["stars"]]], today)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    generated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for shard in SHARDS:
        repos = {slug: h for slug, h in sorted(history.items()) if shard_of(slug) == shard}
        (out / f"{shard}.json").write_text(
            json.dumps({"generated_at": generated, "repos": repos}, separators=(",", ":"))
        )
    print(f"wrote {out} for {len(history)} repos")


if __name__ == "__main__":
    main()
