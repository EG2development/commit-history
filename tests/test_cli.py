import json
import os
import subprocess

import pytest

from commit_history import cli
from fakes import FakeClient, node, repository_node


@pytest.fixture
def fake_github(monkeypatch):
    """Replace token resolution and the transport with an in-memory GraphQL double."""
    client = FakeClient(
        repositories=[repository_node("alpha"), repository_node("broken"),
                      repository_node("empty", isEmpty=True), repository_node("old", isArchived=True)],
        histories={
            "alpha": [node("a2", "2026-02-01T00:00:00Z"),
                      node("a1", "2026-01-01T00:00:00Z", name="dependabot[bot]", login=None)],
            "old": [node("o1", "2025-01-01T00:00:00Z")],
        },
        tags={"alpha": [{"name": "v1.0.0", "target": {"oid": "a2"}}]},
        members=["ada"],
        failures={"broken": "Could not resolve to a Repository"},
    )
    monkeypatch.setattr(cli, "resolve_token", lambda host: ("tok", "GITHUB_TOKEN"))
    monkeypatch.setattr(cli, "GraphQL", lambda url, token, log=None: client)
    return client


def test_collect_writes_every_repository_and_reports_partial_failure(fake_github, tmp_path, capsys):
    status = cli.main(["collect", "--org", "acme", "--output", str(tmp_path), "--highlight", "outside",
                       "--repo", "alpha", "--repo", "broken", "--repo", "empty", "--repo", "missing"])
    assert status == cli.EXIT_PARTIAL
    index = json.loads((tmp_path / "index.json").read_text())
    by_name = {entry["name"]: entry for entry in index["repositories"]}
    assert by_name["alpha"]["status"] == "ok" and by_name["alpha"]["commits"] == 2
    assert by_name["alpha"]["releases"] == 1 and by_name["alpha"]["highlighted_commits"] == 1
    assert by_name["broken"]["status"] == "error" and "Could not resolve" in by_name["broken"]["error"]
    assert by_name["empty"]["status"] == "empty"
    assert by_name["missing"]["status"] == "error"
    assert index["totals"]["repositories_failed"] == 2
    assert index["combined"]["commits"] == 2
    assert (tmp_path / "alpha" / "commits.csv").exists()
    assert (tmp_path / "_all" / "commits.csv").exists()
    assert "broken: FAILED" in capsys.readouterr().err


def test_collect_skips_archived_by_default_and_exits_zero(fake_github, tmp_path):
    status = cli.main(["collect", "--org", "acme", "--output", str(tmp_path), "--repo", "alpha",
                       "--combined-max", "0"])
    assert status == cli.EXIT_OK
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["combined"] is None and index["highlight"]["rule"] == "bots"

    status = cli.main(["collect", "--org", "acme", "--output", str(tmp_path), "--clean"])
    assert status == cli.EXIT_PARTIAL  # "broken" still fails
    names = {entry["name"] for entry in json.loads((tmp_path / "index.json").read_text())["repositories"]}
    assert names == {"alpha", "broken", "empty"}
    status = cli.main(["collect", "--org", "acme", "--output", str(tmp_path), "--include-archived",
                       "--repo", "old"])
    assert status == cli.EXIT_OK


def test_collect_reads_a_user_account_without_a_members_query(monkeypatch, tmp_path):
    client = FakeClient(
        owner_type="User", login="ada",
        repositories=[repository_node("blog", owner="ada")],
        histories={"blog": [node("b2", "2026-02-01T00:00:00Z"),
                            node("b1", "2026-01-01T00:00:00Z", name="Guest", email="g@example.org",
                                 login="guest")]},
    )
    monkeypatch.setattr(cli, "resolve_token", lambda host: ("tok", "GITHUB_TOKEN"))
    monkeypatch.setattr(cli, "GraphQL", lambda url, token, log=None: client)
    status = cli.main(["collect", "--org", "ADA", "--highlight", "outside", "--output", str(tmp_path)])
    assert status == cli.EXIT_OK
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["organisation"] == "ada"
    assert index["highlight"]["label"].startswith("accounts other than ada")
    assert index["repositories"][0]["highlighted_commits"] == 1
    assert not any(op == "Members" for op, _ in client.calls)


def test_unknown_login_exits_with_two(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "resolve_token", lambda host: ("tok", "GITHUB_TOKEN"))
    monkeypatch.setattr(cli, "GraphQL", lambda url, token, log=None: FakeClient(login=None))
    assert cli.main(["collect", "--org", "nobody", "--output", str(tmp_path)]) == cli.EXIT_USAGE


def test_redact_emails_flag(fake_github, tmp_path):
    status = cli.main(["collect", "--org", "acme", "--output", str(tmp_path), "--repo", "alpha",
                       "--redact-emails"])
    assert status == cli.EXIT_OK
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["emails"] == "redacted"
    assert "@" not in (tmp_path / "alpha" / "commits.csv").read_text()
    assert "@" not in (tmp_path / "_all" / "commits.csv").read_text()
    assert "redacted" in (tmp_path / "alpha" / "highlights.csv").read_text()


def test_usage_errors_exit_with_two(fake_github, tmp_path):
    assert cli.main(["collect", "--org", "acme", "--since", "yesterday"]) == cli.EXIT_USAGE
    status = cli.main(["collect", "--org", "acme", "--highlight", "everyone", "--output", str(tmp_path)])
    assert status == cli.EXIT_USAGE
    with pytest.raises(SystemExit):
        cli.main(["collect", "--org", "acme", "--page-size", "500"])


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.org",
           "GIT_COMMITTER_NAME": "Ada", "GIT_COMMITTER_EMAIL": "ada@example.org"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


@pytest.mark.skipif(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                    reason="git is not installed")
def test_from_git_merges_into_an_existing_index(tmp_path):
    repo = tmp_path / "clone"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "f").write_text("x\n")
    git(repo, "add", "f")
    git(repo, "commit", "-q", "-m", "first")
    out = tmp_path / "data"

    assert cli.main(["from-git", "--repo-dir", str(repo), "--name", "acme/clone", "--output", str(out)]) == 0
    index = json.loads((out / "index.json").read_text())
    assert index["source"] == "git log" and index["organisation"] == "acme"
    assert index["repositories"][0]["commits"] == 1 and index["repositories"][0]["private"] is None

    assert cli.main(["from-git", "--repo-dir", str(repo), "--name", "acme/clone", "--output", str(out),
                     "--title", "ACME"]) == 0
    index = json.loads((out / "index.json").read_text())
    assert len(index["repositories"]) == 1 and index["title"] == "ACME"

    assert cli.main(["from-git", "--repo-dir", str(tmp_path), "--name", "acme/x", "--output", str(out)]) == 2
    assert cli.main(["from-git", "--repo-dir", str(repo), "--name", "nope", "--output", str(out)]) == 2
    assert cli.main(["from-git", "--repo-dir", str(repo), "--name", "acme/clone", "--highlight", "outside",
                     "--output", str(out)]) == 2
