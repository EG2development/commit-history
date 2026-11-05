"""Write the files the site reads: per-repository CSVs and ``index.json``."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .highlights import HighlightRule, entries_for, matches
from .model import Commit, Repository, iso_timestamp

SCHEMA_VERSION = 1
COMBINED_SLUG = "_all"
COLUMNS = (
    "commit_hash", "decorations", "committer_email", "committer_name", "commit_time",
    "author_email", "author_name", "author_time", "commit_title",
    "files_changed", "line_insertions", "line_deletions",
    "repository", "author_login", "parents",
)
HIGHLIGHT_COLUMNS = ("name", "email", "contribution")


def _row(commit: Commit, redact_emails: bool = False) -> list:
    return [
        commit.commit_hash, commit.decorations,
        "" if redact_emails else commit.committer_email, commit.committer_name,
        commit.commit_time,
        "" if redact_emails else commit.author_email, commit.author_name, commit.author_time,
        commit.commit_title,
        "" if commit.files_changed is None else commit.files_changed,
        commit.line_insertions, commit.line_deletions,
        commit.repository, commit.author_login or "", commit.parents,
    ]


def write_commits(directory: Path, commits: list[Commit], redact_emails: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "commits.csv"
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(_row(commit, redact_emails) for commit in commits)
    return target


def write_highlights(directory: Path, entries: list[dict[str, str]] | None) -> Path | None:
    target = directory / "highlights.csv"
    if entries is None:
        if target.exists():
            target.unlink()
        return None
    directory.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HIGHLIGHT_COLUMNS, lineterminator="\n",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)
    return target


def summarise(commits: list[Commit], rule: HighlightRule) -> dict:
    """Counts the index page shows for one dataset."""
    if not commits:
        return {"commits": 0, "contributors": 0, "first_commit": None, "last_commit": None,
                "insertions": 0, "deletions": 0, "releases": 0, "merge_commits": 0,
                "highlighted_commits": 0, "files_unavailable": 0}
    ordered = sorted(commits, key=lambda commit: commit.commit_time)
    return {
        "commits": len(commits),
        "contributors": len({commit.author_name.strip().lower() for commit in commits}),
        "first_commit": iso_timestamp(ordered[0].commit_time),
        "last_commit": iso_timestamp(ordered[-1].commit_time),
        "insertions": sum(commit.line_insertions for commit in commits),
        "deletions": sum(commit.line_deletions for commit in commits),
        "releases": sum(1 for commit in commits if commit.is_release),
        "merge_commits": sum(1 for commit in commits if commit.is_merge),
        "highlighted_commits": sum(1 for commit in commits if matches(rule, commit)),
        "files_unavailable": sum(1 for commit in commits if commit.files_changed is None),
    }


def repository_entry(repository: Repository, web_base: str, status: str, *,
                     commits: list[Commit] | None = None, rule: HighlightRule | None = None,
                     error: str | None = None) -> dict:
    entry = {
        "name": repository.name,
        "full_name": repository.full_name,
        "slug": repository.slug,
        "url": f"{web_base}/{repository.full_name}",
        "default_branch": repository.default_branch,
        "private": repository.private,
        "archived": repository.archived,
        "fork": repository.fork,
        "pushed_at": repository.pushed_at,
        "status": status,
        "error": error,
    }
    entry.update(summarise(commits or [], rule or HighlightRule("none", None)))
    return entry


def write_repository(data_dir: Path, repository: Repository, commits: list[Commit],
                     rule: HighlightRule, redact_emails: bool = False) -> None:
    directory = data_dir / repository.slug
    write_commits(directory, commits, redact_emails)
    write_highlights(directory, entries_for(rule, commits, redact_emails))


def write_combined(data_dir: Path, per_repository: dict[str, list[Commit]], rule: HighlightRule,
                   limit: int, redact_emails: bool = False) -> dict | None:
    """Write ``_all/commits.csv`` with every repository's commits, or skip when over ``limit``."""
    total = sum(len(commits) for commits in per_repository.values())
    directory = data_dir / COMBINED_SLUG
    if limit <= 0 or total == 0 or total > limit:
        shutil.rmtree(directory, ignore_errors=True)
        if total == 0 or limit <= 0:
            return None
        return {"slug": None, "skipped": True, "commits": total, "limit": limit}
    merged: list[Commit] = []
    for name, commits in per_repository.items():
        short = name.split("/", 1)[-1]
        for commit in commits:
            title = f"{short}: {commit.commit_title}" if commit.commit_title else short
            merged.append(Commit(**{**commit.__dict__, "commit_title": title}))
    merged.sort(key=lambda commit: commit.commit_time, reverse=True)
    write_commits(directory, merged, redact_emails)
    write_highlights(directory, entries_for(rule, merged, redact_emails))
    summary = {"slug": COMBINED_SLUG, "skipped": False, "limit": limit}
    summary.update(summarise(merged, rule))
    return summary


def write_index(data_dir: Path, index: dict) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "index.json"
    with target.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return target


def read_index(data_dir: Path) -> dict | None:
    target = data_dir / "index.json"
    if not target.exists():
        return None
    with target.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_index(*, organisation: str, title: str, host: str, source: str, since: str | None,
                rule: HighlightRule, repositories: list[dict], combined: dict | None,
                token_source: str | None, requests: int, points: int, redact_emails: bool = False) -> dict:
    ok = [entry for entry in repositories if entry["status"] == "ok"]
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "organisation": organisation,
        "title": title,
        "host": host,
        "source": source,
        "since": since,
        "emails": "redacted" if redact_emails else "included",
        "highlight": {"rule": rule.rule, "label": rule.label},
        "combined": combined,
        "totals": {
            "repositories": len(repositories),
            "repositories_ok": len(ok),
            "repositories_failed": sum(1 for entry in repositories if entry["status"] == "error"),
            "commits": sum(entry["commits"] for entry in ok),
            "highlighted_commits": sum(entry["highlighted_commits"] for entry in ok),
            "insertions": sum(entry["insertions"] for entry in ok),
            "deletions": sum(entry["deletions"] for entry in ok),
        },
        "run": {"token_source": token_source, "graphql_requests": requests, "graphql_points": points},
        "repositories": repositories,
    }
