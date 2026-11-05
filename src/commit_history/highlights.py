"""Decide which contributors the visual draws as hexagons.

The original visual marks "ORCA recipients". Here the second dataset is a
generic *highlight* list, built per repository from one of these rules:

* ``none``     no hexagons; no ``highlights.csv`` is written
* ``bots``     automation accounts (``[bot]`` names or emails, GitHub Actions, GitHub web commits)
* ``outside``  authors whose GitHub account is not a member of the organisation,
               including bots and emails that are not linked to any account
* ``members``  authors whose GitHub account is a member of the organisation
* a CSV path   a hand-written list with ``name``, ``email`` and optional ``contribution`` columns
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .model import Commit

BUILT_IN_RULES = ("none", "bots", "outside", "members")
# Written in place of emails in highlights.csv when emails are redacted. It must be non-empty:
# the visual treats an empty email in the list as matching every commit whose email is empty.
REDACTED_EMAIL = "redacted"


@dataclass(frozen=True)
class HighlightRule:
    rule: str
    label: str | None
    members: frozenset[str] = frozenset()
    entries: tuple[dict[str, str], ...] = field(default_factory=tuple)

    @property
    def needs_members(self) -> bool:
        return self.rule in ("outside", "members")


def parse_rule(value: str) -> tuple[str, Path | None]:
    """``(rule, path)`` for a command-line value: a built-in name or a CSV file."""
    cleaned = value.strip()
    if cleaned.lower() in BUILT_IN_RULES:
        return cleaned.lower(), None
    path = Path(cleaned)
    if path.suffix.lower() == ".csv":
        return "file", path
    raise ValueError(f"--highlight must be one of {', '.join(BUILT_IN_RULES)} or a .csv path, not {value!r}")


def read_entries(path: Path) -> tuple[dict[str, str], ...]:
    """Read a hand-written highlight list; ``name`` or ``email`` must be present."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = {column.strip().lower() for column in reader.fieldnames or []}
        if not columns & {"name", "email"}:
            raise ValueError(f"{path} needs a 'name' or 'email' column")
        rows = []
        for raw in reader:
            row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
            if row.get("name") or row.get("email"):
                rows.append({
                    "name": row.get("name", ""),
                    "email": row.get("email", ""),
                    "contribution": row.get("contribution", ""),
                })
    return tuple(rows)


def build_rule(rule: str, org: str, *, members: set[str] | None = None,
               path: Path | None = None, owner_type: str = "Organization") -> HighlightRule:
    user = owner_type == "User"
    if rule == "none":
        return HighlightRule("none", None)
    if rule == "bots":
        return HighlightRule("bots", "automation accounts: names or emails ending in [bot], "
                                     "GitHub Actions and commits authored by GitHub itself")
    if rule == "outside":
        who = f"accounts other than {org}" if user else f"accounts that are not members of {org}"
        return HighlightRule("outside", f"{who}, including bots and emails that are not linked to a "
                                        "GitHub account",
                             frozenset(login.lower() for login in members or ()))
    if rule == "members":
        return HighlightRule("members", f"the account {org} itself" if user else f"members of {org}",
                             frozenset(login.lower() for login in members or ()))
    if rule == "file":
        if path is None:
            raise ValueError("a CSV path is required for the file rule")
        return HighlightRule("file", f"contributors listed in {path.name}", entries=read_entries(path))
    raise ValueError(f"unknown highlight rule {rule!r}")


def matches(rule: HighlightRule, commit: Commit) -> bool:
    """Whether the visual should draw this commit as a hexagon."""
    if rule.rule == "none":
        return False
    if rule.rule == "bots":
        return commit.is_bot
    login = (commit.author_login or "").lower()
    if rule.rule == "outside":
        return not login or login not in rule.members
    if rule.rule == "members":
        return bool(login) and login in rule.members
    name = commit.author_name.strip().lower()
    email = commit.author_email.strip().lower()
    return any(
        (entry["email"] and entry["email"].lower() == email)
        or (entry["name"] and entry["name"].lower() == name)
        for entry in rule.entries
    )


def entries_for(rule: HighlightRule, commits: list[Commit],
                redact_emails: bool = False) -> list[dict[str, str]] | None:
    """Rows for ``highlights.csv``: one per distinct highlighted author identity.

    The visual matches on exact email or case-insensitive name, so every
    (name, email) pair seen on a highlighted commit is listed. With
    ``redact_emails`` the email column holds a placeholder and matching works by
    name alone.
    """
    if rule.rule == "none":
        return None
    if rule.rule == "file":
        entries = list(rule.entries)
    else:
        seen: dict[tuple[str, str], dict[str, str]] = {}
        for commit in commits:
            if not matches(rule, commit):
                continue
            key = (commit.author_name.strip().lower(), commit.author_email.strip().lower())
            if key in seen:
                continue
            account = commit.author_login or "no linked GitHub account"
            seen[key] = {
                "name": commit.author_name.strip(),
                "email": commit.author_email.strip(),
                "contribution": f"{rule.rule}: {account}",
            }
        entries = list(seen.values())
    if redact_emails:
        entries = [{**entry, "email": REDACTED_EMAIL} for entry in entries]
    return entries
