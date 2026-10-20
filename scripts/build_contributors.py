"""Build dist/contributors.json: who contributes to the most-starred repos in the directory.

Usage: python scripts/build_contributors.py [--top 500] [--per-repo 30] [--reuse URL]

Reads dist/index.json (run build_index.py first), asks GitHub for the top contributors of the
`--top` most-starred repos, and writes one entry per developer: their GitHub login and user id
(for the avatar) and how many commits they made to each repo. Nothing else about a person is
collected. Bots, automation accounts and every login in opt-out.toml are left out.

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
                    raise SystemExit("GitHub rate limit nearly used up; stopping")
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404, 451):  # too large to list, gone, or blocked
                return None
            time.sleep(2 ** attempt)
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    return None


def build(index: dict, top: int, per_repo: int, tok: str) -> dict:
    repos = [r for r in index["repos"] if not r.get("archived") and parse(r["repository"])][:top]
    people: dict[str, dict] = {}
    covered = 0
    for n, repo in enumerate(repos, 1):
        found = contributors(*parse(repo["repository"]), per_repo, tok)
        if found is None:
            continue
        covered += 1
        for c in found:
            if c.get("type") != "User" or not is_person(c["login"]):
                continue
            p = people.setdefault(c["login"], {"login": c["login"], "id": c["id"], "repos": []})
            p["repos"].append([repo["slug"], c["contributions"]])
        if n % 100 == 0:
            print(f"{n}/{len(repos)} repos")
    return {"repos_covered": covered, "developers": list(people.values())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=500)
    ap.add_argument("--per-repo", type=int, default=30)
    ap.add_argument("--reuse")
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
        data = build(json.loads(Path(args.index).read_text()), args.top, args.per_repo, tok)

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
