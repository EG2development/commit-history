"""Test doubles shared by the test modules."""

from __future__ import annotations

import io
import urllib.error


def node(oid: str, date: str, *, name: str = "Ada Lovelace", email: str = "ada@example.org",
         login: str | None = "ada", additions: int = 10, deletions: int = 2, files: int | None = 1,
         parents: int = 1, title: str = "Add a thing", committer: dict | None = None) -> dict:
    """One ``history`` node as the GraphQL API returns it."""
    return {
        "oid": oid,
        "committedDate": date,
        "authoredDate": date,
        "messageHeadline": title,
        "message": title,
        "additions": additions,
        "deletions": deletions,
        "changedFilesIfAvailable": files,
        "parents": {"totalCount": parents},
        "author": {"name": name, "email": email, "user": {"login": login} if login else None},
        "committer": committer or {"name": name, "email": email, "user": {"login": login} if login else None},
    }


def repository_node(name: str, owner: str = "acme", **overrides) -> dict:
    data = {
        "name": name,
        "nameWithOwner": f"{owner}/{name}",
        "isArchived": False,
        "isFork": False,
        "isPrivate": True,
        "isEmpty": False,
        "pushedAt": "2026-11-01T00:00:00Z",
        "defaultBranchRef": {"name": "main"},
    }
    data.update(overrides)
    return data


class FakeClient:
    """Answers the collector's four queries from in-memory data, paging two nodes at a time."""

    def __init__(self, repositories=(), histories=None, tags=None, members=(), failures=None,
                 page_size: int = 2, owner_type: str = "Organization", login: str | None = "acme"):
        self.url = "https://api.example.test/graphql"
        self.owner_type = owner_type
        self.login = login
        self.repositories = list(repositories)
        self.histories = histories or {}
        self.tags = tags or {}
        self.members = list(members)
        self.failures = failures or {}
        self.page_size = page_size
        self.requests = 0
        self.points_used = 0
        self.calls: list[tuple[str, dict]] = []

    @staticmethod
    def _operation(query: str) -> str:
        return query.strip().split("(")[0].split()[-1]

    def _page(self, items: list, after: str | None, size: int | None = None) -> dict:
        size = size or self.page_size
        start = int(after or 0)
        end = start + size
        return {
            "pageInfo": {"hasNextPage": end < len(items), "endCursor": str(end)},
            "nodes": items[start:end],
        }

    def execute(self, query: str, variables: dict) -> dict:
        self.requests += 1
        self.points_used += 1
        operation = self._operation(query)
        self.calls.append((operation, dict(variables)))
        after = variables.get("after")
        rate = {"rateLimit": {"cost": 1, "remaining": 4999, "resetAt": "2026-11-05T10:00:00Z"}}
        if operation == "Owner":
            if self.login is None:
                error = {"type": "NOT_FOUND", "message": "Could not resolve to a RepositoryOwner"}
                return {"data": {"repositoryOwner": None, **rate}, "errors": [error]}
            return {"data": {"repositoryOwner": {"__typename": self.owner_type, "login": self.login}, **rate}}
        if operation == "Repositories":
            owner = {"repositories": self._page(self.repositories, after)}
            return {"data": {"repositoryOwner": owner, **rate}}
        if operation == "Members":
            nodes = [{"login": login} for login in self.members]
            return {"data": {"organization": {"membersWithRole": self._page(nodes, after)}, **rate}}
        if operation == "Tags":
            nodes = self.tags.get(variables["name"], [])
            return {"data": {"repository": {"refs": self._page(nodes, after)}, **rate}}
        if operation == "History":
            name = variables["name"]
            if name in self.failures:
                return {"data": {"repository": None, **rate},
                        "errors": [{"type": "NOT_FOUND", "message": self.failures[name]}]}
            nodes = self.histories.get(name, [])
            page = self._page(nodes, after, variables["pageSize"])
            page["totalCount"] = len(nodes)
            branch = {"name": "main", "target": {"history": page}}
            return {"data": {"repository": {"defaultBranchRef": branch}, **rate}}
        raise AssertionError(f"unexpected operation {operation}")


class FakeResponse:
    """What ``urlopen`` yields for a 200 response."""

    def __init__(self, body: str, headers: dict | None = None, status: int = 200):
        self.status = status
        self.headers = headers or {}
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


def http_error(status: int, body: str = "", headers: dict | None = None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.example.test/graphql", status, "error", headers or {},
                                  io.BytesIO(body.encode("utf-8")))


class FakeUrlopen:
    """Returns the scripted responses in order; an exception instance is raised instead of returned."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("no more scripted responses")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response
