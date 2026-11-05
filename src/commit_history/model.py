"""Data model shared by the GraphQL and git-log collectors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

BOT_EMAILS = frozenset({"actions@github.com", "noreply@github.com"})
VERSION_TAG = re.compile(r"v\d")


@dataclass(frozen=True)
class Commit:
    """One commit on a repository's default branch.

    Field names follow the ``commits.csv`` schema of the ORCA commit-history
    visual so the file can be read by the unmodified visual code.
    """

    commit_hash: str
    decorations: str
    committer_email: str
    committer_name: str
    commit_time: str
    author_email: str
    author_name: str
    author_time: str
    commit_title: str
    files_changed: int | None
    line_insertions: int
    line_deletions: int
    repository: str
    author_login: str | None
    parents: int

    @property
    def is_merge(self) -> bool:
        return self.parents > 1

    @property
    def is_release(self) -> bool:
        """Mirror the visual: a decoration containing ``v`` followed by a digit."""
        return bool(VERSION_TAG.search(self.decorations))

    @property
    def is_bot(self) -> bool:
        """Automation accounts: ``[bot]`` suffixes and GitHub's own author identities."""
        name = self.author_name.strip().lower()
        email = self.author_email.strip().lower()
        if name.endswith("[bot]") or "[bot]@" in email:
            return True
        if email in BOT_EMAILS:
            return True
        return self.author_login is not None and self.author_login.lower().endswith("[bot]")


@dataclass(frozen=True)
class Repository:
    """A repository as listed from an organisation."""

    name: str
    full_name: str
    default_branch: str | None
    private: bool | None
    archived: bool
    fork: bool
    empty: bool
    pushed_at: str | None

    @property
    def owner(self) -> str:
        return self.full_name.split("/", 1)[0]

    @property
    def slug(self) -> str:
        return slug_for(self.name)


def slug_for(name: str) -> str:
    """Directory name for a repository: GitHub names are already filesystem safe."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", name).strip(".")
    if not cleaned or cleaned.startswith("_"):
        raise ValueError(f"cannot derive a data directory name from {name!r}")
    return cleaned


def git_timestamp(iso_timestamp: str) -> str:
    """Convert ``2023-10-15T07:08:59Z`` to git's ``2023-10-15 07:08:59 +0000`` form in UTC."""
    moment = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S +0000")


def iso_timestamp(git_time: str) -> str:
    """Convert git's ``2023-10-15 07:08:59 +0100`` form to ISO 8601 in UTC."""
    moment = datetime.strptime(git_time.strip(), "%Y-%m-%d %H:%M:%S %z")
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def subject_of(message: str | None, headline: str | None = None) -> str:
    """Git's commit subject: the first paragraph of the message with its line breaks turned into spaces.

    GitHub's ``messageHeadline`` is the first line only and is cut at about 72 characters with an
    ellipsis, so the full ``message`` is preferred and the headline is only a fallback.
    """
    lines: list[str] = []
    for line in (message or "").replace("\r\n", "\n").split("\n"):
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line)
    subject = " ".join(lines).strip()
    return subject or (headline or "").strip()


def decorations_for(tags: list[str]) -> str:
    """Render tag names the way ``git log --format=%D`` does, version-like tags first."""
    ordered = sorted(tags, key=lambda tag: (0 if VERSION_TAG.search(tag) else 1, tag))
    return ", ".join(f"tag: {tag}" for tag in ordered)
