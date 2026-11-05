"""Collect repositories, commit history, tags and members through GraphQL."""

from __future__ import annotations

from collections.abc import Iterator

from . import queries
from .github import GitHubError, GraphQL, error_messages
from .model import Commit, Repository, decorations_for, git_timestamp, subject_of


def _dig(payload: dict, *path: str) -> dict | None:
    node: object = payload.get("data") or {}
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, dict) else None


def _connection(client: GraphQL, query: str, variables: dict, path: tuple[str, ...],
                what: str) -> Iterator[dict]:
    """Yield every page of a GraphQL connection found at ``path`` under ``data``."""
    after: str | None = None
    while True:
        payload = client.execute(query, {**variables, "after": after})
        connection = _dig(payload, *path)
        if connection is None:
            messages = error_messages(payload)
            if messages:
                raise GitHubError(f"{what}: {'; '.join(messages)}")
            yield {}
            return
        yield connection
        page = connection.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return
        after = page.get("endCursor")


def fetch_owner(client: GraphQL, login: str) -> tuple[str, str]:
    """``(type, login)`` of an organisation or user account, with GitHub's spelling of the login."""
    payload = client.execute(queries.OWNER, {"login": login})
    owner = _dig(payload, "repositoryOwner")
    if owner is None:
        messages = error_messages(payload)
        detail = "; ".join(messages) if messages else "no organisation or user account with this login"
        raise GitHubError(f"{login}: {detail}")
    return owner.get("__typename") or "Organization", owner.get("login") or login


def list_repositories(client: GraphQL, org: str) -> list[Repository]:
    """Every repository the token can see that ``org`` (an organisation or a user) owns, by name."""
    repositories: list[Repository] = []
    path = ("repositoryOwner", "repositories")
    for page in _connection(client, queries.REPOSITORIES, {"org": org}, path, f"repositories of {org}"):
        for node in page.get("nodes") or []:
            if not node:
                continue
            branch = node.get("defaultBranchRef") or {}
            repositories.append(Repository(
                name=node["name"],
                full_name=node["nameWithOwner"],
                default_branch=branch.get("name"),
                private=bool(node.get("isPrivate")),
                archived=bool(node.get("isArchived")),
                fork=bool(node.get("isFork")),
                empty=bool(node.get("isEmpty")),
                pushed_at=node.get("pushedAt"),
            ))
    return repositories


def select_repositories(repositories: list[Repository], wanted: list[str] | None,
                        include_archived: bool, include_forks: bool) -> tuple[list[Repository], list[str]]:
    """Apply the name, archive and fork filters; return the selection and unknown names."""
    by_name = {repo.name.lower(): repo for repo in repositories}
    missing: list[str] = []
    if wanted:
        chosen = []
        for name in wanted:
            key = name.split("/", 1)[-1].lower()
            if key in by_name:
                chosen.append(by_name[key])
            else:
                missing.append(name)
        return chosen, missing
    chosen = [
        repo for repo in repositories
        if (include_archived or not repo.archived) and (include_forks or not repo.fork)
    ]
    return chosen, missing


def fetch_members(client: GraphQL, org: str, owner_type: str = "Organization") -> set[str]:
    """Logins of the organisation's members (needs a token that can read membership).

    A user account has no members: the account itself is the only "member".
    """
    if owner_type == "User":
        return {org.lower()}
    logins: set[str] = set()
    path = ("organization", "membersWithRole")
    for page in _connection(client, queries.MEMBERS, {"org": org}, path, f"members of {org}"):
        for node in page.get("nodes") or []:
            if node and node.get("login"):
                logins.add(node["login"].lower())
    return logins


def fetch_tags(client: GraphQL, owner: str, name: str) -> dict[str, list[str]]:
    """Map commit SHA to the tag names that point at it, resolving annotated tags."""
    tags: dict[str, list[str]] = {}
    path = ("repository", "refs")
    variables = {"owner": owner, "name": name}
    for page in _connection(client, queries.TAGS, variables, path, f"tags of {owner}/{name}"):
        for node in page.get("nodes") or []:
            target = (node or {}).get("target") or {}
            inner = target.get("target") or {}
            sha = inner.get("oid") or target.get("oid")
            if sha and node.get("name"):
                tags.setdefault(sha, []).append(node["name"])
    return tags


def _identity(block: dict | None) -> tuple[str, str, str | None]:
    block = block or {}
    user = block.get("user") or {}
    return (block.get("name") or "", block.get("email") or "", user.get("login"))


def commit_from_node(node: dict, tags: dict[str, list[str]], repository: str) -> Commit:
    """Translate one ``history`` node into a CSV-ready commit.

    Merge commits keep zero line and file counts, which is what
    ``git log --shortstat`` reports for them and what the visual expects.
    """
    author_name, author_email, author_login = _identity(node.get("author"))
    committer_name, committer_email, _ = _identity(node.get("committer"))
    parents = int(((node.get("parents") or {}).get("totalCount")) or 0)
    merge = parents > 1
    files = node.get("changedFilesIfAvailable")
    return Commit(
        commit_hash=node["oid"],
        decorations=decorations_for(tags.get(node["oid"], [])),
        committer_email=committer_email,
        committer_name=committer_name,
        commit_time=git_timestamp(node["committedDate"]),
        author_email=author_email,
        author_name=author_name,
        author_time=git_timestamp(node.get("authoredDate") or node["committedDate"]),
        commit_title=subject_of(node.get("message"), node.get("messageHeadline")),
        files_changed=0 if merge else (int(files) if files is not None else None),
        line_insertions=0 if merge else int(node.get("additions") or 0),
        line_deletions=0 if merge else int(node.get("deletions") or 0),
        repository=repository,
        author_login=author_login,
        parents=parents,
    )


def fetch_history(client: GraphQL, repository: Repository, *, since: str | None = None,
                  page_size: int = 100, tags: dict[str, list[str]] | None = None) -> list[Commit]:
    """All commits reachable from the default branch, newest first."""
    tags = tags if tags is not None else {}
    variables = {
        "owner": repository.owner,
        "name": repository.name,
        "since": f"{since}T00:00:00Z" if since else None,
        "pageSize": page_size,
    }
    commits: list[Commit] = []
    path = ("repository", "defaultBranchRef", "target", "history")
    for page in _connection(client, queries.HISTORY, variables, path, repository.full_name):
        for node in page.get("nodes") or []:
            if node:
                commits.append(commit_from_node(node, tags, repository.full_name))
    return commits
