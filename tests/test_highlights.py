from pathlib import Path

import pytest

from commit_history.highlights import build_rule, entries_for, matches, parse_rule, read_entries
from commit_history.model import Commit


def commit(name="Ada Lovelace", email="ada@example.org", login="ada") -> Commit:
    return Commit(commit_hash="x" * 40, decorations="", committer_email=email, committer_name=name,
                  commit_time="2026-01-01 00:00:00 +0000", author_email=email, author_name=name,
                  author_time="2026-01-01 00:00:00 +0000", commit_title="t", files_changed=1,
                  line_insertions=1, line_deletions=0, repository="acme/engine", author_login=login,
                  parents=1)


def test_parse_rule_accepts_built_ins_and_csv_paths():
    assert parse_rule("Bots") == ("bots", None)
    assert parse_rule("none") == ("none", None)
    assert parse_rule("team/list.csv") == ("file", Path("team/list.csv"))
    with pytest.raises(ValueError, match="--highlight must be one of"):
        parse_rule("everyone")


def test_bots_rule():
    rule = build_rule("bots", "acme")
    assert rule.label and not rule.needs_members
    assert matches(rule, commit(name="dependabot[bot]", login=None))
    assert not matches(rule, commit())


def test_outside_and_members_rules():
    outside = build_rule("outside", "acme", members={"Ada", "grace"})
    assert outside.needs_members
    assert not matches(outside, commit(login="ada"))
    assert matches(outside, commit(name="Guest", email="g@example.org", login="guest"))
    assert matches(outside, commit(login=None))
    members = build_rule("members", "acme", members={"ada"})
    assert matches(members, commit(login="ADA"))
    assert not matches(members, commit(login=None))


def test_file_rule_matches_on_email_or_case_insensitive_name(tmp_path):
    listing = tmp_path / "key-people.csv"
    listing.write_text("name,email,contribution\n"
                       "ADA LOVELACE,,Analytical engine\n"
                       ",bob@example.org,Reviewer\n")
    rule = build_rule("file", "acme", path=listing)
    assert rule.label == "contributors listed in key-people.csv"
    assert matches(rule, commit(name="Ada Lovelace", email="other@example.org"))
    assert matches(rule, commit(name="Robert", email="bob@example.org"))
    assert not matches(rule, commit(name="Grace", email="grace@example.org"))
    assert entries_for(rule, []) == list(rule.entries)


def test_read_entries_requires_a_usable_column(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("login\nada\n")
    with pytest.raises(ValueError, match="needs a 'name' or 'email' column"):
        read_entries(bad)


def test_entries_for_lists_each_highlighted_identity_once():
    rule = build_rule("bots", "acme")
    commits = [
        commit(name="dependabot[bot]", email="dep@users.noreply.github.com", login=None),
        commit(name="dependabot[bot]", email="dep@users.noreply.github.com", login=None),
        commit(name="Dependabot[bot]", email="other@users.noreply.github.com", login="dependabot[bot]"),
        commit(),
    ]
    entries = entries_for(rule, commits)
    assert entries == [
        {"name": "dependabot[bot]", "email": "dep@users.noreply.github.com",
         "contribution": "bots: no linked GitHub account"},
        {"name": "Dependabot[bot]", "email": "other@users.noreply.github.com",
         "contribution": "bots: dependabot[bot]"},
    ]
    assert entries_for(build_rule("none", "acme"), commits) is None
    redacted = entries_for(rule, commits, redact_emails=True)
    assert [entry["email"] for entry in redacted] == ["redacted", "redacted"]
    assert [entry["name"] for entry in redacted] == ["dependabot[bot]", "Dependabot[bot]"]


def test_user_account_labels():
    outside = build_rule("outside", "ada", members={"ada"}, owner_type="User")
    assert outside.label.startswith("accounts other than ada")
    assert build_rule("members", "ada", members={"ada"}, owner_type="User").label == "the account ada itself"


def test_unknown_rule_is_rejected():
    with pytest.raises(ValueError):
        build_rule("file", "acme")
    with pytest.raises(ValueError):
        build_rule("mystery", "acme")
