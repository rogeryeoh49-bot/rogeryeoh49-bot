#!/usr/bin/env python3
"""Refresh the four most recent meaningful project updates in the profile README.

Uses only public GitHub commit metadata. Keeps everything outside the activity
markers unchanged. Called by the scheduled GitHub Actions workflow.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import urllib.request

OWNER = "rogeryeoh49-bot"
README = Path("README.md")
START = "<!-- RECENT_ACTIVITY_START -->"
END = "<!-- RECENT_ACTIVITY_END -->"
MAX_ITEMS = 4
MAX_AGE_DAYS = 180

# Deliberately curated: these are projects Roger wants represented on his profile.
PROJECTS = {
    "Radio-DIAL": ("Radio DIAL", "📻", "A free macOS radio and podcast player."),
    "FrameFloat": ("FrameFloat", "🖥️", "A lightweight macOS refresh-rate monitor."),
    "cie-paper-marking-skill": ("CIE Paper Marking Skill", "🤖", "A Codex skill for grading exam papers and annotating PDFs."),
    "digital-fly": ("DesktopFly", "🪰", "A desktop fly with brain-inspired simulation and movement."),
    "LinerNotes": ("LinerNotes", "🎵", "A SwiftUI app for discovering music samples and production details."),
}

SUBSTANTIVE = re.compile(
    r"\b(release|ship|add|implement|integrate|introduce|support|improve|fix|upgrade|feat|feature|build|rework|refactor|require|enable)\b",
    re.IGNORECASE,
)
TRIVIAL = re.compile(
    r"\b(readme|docs?|documentation|typo|badge|links?|website|license|chore|formatting|initial commit)\b",
    re.IGNORECASE,
)


def api_get(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "roger-profile-activity-workflow",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if os.getenv("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as res:
        return json.load(res)


def clean(subject: str, max_length: int = 86) -> str:
    subject = subject.splitlines()[0].strip()
    subject = re.sub(r"\s+", " ", subject)
    subject = re.sub(r"([\\\[\]*_`])", r"\\\1", subject)
    return subject if len(subject) <= max_length else subject[: max_length - 1].rstrip() + "…"


def latest_substantive_commit(repo: str):
    url = f"https://api.github.com/repos/{OWNER}/{repo}/commits?per_page=30"
    now = dt.datetime.now(dt.timezone.utc)
    for commit in api_get(url):
        message = commit["commit"]["message"].splitlines()[0].strip()
        if TRIVIAL.search(message) or not SUBSTANTIVE.search(message):
            continue
        date = dt.datetime.fromisoformat(commit["commit"]["committer"]["date"].replace("Z", "+00:00"))
        if (now - date).days > MAX_AGE_DAYS:
            continue
        return {"repo": repo, "subject": message, "date": date, "url": commit["html_url"]}
    return None


def main() -> None:
    text = README.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
        raise RuntimeError("Expected a single properly ordered activity section in README.md")
    candidates = [c for r in PROJECTS if (c := latest_substantive_commit(r))]
    if len(candidates) < MAX_ITEMS:
        raise RuntimeError(f"Only {len(candidates)} meaningful project updates found; preserving existing README")
    candidates.sort(key=lambda c: c["date"], reverse=True)
    lines = []
    for item in candidates[:MAX_ITEMS]:
        name, emoji, description = PROJECTS[item["repo"]]
        period = item["date"].strftime("%b %Y")
        link = f"https://github.com/{OWNER}/{item['repo']}"
        message = clean(item["subject"])
        lines.append(
            f"- **{period} · [{name}]({link})** {emoji} — "
            f"{description} Latest: [{message}]({item['url']})."
        )
    new_region = START + "\n" + "\n".join(lines) + "\n" + END
    left = text.index(START)
    right = text.index(END) + len(END)
    updated = text[:left] + new_region + text[right:]
    if updated != text:
        README.write_text(updated, encoding="utf-8")
        print(f"Updated recent activity with {len(lines)} projects")
    else:
        print("No activity changes")


if __name__ == "__main__":
    main()
