"""Command line entry point: ``commit-history collect`` and ``commit-history from-git``.

Exit status: 0 when every selected repository was written, 1 when at least one
repository failed (the rest are written and listed in ``index.json``), 2 for a
usage, authentication or configuration problem.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from . import __version__
from .collect import (
    fetch_history,
    fetch_members,
    fetch_owner,
    fetch_tags,
    list_repositories,
    select_repositories,
)
from .github import GitHubError, GraphQL, graphql_url, resolve_token, web_url
from .gitlog import GitLogError, parse_log, read_log
from .highlights import HighlightRule, build_rule, parse_rule
from .model import Repository
from .output import (
    build_index,
    read_index,
    repository_entry,
    write_combined,
    write_index,
    write_repository,
)

EXIT_OK, EXIT_PARTIAL, EXIT_USAGE = 0, 1, 2


class UsageError(Exception):
    """A problem the operator has to fix before the run can succeed."""


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _page_size(value: str) -> int:
    size = int(value)
    if not 1 <= size <= 100:
        raise argparse.ArgumentTypeError("page size must be between 1 and 100")
    return size


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-history",
        description="Collect the commit history of GitHub repositories for the commit-history site.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    collect = commands.add_parser(
        "collect", help="read every repository of an organisation through the GitHub GraphQL API")
    collect.add_argument("--org", required=True, metavar="LOGIN",
                         help="organisation to read, for example my-org; a user account works too")
    collect.add_argument("--repo", action="append", dest="repos", metavar="NAME",
                         help="collect only this repository; repeat for several")
    collect.add_argument("--since", metavar="YYYY-MM-DD", help="ignore commits made before this date")
    collect.add_argument("--include-archived", action="store_true", help="also read archived repositories")
    collect.add_argument("--include-forks", action="store_true", help="also read forks")
    collect.add_argument("--highlight", default="bots", metavar="RULE",
                         help="which authors become hexagons: none, bots, outside, members or a .csv path "
                              "(default: bots)")
    collect.add_argument("--combined-max", type=int, default=50_000, metavar="N",
                         help="write an all-repositories dataset when the organisation has at most N "
                              "commits; 0 disables it (default: 50000)")
    collect.add_argument("--page-size", type=_page_size, default=100, metavar="N",
                         help="commits per GraphQL page, 1 to 100; lower it if large repositories time out")
    collect.add_argument("--host", default="github.com",
                         help="github.com, your-subdomain.ghe.com or a GitHub Enterprise Server host")
    collect.add_argument("--title", help="display name for the organisation (default: its login)")
    collect.add_argument("--output", type=Path, default=Path("site/data"),
                         help="data directory the site reads (default: site/data)")
    collect.add_argument("--clean", action="store_true", help="delete the output directory first")
    collect.add_argument("--redact-emails", action="store_true",
                         help="leave author and committer emails out of the written files; highlighted "
                              "contributors are then matched by name only")
    collect.set_defaults(func=run_collect)

    from_git = commands.add_parser(
        "from-git", help="read one local clone with git log, the way the original ORCA visual did")
    from_git.add_argument("--repo-dir", type=Path, required=True, help="path to the clone")
    from_git.add_argument("--name", required=True, metavar="OWNER/NAME", help="repository name to display")
    from_git.add_argument("--ref", default="HEAD", help="branch or ref to walk (default: HEAD)")
    from_git.add_argument("--highlight", default="bots", metavar="RULE",
                          help="none, bots or a .csv path (default: bots)")
    from_git.add_argument("--host", default="github.com", help="host used to build the repository link")
    from_git.add_argument("--title", help="display name for the organisation")
    from_git.add_argument("--output", type=Path, default=Path("site/data"))
    from_git.add_argument("--redact-emails", action="store_true",
                          help="leave author and committer emails out of the written files")
    from_git.set_defaults(func=run_from_git)
    return parser


def _validate_since(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise UsageError(f"--since must be YYYY-MM-DD, not {value!r}") from exc


def _highlight_rule(value: str, org: str, client: GraphQL | None,
                    owner_type: str = "Organization") -> HighlightRule:
    try:
        rule_name, path = parse_rule(value)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    members: set[str] | None = None
    if rule_name in ("outside", "members"):
        if client is None:
            raise UsageError("from-git cannot resolve organisation membership; use none, bots or a .csv list")
        try:
            members = fetch_members(client, org, owner_type)
        except GitHubError as exc:
            raise UsageError(f"--highlight {rule_name} needs a token that can read the members of {org} "
                             f"({exc}); use --highlight bots or --highlight none") from exc
        log(f"{org}: {len(members)} members")
    try:
        return build_rule(rule_name, org, members=members, path=path, owner_type=owner_type)
    except (OSError, ValueError) as exc:
        raise UsageError(f"could not read the highlight list: {exc}") from exc


def _missing_entry(name: str, org: str, web: str) -> dict:
    short = name.split("/", 1)[-1]
    repository = Repository(name=short, full_name=f"{org}/{short}", default_branch=None, private=None,
                            archived=False, fork=False, empty=False, pushed_at=None)
    return repository_entry(repository, web, "error",
                            error="not found in the organisation, or not visible to this token")


def collect_repository(client: GraphQL, repository: Repository, rule: HighlightRule, *, since: str | None,
                       page_size: int, web: str, output: Path,
                       redact_emails: bool = False) -> tuple[dict, list | None]:
    """Fetch, write and summarise one repository; never raises for a per-repository failure."""
    if repository.empty or not repository.default_branch:
        log(f"{repository.full_name}: empty, skipped")
        return repository_entry(repository, web, "empty"), None
    started = time.monotonic()
    try:
        tags = fetch_tags(client, repository.owner, repository.name)
        commits = fetch_history(client, repository, since=since, page_size=page_size, tags=tags)
    except GitHubError as exc:
        log(f"{repository.full_name}: FAILED {exc}")
        return repository_entry(repository, web, "error", error=str(exc)), None
    write_repository(output, repository, commits, rule, redact_emails)
    entry = repository_entry(repository, web, "ok", commits=commits, rule=rule)
    log(f"{repository.full_name}: {entry['commits']} commits, {entry['releases']} releases, "
        f"{entry['highlighted_commits']} highlighted ({time.monotonic() - started:.1f}s)")
    return entry, commits


def run_collect(args: argparse.Namespace) -> int:
    since = _validate_since(args.since)
    token, token_source = resolve_token(args.host)
    client = GraphQL(graphql_url(args.host), token, log=log)
    owner_type, owner = fetch_owner(client, args.org)
    log(f"{owner}: listing the repositories of this {owner_type.lower()} via {client.url} "
        f"(token from {token_source})")
    repositories = list_repositories(client, owner)
    chosen, missing = select_repositories(repositories, args.repos, args.include_archived, args.include_forks)
    log(f"{owner}: {len(repositories)} repositories visible, {len(chosen)} selected")
    rule = _highlight_rule(args.highlight, owner, client, owner_type)

    if args.clean and args.output.exists():
        shutil.rmtree(args.output)
    web = web_url(args.host)
    entries: list[dict] = []
    per_repository: dict[str, list] = {}
    for repository in chosen:
        entry, commits = collect_repository(client, repository, rule, since=since, page_size=args.page_size,
                                            web=web, output=args.output, redact_emails=args.redact_emails)
        entries.append(entry)
        if commits is not None:
            per_repository[repository.full_name] = commits
    entries.extend(_missing_entry(name, owner, web) for name in missing)

    combined = write_combined(args.output, per_repository, rule, args.combined_max, args.redact_emails)
    index = build_index(organisation=owner, title=args.title or owner, host=args.host, source="graphql",
                        since=since, rule=rule, repositories=entries, combined=combined,
                        token_source=token_source, requests=client.requests, points=client.points_used,
                        redact_emails=args.redact_emails)
    write_index(args.output, index)
    totals = index["totals"]
    log(f"{owner}: wrote {totals['repositories_ok']} repositories, {totals['commits']} commits to "
        f"{args.output} ({client.requests} requests, {client.points_used} points)")
    if combined and combined.get("skipped"):
        log(f"{owner}: combined dataset skipped, {combined['commits']} commits exceed --combined-max "
            f"{combined['limit']}")
    if totals["repositories_failed"]:
        log(f"{owner}: {totals['repositories_failed']} repositories FAILED; see index.json")
        return EXIT_PARTIAL
    return EXIT_OK


def run_from_git(args: argparse.Namespace) -> int:
    owner, _, name = args.name.partition("/")
    if not owner or not name:
        raise UsageError("--name must be OWNER/NAME")
    rule = _highlight_rule(args.highlight, owner, None)
    try:
        commits = parse_log(read_log(args.repo_dir, args.ref), args.name)
    except GitLogError as exc:
        raise UsageError(str(exc)) from exc
    repository = Repository(name=name, full_name=args.name, default_branch=args.ref, private=None,
                            archived=False, fork=False, empty=not commits, pushed_at=None)
    web = web_url(args.host)
    write_repository(args.output, repository, commits, rule, args.redact_emails)
    entry = repository_entry(repository, web, "ok" if commits else "empty", commits=commits, rule=rule)

    existing = read_index(args.output) or {}
    others = [item for item in existing.get("repositories", []) if item.get("slug") != repository.slug]
    entries = sorted([*others, entry], key=lambda item: item["name"].lower())
    index = build_index(organisation=existing.get("organisation") or owner,
                        title=args.title or existing.get("title") or owner, host=args.host, source="git log",
                        since=None, rule=rule, repositories=entries, combined=existing.get("combined"),
                        token_source=None, requests=0, points=0, redact_emails=args.redact_emails)
    write_index(args.output, index)
    log(f"{args.name}: {entry['commits']} commits, {entry['releases']} releases, "
        f"{entry['highlighted_commits']} highlighted, written to {args.output / repository.slug}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (UsageError, GitHubError) as exc:
        log(f"error: {exc}")
        return EXIT_USAGE
    except KeyboardInterrupt:
        log("interrupted")
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
