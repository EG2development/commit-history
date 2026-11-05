import pytest

from commit_history.collect import (
    commit_from_node,
    fetch_history,
    fetch_members,
    fetch_owner,
    fetch_tags,
    list_repositories,
    select_repositories,
)
from commit_history.github import GitHubError
from commit_history.model import Repository
from fakes import FakeClient, node, repository_node

ENGINE = Repository(name="engine", full_name="acme/engine", default_branch="main", private=True,
                    archived=False, fork=False, empty=False, pushed_at=None)


def test_commit_from_node_maps_every_field():
    commit = commit_from_node(node("abc", "2026-03-04T05:06:07Z", title=" Fix: bug "), {"abc": ["v1.0.0"]},
                              "acme/engine")
    assert commit.commit_hash == "abc"
    assert commit.decorations == "tag: v1.0.0"
    assert commit.commit_time == "2026-03-04 05:06:07 +0000"
    assert commit.author_time == "2026-03-04 05:06:07 +0000"
    assert commit.author_name == "Ada Lovelace"
    assert commit.author_login == "ada"
    assert commit.commit_title == "Fix: bug"
    assert (commit.files_changed, commit.line_insertions, commit.line_deletions) == (1, 10, 2)
    assert commit.repository == "acme/engine"
    assert commit.parents == 1


def test_title_is_gits_subject_from_the_full_message():
    headline = "Activate the selector check for the `autoprint` integration test as s…"
    raw = node("t", "2026-01-01T00:00:00Z", title=headline)
    raw["message"] = ("Activate the selector check for the `autoprint` integration test as soon as possible\n"
                      "\nBody text\n")
    assert commit_from_node(raw, {}, "acme/engine").commit_title == (
        "Activate the selector check for the `autoprint` integration test as soon as possible")
    raw["message"] = "\n\nAcroForm: Add support for ResetForm action\n  - it aims to fix #12721.\n\nMore\n"
    assert commit_from_node(raw, {}, "acme/engine").commit_title == (
        "AcroForm: Add support for ResetForm action   - it aims to fix #12721.")
    raw["message"] = ""
    assert commit_from_node(raw, {}, "acme/engine").commit_title.endswith("as s…")


def test_merge_commits_keep_zero_counts_like_git_log():
    merge = node("m", "2026-01-01T00:00:00Z", additions=500, deletions=20, files=9, parents=2)
    commit = commit_from_node(merge, {}, "acme/engine")
    assert (commit.files_changed, commit.line_insertions, commit.line_deletions) == (0, 0, 0)
    assert commit.is_merge


def test_unavailable_file_count_and_unlinked_author():
    raw = node("x", "2026-01-01T00:00:00Z", files=None, login=None)
    raw["author"]["user"] = None
    commit = commit_from_node(raw, {}, "acme/engine")
    assert commit.files_changed is None
    assert commit.author_login is None
    assert commit.line_insertions == 10


def test_fetch_history_walks_every_page_in_order():
    nodes = [node(f"c{i}", f"2026-01-0{9 - i}T00:00:00Z") for i in range(5)]
    client = FakeClient(histories={"engine": nodes})
    commits = fetch_history(client, ENGINE, page_size=2, tags={"c3": ["v2"]})
    assert [c.commit_hash for c in commits] == ["c0", "c1", "c2", "c3", "c4"]
    assert commits[3].decorations == "tag: v2"
    history_calls = [v for op, v in client.calls if op == "History"]
    assert [v["after"] for v in history_calls] == [None, "2", "4"]
    assert history_calls[0]["since"] is None


def test_fetch_history_passes_since_as_a_git_timestamp():
    client = FakeClient(histories={"engine": []})
    fetch_history(client, ENGINE, since="2026-01-01")
    assert client.calls[0][1]["since"] == "2026-01-01T00:00:00Z"


def test_fetch_history_raises_on_graphql_errors():
    client = FakeClient(failures={"engine": "Could not resolve to a Repository"})
    with pytest.raises(GitHubError, match="acme/engine: NOT_FOUND: Could not resolve"):
        fetch_history(client, ENGINE)


def test_fetch_tags_resolves_annotated_and_lightweight_tags():
    client = FakeClient(tags={"engine": [
        {"name": "v1.0.0", "target": {"oid": "tagobj", "target": {"oid": "c1"}}},
        {"name": "latest", "target": {"oid": "c1"}},
        {"name": "v0.9.0", "target": {"oid": "c0"}},
    ]})
    assert fetch_tags(client, "acme", "engine") == {"c1": ["v1.0.0", "latest"], "c0": ["v0.9.0"]}


def test_list_and_select_repositories():
    client = FakeClient(repositories=[
        repository_node("alpha"),
        repository_node("beta", isArchived=True),
        repository_node("gamma", isFork=True),
        repository_node("delta", isEmpty=True, defaultBranchRef=None),
    ])
    repositories = list_repositories(client, "acme")
    assert [r.name for r in repositories] == ["alpha", "beta", "gamma", "delta"]
    assert repositories[3].empty and repositories[3].default_branch is None
    assert repositories[0].owner == "acme"

    chosen, missing = select_repositories(repositories, None, False, False)
    assert [r.name for r in chosen] == ["alpha", "delta"] and missing == []
    chosen, _ = select_repositories(repositories, None, True, True)
    assert len(chosen) == 4
    chosen, missing = select_repositories(repositories, ["acme/Beta", "nope"], False, False)
    assert [r.name for r in chosen] == ["beta"] and missing == ["nope"]


def test_fetch_members_lowercases_logins():
    client = FakeClient(members=["Ada", "grace", "linus"])
    assert fetch_members(client, "acme") == {"ada", "grace", "linus"}
    assert len([op for op, _ in client.calls if op == "Members"]) == 2


def test_fetch_owner_for_organisations_users_and_unknown_logins():
    assert fetch_owner(FakeClient(), "ACME") == ("Organization", "acme")
    user = FakeClient(owner_type="User", login="ada", members=["ignored"])
    assert fetch_owner(user, "ada") == ("User", "ada")
    assert fetch_members(user, "Ada", "User") == {"ada"}
    assert not any(op == "Members" for op, _ in user.calls)
    with pytest.raises(GitHubError, match="nobody: NOT_FOUND"):
        fetch_owner(FakeClient(login=None), "nobody")
