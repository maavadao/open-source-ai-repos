"""Build dist/contributors.json: who contributes to the most-starred repos in the directory.

Usage: python scripts/build_contributors.py [--top 500] [--per-repo 30] [--reuse URL] [--cache FILE]
                                   [--previous URL --refresh N]

Reads dist/index.json (run build_index.py first), asks GitHub for the top contributors of the
`--top` most-starred repos, and writes one entry per developer: their GitHub login and user id
(for the avatar) and how many commits they made to each repo. Nothing else about a person is
collected. Bots, automation accounts and every login in opt-out.toml are left out.

With --cache, each repo's result is saved to FILE as it is fetched, so an interrupted run resumes
where it stopped and repos already in the cache cost no API calls. When GitHub's hourly limit is
nearly used up the run sleeps until it resets instead of stopping.

With --previous and --refresh N (the daily run), the last published file seeds the cache and only
N repos are asked about: those not in it yet, then a window that moves on each day, so every repo
is refreshed every few weeks while staying inside GitHub's hourly limit for the Actions token.

With --reuse, the last published file is downloaded instead of calling GitHub (used on merges,
so only the daily build spends API calls); opt-outs are still applied to it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

from directory import ROOT
from github_stats import parse, token


# Automation accounts that GitHub reports as ordinary users.
AUTOMATION = {
    "actions-user", "github-actions", "web-flow", "dependabot", "renovate-bot", "pre-commit-ci",
    "allcontributors", "imgbot", "semantic-release-bot", "greenkeeperio-bot", "snyk-bot", "codecov-io",
    "claude", "copilot", "copilot-swe-agent", "cursoragent", "devin-ai-integration", "coderabbitai",
    "gemini-code-assist", "openhands-agent", "sweep-ai", "codex", "jules", "google-labs-jules",
}


def is_person(login: str) -> bool:
    low = login.lower()
    return low not in AUTOMATION and not low.endswith(("[bot]", "-bot", "_bot"))


def opted_out() -> set[str]:
    with (ROOT / "opt-out.toml").open("rb") as fh:
        return {login.lower() for login in tomllib.load(fh).get("logins", [])}


def contributors(owner: str, name: str, per_repo: int, tok: str) -> list[dict] | None:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{name}/contributors?per_page={per_repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {tok}",
            "User-Agent": "maavadao-open-source-ai-repos",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 204:  # empty repository
                    return []
                if int(resp.headers.get("X-RateLimit-Remaining", "100")) < 5:
                    wait = max(int(resp.headers.get("X-RateLimit-Reset", "0")) - int(time.time()), 0) + 5
                    print(f"rate limit nearly used up; sleeping {wait}s")
                    time.sleep(wait)
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404, 451):  # too large to list, gone, or blocked
                return None
            time.sleep(2 ** attempt)
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    return None


def seed_from(published: dict) -> dict[str, list]:
    """Per-repo contributor lists rebuilt from a published contributors.json."""
    cache: dict[str, list] = {}
    for d in published["developers"]:
        for slug, commits in d["repos"]:
            cache.setdefault(slug, []).append(
                {"login": d["login"], "id": d["id"], "type": "User", "contributions": commits})
    return cache


def build(index: dict, top: int, per_repo: int, tok: str, cache_path: Path | None = None,
          seed: dict[str, list] | None = None, refresh: int = 0) -> dict:
    repos = [r for r in index["repos"] if not r.get("archived") and parse(r["repository"])][:top]
    people: dict[str, dict] = {}
    covered = 0
    cache: dict[str, list | None] = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())
        print(f"cache has {len(cache)} repos")
    fetch: set[str] | None = None
    if seed is not None:
        cache = {r["slug"]: seed[r["slug"]] for r in repos if r["slug"] in seed}
        missing = [r["slug"] for r in repos if r["slug"] not in cache]
        day = (dt.datetime.now(dt.timezone.utc).date() - dt.date(1970, 1, 1)).days
        start = (day * refresh) % len(repos)
        window = [repos[(start + i) % len(repos)]["slug"] for i in range(min(refresh, len(repos)))]
        fetch = set((missing + window)[:refresh])
        for slug in fetch:
            cache.pop(slug, None)
        print(f"seeded {len(cache)} repos; fetching {len(fetch)}")
    for n, repo in enumerate(repos, 1):
        slug = repo["slug"]
        if slug in cache:
            found = cache[slug]
        elif fetch is not None and slug not in fetch:
            continue
        else:
            found = contributors(*parse(repo["repository"]), per_repo, tok)
            # Keep only what is published, so the cache holds no more than the output does.
            if found is not None:
                found = [{"login": c["login"], "id": c["id"], "type": c.get("type"), "contributions": c["contributions"]}
                         for c in found]
            cache[slug] = found
            if cache_path and len(cache) % 100 == 0:
                cache_path.write_text(json.dumps(cache, separators=(",", ":")))
        if found is None:
            continue
        covered += 1
        for c in found:
            if c.get("type") != "User" or not is_person(c["login"]):
                continue
            p = people.setdefault(c["login"], {"login": c["login"], "id": c["id"], "repos": []})
            p["repos"].append([repo["slug"], c["contributions"]])
        if n % 100 == 0:
            print(f"{n}/{len(repos)} repos", flush=True)
    if cache_path:
        cache_path.write_text(json.dumps(cache, separators=(",", ":")))
    return {"repos_covered": covered, "developers": list(people.values())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=500)
    ap.add_argument("--per-repo", type=int, default=30)
    ap.add_argument("--reuse")
    ap.add_argument("--previous", help="published contributors.json to seed from, with --refresh")
    ap.add_argument("--refresh", type=int, default=0, help="repos to ask GitHub about in this run")
    ap.add_argument("--cache", help="JSON file that keeps each repo's result between runs")
    ap.add_argument("--index", default=str(ROOT / "dist" / "index.json"))
    ap.add_argument("--out", default=str(ROOT / "dist" / "contributors.json"))
    args = ap.parse_args()

    data = None
    if args.reuse:
        try:
            with urllib.request.urlopen(args.reuse, timeout=60) as resp:
                data = json.load(resp)
            print(f"reusing {args.reuse}")
        except Exception as exc:  # noqa: BLE001 - first build has nothing to reuse
            print(f"nothing to reuse ({exc}); building from GitHub")
    if data is None:
        tok = token()
        if not tok:
            raise SystemExit("Set GITHUB_TOKEN to fetch contributors")
        seed = None
        if args.previous and args.refresh:
            try:
                with urllib.request.urlopen(args.previous, timeout=120) as resp:
                    seed = seed_from(json.load(resp))
            except Exception as exc:  # noqa: BLE001 - first build has nothing to seed from
                print(f"nothing to seed from ({exc})")
        data = build(json.loads(Path(args.index).read_text()), args.top, args.per_repo, tok,
                     Path(args.cache) if args.cache else None, seed, args.refresh)

    skip = opted_out()
    developers = [d for d in data["developers"] if d["login"].lower() not in skip and is_person(d["login"])]
    for d in developers:
        d["repos"].sort(key=lambda r: -r[1])
        d["total"] = sum(r[1] for r in d["repos"])
    # People active across several big projects first, then by commits.
    developers.sort(key=lambda d: (-len(d["repos"]), -d["total"], d["login"].lower()))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": data.get("generated_at") if args.reuse and "generated_at" in data
        else dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repos_covered": data["repos_covered"],
        "count": len(developers),
        "developers": developers,
    }, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {out} with {len(developers)} developers from {data['repos_covered']} repos")


if __name__ == "__main__":
    main()
