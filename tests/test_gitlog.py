import os
import subprocess
from pathlib import Path

import pytest

from commit_history.gitlog import (
    FIELD,
    RECORD,
    GitLogError,
    log_command,
    parse_log,
    parse_shortstat,
    read_log,
    tag_decorations,
)


def record(*fields: str, stats: str = "") -> str:
    return RECORD + FIELD.join(fields) + ("\n\n" + stats + "\n" if stats else "\n")


SAMPLE = (
    record("a" * 40, "HEAD -> main, tag: v1.0.0, origin/main", "ada@example.org", "Ada",
           "2026-01-03 10:00:00 +0100", "ada@example.org", "Ada Lovelace", "2026-01-03 09:59:00 +0100",
           'Release "v1.0.0", finally', "b" * 40,
           stats=" 3 files changed, 10 insertions(+), 4 deletions(-)")
    + record("b" * 40, "", "noreply@github.com", "GitHub", "2026-01-02 10:00:00 +0000", "ada@example.org",
             "Ada Lovelace", "2026-01-02 10:00:00 +0000", "Merge pull request #1", "c" * 40 + " " + "d" * 40)
    + record("c" * 40, "tag: 1.1", "bob@example.org", "Bob", "2026-01-01 10:00:00 +0000", "bob@example.org",
             "Bob", "2026-01-01 10:00:00 +0000", "Remove, things", "d" * 40,
             stats=" 1 file changed, 7 deletions(-)")
)


def test_parse_log_reads_fields_stats_tags_and_parents():
    commits = parse_log(SAMPLE, "acme/engine")
    assert [c.commit_hash[0] for c in commits] == ["a", "b", "c"]
    first, merge, last = commits
    assert first.decorations == "tag: v1.0.0"
    assert first.commit_title == 'Release "v1.0.0", finally'
    assert (first.files_changed, first.line_insertions, first.line_deletions) == (3, 10, 4)
    assert first.commit_time == "2026-01-03 10:00:00 +0100"
    assert first.parents == 1 and first.author_login is None
    assert merge.parents == 2 and merge.is_merge
    assert (merge.files_changed, merge.line_insertions, merge.line_deletions) == (0, 0, 0)
    assert last.decorations == "tag: 1.1" and not last.is_release
    assert (last.files_changed, last.line_insertions, last.line_deletions) == (1, 0, 7)
    assert last.commit_title == "Remove, things"


def test_parse_log_rejects_malformed_records():
    with pytest.raises(GitLogError, match="unexpected git log record"):
        parse_log(RECORD + "only" + FIELD + "two\n", "acme/engine")


def test_parse_shortstat_variants():
    assert parse_shortstat(" 2 files changed, 13 insertions(+), 26 deletions(-)") == (2, 13, 26)
    assert parse_shortstat(" 1 file changed, 1 insertion(+)") == (1, 1, 0)
    assert parse_shortstat(" 1 file changed, 1 deletion(-)") == (1, 0, 1)
    assert parse_shortstat("") == (0, 0, 0)


def test_tag_decorations_keeps_only_tags():
    assert tag_decorations("HEAD -> main, tag: v2, origin/main, tag: latest") == "tag: v2, tag: latest"
    assert tag_decorations("") == ""


def test_log_command_shape():
    command = log_command(Path("/repo"), "origin/main")
    assert command[:5] == ["git", "-C", "/repo", "log", "origin/main"]
    assert "--shortstat" in command and "--no-color" in command


def test_read_log_requires_a_repository(tmp_path):
    with pytest.raises(GitLogError, match="not a git repository"):
        read_log(tmp_path)


def git(repo: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "Ada Lovelace", "GIT_AUTHOR_EMAIL": "ada@example.org",
           "GIT_COMMITTER_NAME": "Ada Lovelace", "GIT_COMMITTER_EMAIL": "ada@example.org",
           "GIT_AUTHOR_DATE": "2026-02-01T10:00:00+0000", "GIT_COMMITTER_DATE": "2026-02-01T10:00:00+0000"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


@pytest.mark.skipif(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                    reason="git is not installed")
def test_read_log_against_a_real_repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("one\ntwo\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "Initial import, with a comma")
    (repo / "a.txt").write_text("one\n")
    git(repo, "commit", "-q", "-am", "Trim a line")
    git(repo, "tag", "v0.1.0")

    commits = parse_log(read_log(repo), "acme/engine")
    assert [c.commit_title for c in commits] == ["Trim a line", "Initial import, with a comma"]
    assert commits[0].decorations == "tag: v0.1.0" and commits[0].is_release
    assert (commits[0].files_changed, commits[0].line_insertions, commits[0].line_deletions) == (1, 0, 1)
    assert (commits[1].files_changed, commits[1].line_insertions, commits[1].line_deletions) == (1, 2, 0)
    assert commits[1].parents == 0 and commits[0].parents == 1
    assert commits[0].commit_time == "2026-02-01 10:00:00 +0000"
