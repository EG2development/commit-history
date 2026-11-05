import csv
import json

from commit_history.highlights import build_rule
from commit_history.model import Commit, Repository
from commit_history.output import (
    COLUMNS,
    build_index,
    read_index,
    repository_entry,
    summarise,
    write_combined,
    write_commits,
    write_highlights,
    write_index,
    write_repository,
)

ORCA_COLUMNS = ("commit_hash", "decorations", "committer_email", "committer_name", "commit_time",
                "author_email", "author_name", "author_time", "commit_title", "files_changed",
                "line_insertions", "line_deletions")

REPO = Repository(name="engine", full_name="acme/engine", default_branch="main", private=True, archived=False,
                  fork=False, empty=False, pushed_at="2026-11-01T00:00:00Z")


def commit(sha, time, *, name="Ada Lovelace", login="ada", ins=5, dele=1, files=1, parents=1, tags="",
           title="Change") -> Commit:
    return Commit(commit_hash=sha, decorations=tags, committer_email="c@example.org", committer_name="C",
                  commit_time=time, author_email=f"{login or name}@example.org", author_name=name,
                  author_time=time, commit_title=title, files_changed=files, line_insertions=ins,
                  line_deletions=dele, repository="acme/engine", author_login=login, parents=parents)


COMMITS = [
    commit("c3", "2026-03-01 00:00:00 +0000", tags="tag: v2.0.0"),
    commit("c2", "2026-02-01 00:00:00 +0000", name="dependabot[bot]", login=None, files=None),
    commit("c1", "2026-01-01 00:00:00 +0000", parents=2, ins=0, dele=0, files=0, title="Merge"),
]


def test_commits_csv_starts_with_the_orca_schema(tmp_path):
    target = write_commits(tmp_path, COMMITS)
    with target.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0][:12]) == ORCA_COLUMNS
    assert tuple(rows[0]) == COLUMNS
    assert rows[1][0] == "c3" and rows[1][1] == "tag: v2.0.0"
    assert rows[2][9] == ""  # unavailable file count stays blank
    assert rows[3][-1] == "2"  # parents


def test_highlights_csv_is_written_or_removed(tmp_path):
    assert write_highlights(tmp_path, [{"name": "A", "email": "a@x", "contribution": "why", "extra": 1}])
    assert (tmp_path / "highlights.csv").read_text() == "name,email,contribution\nA,a@x,why\n"
    assert write_highlights(tmp_path, None) is None
    assert not (tmp_path / "highlights.csv").exists()


def test_summarise_counts():
    summary = summarise(COMMITS, build_rule("bots", "acme"))
    assert summary == {
        "commits": 3, "contributors": 2, "first_commit": "2026-01-01T00:00:00Z",
        "last_commit": "2026-03-01T00:00:00Z", "insertions": 10, "deletions": 2, "releases": 1,
        "merge_commits": 1, "highlighted_commits": 1, "files_unavailable": 1,
    }
    assert summarise([], build_rule("none", "acme"))["first_commit"] is None


def test_repository_entry_and_write_repository(tmp_path):
    rule = build_rule("bots", "acme")
    write_repository(tmp_path, REPO, COMMITS, rule)
    assert (tmp_path / "engine" / "commits.csv").exists()
    assert "dependabot[bot]" in (tmp_path / "engine" / "highlights.csv").read_text()
    entry = repository_entry(REPO, "https://github.com", "ok", commits=COMMITS, rule=rule)
    assert entry["url"] == "https://github.com/acme/engine"
    assert entry["slug"] == "engine" and entry["status"] == "ok" and entry["commits"] == 3
    failed = repository_entry(REPO, "https://github.com", "error", error="boom")
    assert failed["commits"] == 0 and failed["error"] == "boom"


def test_write_combined_prefixes_titles_and_respects_the_cap(tmp_path):
    rule = build_rule("bots", "acme")
    other = [commit("o1", "2026-02-15 00:00:00 +0000", title="Other change")]
    per_repository = {"acme/engine": COMMITS, "acme/other": other}

    summary = write_combined(tmp_path, per_repository, rule, limit=10)
    assert summary["slug"] == "_all" and summary["commits"] == 4 and not summary["skipped"]
    with (tmp_path / "_all" / "commits.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["commit_hash"] for row in rows] == ["c3", "o1", "c2", "c1"]
    assert rows[0]["commit_title"] == "engine: Change" and rows[1]["commit_title"] == "other: Other change"
    assert (tmp_path / "_all" / "highlights.csv").exists()

    skipped = write_combined(tmp_path, per_repository, rule, limit=3)
    assert skipped == {"slug": None, "skipped": True, "commits": 4, "limit": 3}
    assert not (tmp_path / "_all").exists()
    assert write_combined(tmp_path, per_repository, rule, limit=0) is None
    assert write_combined(tmp_path, {}, rule, limit=10) is None


def test_redacting_emails_blanks_them_and_keeps_name_matching_possible(tmp_path):
    rule = build_rule("bots", "acme")
    write_repository(tmp_path, REPO, COMMITS, rule, redact_emails=True)
    with (tmp_path / "engine" / "commits.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["author_email"] for row in rows} == {""}
    assert {row["committer_email"] for row in rows} == {""}
    assert {row["author_name"] for row in rows} == {"Ada Lovelace", "dependabot[bot]"}
    highlights = (tmp_path / "engine" / "highlights.csv").read_text()
    assert "dependabot[bot],redacted," in highlights and "@" not in highlights
    summary = write_combined(tmp_path, {"acme/engine": COMMITS}, rule, limit=10, redact_emails=True)
    assert summary["commits"] == 3
    assert "@" not in (tmp_path / "_all" / "commits.csv").read_text()
    index = build_index(organisation="acme", title="ACME", host="github.com", source="graphql", since=None,
                        rule=rule, repositories=[], combined=None, token_source=None, requests=0, points=0,
                        redact_emails=True)
    assert index["emails"] == "redacted"


def test_build_index_and_round_trip(tmp_path):
    rule = build_rule("outside", "acme", members={"ada"})
    entries = [
        repository_entry(REPO, "https://github.com", "ok", commits=COMMITS, rule=rule),
        repository_entry(REPO, "https://github.com", "error", error="nope"),
    ]
    index = build_index(organisation="acme", title="ACME", host="github.com", source="graphql", since=None,
                        rule=rule, repositories=entries, combined=None, token_source="GITHUB_TOKEN",
                        requests=7, points=7)
    assert index["totals"] == {"repositories": 2, "repositories_ok": 1, "repositories_failed": 1,
                               "commits": 3, "highlighted_commits": 1, "insertions": 10, "deletions": 2}
    assert index["highlight"]["rule"] == "outside"
    write_index(tmp_path, index)
    assert read_index(tmp_path) == json.loads(json.dumps(index))
    assert read_index(tmp_path / "missing") is None
