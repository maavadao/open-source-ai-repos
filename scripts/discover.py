"""Find new open-source AI repos on GitHub and write a repo file for each.

Usage: python scripts/discover.py [--max-new 150] [--min-stars 300] [--dry-run]

Searches GitHub for repos tagged with AI topics and adds the ones that aren't listed yet:
  - established repos with at least --min-stars stars and a push in the last year, and
  - fast-rising ones created in the last 90 days with at least 100 stars.
Forks, archived repos, repos without a description and everything already in the directory (any
URL casing or rename) are skipped. Each new file takes the repo's own GitHub description and
topics; the category is guessed from the topics (falling back to "other"), so a maintainer can
fix it later with a normal pull request.

Needs GITHUB_TOKEN (the search API allows 30 requests a minute with one).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from directory import SLUG_RE, dumps, load, path_for, repo_files
from github_stats import token

# GitHub topics that mark a repo as part of the AI space.
TOPICS = [
    "ai", "artificial-intelligence", "llm", "large-language-models", "generative-ai", "ai-agents",
    "agents", "agentic-ai", "rag", "mcp", "mcp-server", "model-context-protocol", "chatgpt", "openai",
    "deep-learning", "machine-learning", "stable-diffusion", "diffusion-models", "nlp",
    "transformers", "langchain", "llama", "prompt-engineering", "speech-recognition",
    "text-to-speech", "computer-vision", "multimodal", "vector-database", "claude", "gemini",
]

# First matching topic wins, so list the specific categories before the broad ones.
CATEGORY_TOPICS = [
    ("mcp-servers", {"mcp", "mcp-server", "mcp-servers", "model-context-protocol"}),
    ("browser-automation", {"browser-automation", "web-scraping", "web-agent", "browser-use"}),
    ("vector-databases", {"vector-database", "vector-search", "vector-db", "embeddings"}),
    ("local-llms", {"ollama", "llama-cpp", "llamacpp", "gguf", "local-llm", "inference", "quantization", "vllm"}),
    ("skills-prompts", {"prompt-engineering", "prompts", "prompt", "claude-code", "claude-skills", "awesome-prompts"}),
    ("coding", {"code-generation", "copilot", "coding-assistant", "code-review", "ai-coding", "cursor"}),
    ("agents", {"ai-agents", "agents", "agentic-ai", "multi-agent", "autonomous-agents", "agent", "agentic"}),
    ("image", {"stable-diffusion", "diffusion-models", "text-to-image", "image-generation", "diffusion", "comfyui"}),
    ("video", {"text-to-video", "video-generation", "video-editing"}),
    ("speech", {"speech-recognition", "text-to-speech", "tts", "stt", "whisper", "asr", "voice"}),
    ("vision", {"computer-vision", "object-detection", "ocr", "image-segmentation", "yolo", "opencv"}),
    ("robotics", {"robotics", "reinforcement-learning", "embodied-ai", "ros"}),
    ("documents", {"document-parsing", "pdf", "document-ai", "ocr-pdf"}),
    ("search", {"search-engine", "semantic-search", "ai-search"}),
    ("chat", {"chatbot", "chatgpt", "chat-ui", "chatgpt-web", "open-webui"}),
    ("no-code", {"no-code", "low-code", "workflow-automation", "workflow"}),
    ("llm-apps", {"rag", "langchain", "llamaindex", "llm", "large-language-models", "llmops", "llm-framework"}),
    ("models", {"llama", "language-model", "foundation-models", "open-source-llm", "transformers", "multimodal"}),
    ("security", {"ai-security", "red-teaming", "jailbreak", "llm-security", "adversarial-attacks"}),
    ("education", {"education", "edtech", "tutoring"}),
    ("learning", {"tutorial", "course", "awesome", "awesome-list", "learning", "roadmap", "books", "cheatsheet"}),
    ("data-science", {"data-science", "data-analysis", "pandas", "jupyter-notebook", "visualization"}),
    ("ml-platforms", {"machine-learning", "deep-learning", "mlops", "pytorch", "tensorflow", "ml", "automl", "jax"}),
]


# Words that show a repo is really about AI, so a popular project that only carries a trendy
# topic (an "mcp" tag on a Java guide, say) isn't listed.
AI_RE = re.compile(
    r"\b(ai|a\.i\.|llms?|gpt\S*|agents?|agentic|rag|mcp|machine learning|deep learning|neural|"
    r"transformers?|diffusion|chatbots?|openai|anthropic|claude|gemini|llama|ollama|embeddings?|"
    r"prompts?|copilot|generative|nlp|computer vision|speech|tts|whisper|model context protocol)\b",
    re.I,
)


def is_ai(repo: dict) -> bool:
    """AI in the name or description, or several AI topics on the repo."""
    if AI_RE.search(f"{repo['name']} {repo.get('description') or ''}"):
        return True
    return len(set(repo.get("topics", [])) & set(TOPICS)) >= 3


def guess_category(repo: dict) -> str:
    have = set(repo.get("topics", []))
    text = f"{repo['name']} {repo.get('description') or ''}".lower()
    for category, wanted in CATEGORY_TOPICS:
        if have & wanted and (category != "mcp-servers" or "mcp" in text or "model context" in text):
            return category
    return "other"


def search(query: str, pages: int, tok: str) -> list[dict]:
    """Repos matching a GitHub search query, most-starred first (the API stops at 1,000 results)."""
    found: list[dict] = []
    for page in range(1, pages + 1):
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": query, "sort": "stars", "order": "desc", "per_page": 100, "page": page})
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {tok}",
            "User-Agent": "maavadao-open-source-ai-repos",
        })
        items = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    items = json.load(resp)["items"]
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429):  # search rate limit: wait out the minute
                    time.sleep(30 * (attempt + 1))
                elif exc.code == 422:  # beyond the last page
                    break
                else:
                    time.sleep(2 ** attempt)
            except urllib.error.URLError:
                time.sleep(2 ** attempt)
        time.sleep(2.2)  # stay under 30 searches a minute
        if not items:
            break
        found.extend(items)
        if len(items) < 100:
            break
    return found


def clean(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", re.sub(r":[a-z0-9_+-]+:", "", text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def listed() -> tuple[set[str], set[str]]:
    """Repository URLs (lower case) and slugs already in the directory."""
    urls, slugs = set(), set()
    for path in repo_files():
        urls.add(str(load(path).get("repository", "")).rstrip("/").lower())
        slugs.add(path.stem)
    return urls, slugs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-new", type=int, default=150)
    ap.add_argument("--min-stars", type=int, default=300)
    ap.add_argument("--pages", type=int, default=10, help="search pages per topic (100 repos each)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tok = token()
    if not tok:
        raise SystemExit("Set GITHUB_TOKEN to search GitHub")

    today = dt.date.today()
    year_ago = (today - dt.timedelta(days=365)).isoformat()
    recent = (today - dt.timedelta(days=90)).isoformat()
    urls, slugs = listed()
    new: dict[str, dict] = {}

    for topic in TOPICS:
        for query in (
            f"topic:{topic} stars:>={args.min_stars} pushed:>{year_ago} fork:false archived:false",
            f"topic:{topic} stars:>=100 created:>{recent} fork:false archived:false",
        ):
            for repo in search(query, args.pages, tok):
                url = repo["html_url"].rstrip("/").lower()
                if url in urls or url in new or repo.get("fork") or repo.get("archived"):
                    continue
                if len((repo.get("description") or "").strip()) < 10 or not is_ai(repo):
                    continue
                new[url] = repo
        print(f"{topic}: {len(new)} new so far", flush=True)

    # Most-starred first, so a capped run adds the biggest ones and the rest wait for tomorrow.
    chosen = sorted(new.values(), key=lambda r: -r["stargazers_count"])[: args.max_new]
    written = 0
    for repo in chosen:
        slug = re.sub(r"[^a-z0-9]+", "-", repo["name"].lower()).strip("-")[:64].strip("-")
        if not SLUG_RE.match(slug or "") or slug in slugs:
            slug = re.sub(r"[^a-z0-9]+", "-", repo["full_name"].lower()).strip("-")[:64].strip("-")
        if not SLUG_RE.match(slug or "") or slug in slugs:
            continue
        topics = repo.get("topics", [])
        data = {
            "name": clean(repo["name"], 80),
            "description": clean(repo["description"], 300),
            "category": guess_category(repo),
            "tags": [t for t in topics if re.match(r"^[a-z0-9][a-z0-9-]{0,39}$", t)][:8],
            "repository": repo["html_url"],
            "website": repo.get("homepage") if re.match(r"^https?://\S+$", repo.get("homepage") or "") else None,
            "license": (repo.get("license") or {}).get("spdx_id"),
            "language": repo.get("language"),
            "added": today,
        }
        if data["license"] in ("NOASSERTION", "Other"):
            data["license"] = None
        data = {k: v for k, v in data.items() if v not in (None, [], "")}
        slugs.add(slug)
        written += 1
        if args.dry_run:
            print(f"would add {slug} ({data['category']}, {repo['stargazers_count']} stars)")
            continue
        path = path_for(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(data))
    print(f"found {len(new)} new repos; {'would write' if args.dry_run else 'wrote'} {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
