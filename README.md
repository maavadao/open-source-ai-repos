# Open-source AI repos

A free, community-maintained directory of open-source AI repositories, for anyone who wants to
learn, teach, research or build with AI. Browse it on [maavadao.com/repos](https://maavadao.com/repos),
and see who builds them on [maavadao.com/developers](https://maavadao.com/developers).

Part of [maavaDao](https://maavadao.com): community-governed AI and blockchain technologies for
education. Build it. Own it. Share it.

## How it works

Every repo is one small [TOML](https://toml.io) file: one `field = value` per line, text in
`"double quotes"`, lists in `[square brackets]`. No indentation to get right, and you can leave
notes with `#`.

```toml
# repos/a/aider.toml
name = "aider"
description = "AI pair programming in your terminal"
category = "coding"
tags = ["cli", "llm", "pair-programming"]
repository = "https://github.com/Aider-AI/aider"
website = "https://aider.chat"
license = "Apache-2.0"
language = "Python"
added = 2026-10-20
```

Files live in `repos/<first character>/<slug>.toml` (`repos/0-9/` for names that start with a
digit), so no folder gets too big to browse on GitHub. Each file names one category from
[`categories.toml`](categories.toml).

Every day, and on every merge, GitHub Actions publishes these files on GitHub Pages:

| File | What |
| --- | --- |
| [`index.json`](https://maavadao.github.io/open-source-ai-repos/index.json) | Every repo, with live stars, forks, open issues, watchers, latest release, last activity and archived status from GitHub |
| [`contributors.json`](https://maavadao.github.io/open-source-ai-repos/contributors.json) | The top 30 contributors of every repo in the directory (~87,000 developers): GitHub login, user id and commits per repo, nothing else |
| `history/<first character>.json` | Star history: every repo's star count, recorded daily since 20 October 2026 (GitHub no longer lists when each star was given, so there's no earlier history) |

All are free to use in your own projects.

## Add a repo

Read [CONTRIBUTING.md](CONTRIBUTING.md). In short: copy
[`templates/repo.toml`](templates/repo.toml) to `repos/<x>/<slug>.toml`, fill it in, and open a
pull request. CI checks it, and a maintainer reviews it. You can do all of this in GitHub's web
editor.

Can't open a pull request? [Suggest a repo](../../issues/new/choose) in an issue instead.

## Don't want to be listed as a contributor?

Open the [remove me](../../issues/new?template=remove-me.yml) issue, or add your GitHub login to
[`opt-out.toml`](opt-out.toml). We remove you on the next build, no questions asked.

## Layout

| Path | What |
| --- | --- |
| [`repos/`](repos) | One TOML file per repo |
| [`categories.toml`](categories.toml) | The categories, with names and descriptions |
| [`opt-out.toml`](opt-out.toml) | GitHub logins never shown on the developer pages |
| [`schema/repo.schema.json`](schema/repo.schema.json) | What a repo file may contain |
| [`templates/repo.toml`](templates/repo.toml) | A file to copy when adding a repo |
| [`scripts/validate.py`](scripts/validate.py) | Checks every file (CI runs it on each pull request) |
| [`scripts/add_repo.py`](scripts/add_repo.py) | Starts a repo file from a GitHub URL |
| [`scripts/build_index.py`](scripts/build_index.py) | Builds `dist/index.json` |
| [`scripts/build_contributors.py`](scripts/build_contributors.py) | Builds `dist/contributors.json` |
| [`scripts/build_history.py`](scripts/build_history.py) | Adds today's stars to `dist/history/` |

## Run it locally

Needs Python 3.11 or newer.

```bash
pip install -r requirements.txt
python scripts/validate.py
GITHUB_TOKEN=... python scripts/build_index.py   # or --no-stats to skip GitHub
GITHUB_TOKEN=... python scripts/build_contributors.py
```

## Where the descriptions come from

Each description is the project's own GitHub description, or a contributor's own words. We don't
copy reviews, rankings or write-ups from other directories or blogs.

## Licence

[Apache 2.0](LICENSE). The repos listed here have their own licences; see each project.
