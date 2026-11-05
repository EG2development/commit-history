"""Read commit history from a local clone with ``git log``.

This is the route the original ORCA visual used. It needs no token and works
for repositories that are not on GitHub, but it reads one clone at a time.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from .model import Commit

RECORD = "\x1e"
FIELD = "\x1f"
FORMAT = FIELD.join(["%H", "%D", "%ce", "%cN", "%ci", "%ae", "%aN", "%ai", "%s", "%P"])
SHORTSTAT = re.compile(
    r"(\d+) files? changed"
    r"(?:, (\d+) insertions?\(\+\))?"
    r"(?:, (\d+) deletions?\(-\))?"
)


class GitLogError(RuntimeError):
    """``git log`` could not be run or returned an error."""


def log_command(repo_dir: Path, ref: str) -> list[str]:
    """The exact ``git log`` invocation, exposed for documentation and tests."""
    return [
        "git", "-C", str(repo_dir), "log", ref,
        f"--pretty=format:{RECORD}{FORMAT}",
        "--shortstat", "--decorate=short", "-M20", "--encoding=UTF-8", "--no-color",
    ]


def read_log(repo_dir: Path, ref: str = "HEAD", run: Callable = subprocess.run) -> str:
    """Run ``git log`` for ``ref`` in ``repo_dir`` and return its raw output."""
    if not (repo_dir / ".git").exists() and not (repo_dir / "HEAD").exists():
        raise GitLogError(f"{repo_dir} is not a git repository")
    try:
        result = run(log_command(repo_dir, ref), capture_output=True, text=True,
                     encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        raise GitLogError(f"could not run git: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        raise GitLogError(f"git log failed: {detail[-1] if detail else result.returncode}")
    return result.stdout


def tag_decorations(decorations: str) -> str:
    """Keep only the ``tag: name`` entries of a ``%D`` decoration string."""
    tags = [part.strip() for part in decorations.split(",") if part.strip().startswith("tag: ")]
    return ", ".join(tags)


def parse_shortstat(text: str) -> tuple[int, int, int]:
    """Files, insertions and deletions from a ``--shortstat`` line; zeros when absent."""
    match = SHORTSTAT.search(text)
    if not match:
        return 0, 0, 0
    files, insertions, deletions = match.groups()
    return int(files), int(insertions or 0), int(deletions or 0)


def parse_log(output: str, repository: str) -> list[Commit]:
    """Turn ``read_log`` output into commits, newest first."""
    commits: list[Commit] = []
    for record in output.split(RECORD):
        if not record.strip():
            continue
        head, _, stats = record.partition("\n")
        fields = head.split(FIELD)
        if len(fields) != 10:
            raise GitLogError(f"unexpected git log record with {len(fields)} fields: {head[:80]!r}")
        (sha, decorations, committer_email, committer_name, commit_time,
         author_email, author_name, author_time, title, parents) = fields
        parent_count = len(parents.split()) if parents.strip() else 0
        files, insertions, deletions = parse_shortstat(stats)
        commits.append(Commit(
            commit_hash=sha,
            decorations=tag_decorations(decorations),
            committer_email=committer_email,
            committer_name=committer_name,
            commit_time=commit_time.strip(),
            author_email=author_email,
            author_name=author_name,
            author_time=author_time.strip(),
            commit_title=title.strip(),
            files_changed=files,
            line_insertions=insertions,
            line_deletions=deletions,
            repository=repository,
            author_login=None,
            parents=parent_count,
        ))
    return commits
