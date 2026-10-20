# Contributing

Thank you for helping. Every change is a pull request that a maintainer reviews, and you don't
need to know Python or Git well to make one: GitHub's web editor is enough.

## What belongs here

- **Open source.** The code is public and under an open-source licence. Hosted products with no
  public code belong in the [marketplace registry](https://github.com/maavadao/marketplace-registry).
- **AI.** It builds, runs, uses, teaches or evaluates AI.
- **Alive.** It works today. Archived and abandoned projects are removed.
- **Not a fork** of a repo that's already listed, unless it has become its own project.

## Add a repo

### The quick way (in your browser)

1. Open the [`repos/`](repos) folder, then the folder for the first character of the repo's name
   (`a`, `b`, … or `0-9`).
2. Click **Add file → Create new file** and name it `<slug>.toml`, for example `aider.toml`. The
   slug is lowercase letters, digits and hyphens, usually the repository's name.
3. Paste in [`templates/repo.toml`](templates/repo.toml) and fill it in.
4. Click **Propose changes**, then **Create pull request**.

### With the helper script

```bash
git clone https://github.com/<you>/open-source-ai-repos && cd open-source-ai-repos
pip install -r requirements.txt   # needs Python 3.11 or newer
python scripts/add_repo.py https://github.com/owner/repo --category coding
python scripts/validate.py
```

`add_repo.py` reads the name, description, licence, language, website and topics from GitHub and
writes the file for you. Read it through, fix anything that isn't clear, and open a pull request.

## The fields

| Field | Required | What to put |
| --- | --- | --- |
| `name` | yes | The project's name, as its makers write it |
| `description` | yes | One or two plain sentences, 10–300 characters: what it does and who it helps |
| `category` | yes | One id from [`categories.toml`](categories.toml) |
| `repository` | yes | Link to the source code (GitHub, GitLab, Codeberg or Hugging Face) |
| `added` | yes | Today's date, written `2026-10-20` with no quotes |
| `tags` | no | Up to 8 short lowercase tags, like `rag` or `speech-to-text` |
| `website`, `docs` | no | Home page and documentation |
| `license` | no | SPDX identifier: `MIT`, `Apache-2.0`, `GPL-3.0`… |
| `language` | no | Main programming language |
| `skill_level` | no | `beginner`, `intermediate` or `advanced` |
| `runs_locally` | no | `true` if people can run it on their own machine or server |

### The file format in 30 seconds

Repo files are [TOML](https://toml.io). Each line is one field:

```toml
name = "Whisper"                         # text goes in "double quotes"
tags = ["speech-to-text", "audio"]       # lists go in [square brackets], items separated by commas
runs_locally = true                      # true or false, no quotes
added = 2026-10-20                       # dates have no quotes
```

Anything after `#` is a comment. Order doesn't matter, but please keep the order of the template.
If a quote mark appears inside a description, write it as `\"`.

Stars and last activity aren't in the files. They're read from GitHub every day when the index
is built, so they never go stale.

### Writing a good description

- Say what it does and who it's for: "Turns scanned PDFs into editable Markdown" beats "A
  powerful, next-generation document AI platform".
- Use the project's own description or your own words. **Never copy text from another directory,
  review site or blog.**
- British spelling, no marketing words, no emoji.

## Fix or remove a repo

Edit or delete its file and open a pull request, saying why in the description. If you'd rather
not edit it yourself, [open an issue](../../issues/new/choose).

## How review works

1. CI runs `python scripts/validate.py` on every pull request: the schema, the file's folder and
   name, the category, and duplicate repositories.
2. A maintainer checks the repo is open source, AI-related and alive, and that the description
   is clear and original.
3. Once merged, the repo appears on [maavadao.com/repos](https://maavadao.com/repos) after the next
   index build (on every merge, and daily).

## The developer pages

[maavadao.com/developers](https://maavadao.com/developers) shows who contributes to the most-starred
repos here. Once a day, `scripts/build_contributors.py` asks GitHub for the top contributors of
the 500 most-starred repos and publishes `contributors.json`: each person's GitHub login, their
user id (for the avatar) and their commit count per repo. That's all. No names, emails,
locations or bios are collected.

**Don't want to be listed?** Open the [remove me](../../issues/new?template=remove-me.yml) issue,
or add your login to [`opt-out.toml`](opt-out.toml) in a pull request. Opt-outs are merged without
discussion and take effect on the next build.

## Code of conduct

Be kind, assume good intent and keep discussion about the work. Maintainers may close pull
requests or issues that are spam, self-promotion of closed products, or disrespectful.
