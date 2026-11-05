import pytest

from commit_history.model import Commit, decorations_for, git_timestamp, iso_timestamp, slug_for, subject_of


def make_commit(**overrides) -> Commit:
    data = dict(
        commit_hash="a" * 40, decorations="", committer_email="ada@example.org", committer_name="Ada",
        commit_time="2026-01-02 03:04:05 +0000", author_email="ada@example.org", author_name="Ada Lovelace",
        author_time="2026-01-02 03:04:05 +0000", commit_title="Add", files_changed=1, line_insertions=1,
        line_deletions=0, repository="acme/engine", author_login="ada", parents=1,
    )
    data.update(overrides)
    return Commit(**data)


def test_git_timestamp_converts_iso_to_git_form_in_utc():
    assert git_timestamp("2023-10-15T07:08:59Z") == "2023-10-15 07:08:59 +0000"
    assert git_timestamp("2023-10-15T09:08:59+02:00") == "2023-10-15 07:08:59 +0000"


def test_iso_timestamp_converts_git_form_to_utc_iso():
    assert iso_timestamp("2023-10-15 09:08:59 +0200") == "2023-10-15T07:08:59Z"
    assert iso_timestamp("2023-10-15 07:08:59 +0000") == "2023-10-15T07:08:59Z"


def test_decorations_put_version_like_tags_first_in_git_format():
    assert decorations_for(["latest", "v1.2.0"]) == "tag: v1.2.0, tag: latest"
    assert decorations_for([]) == ""


def test_slug_keeps_github_names_and_rejects_reserved_ones():
    assert slug_for("My.Repo_1-x") == "My.Repo_1-x"
    with pytest.raises(ValueError):
        slug_for("_all")
    with pytest.raises(ValueError):
        slug_for("..")


@pytest.mark.parametrize("overrides", [
    {"author_name": "dependabot[bot]", "author_login": None},
    {"author_email": "41898282+github-actions[bot]@users.noreply.github.com", "author_login": None},
    {"author_email": "actions@github.com", "author_name": "GitHub Actions", "author_login": None},
    {"author_name": "GitHub", "author_email": "noreply@github.com", "author_login": None},
    {"author_login": "renovate[bot]"},
])
def test_bot_detection(overrides):
    assert make_commit(**overrides).is_bot


def test_humans_are_not_bots():
    assert not make_commit().is_bot
    assert not make_commit(author_login=None, author_email="someone@example.org").is_bot


def test_subject_of_mirrors_git():
    assert subject_of("Fix it\r\nproperly\r\n\r\nbody") == "Fix it properly"
    assert subject_of("  \n\nLeading blanks\n") == "Leading blanks"
    assert subject_of("", "Headline…") == "Headline…"
    assert subject_of(None, None) == ""


def test_release_and_merge_flags_follow_the_visual():
    assert make_commit(decorations="tag: v1.0.0").is_release
    assert not make_commit(decorations="tag: 1.0.0").is_release
    assert make_commit(parents=2).is_merge
    assert not make_commit(parents=1).is_merge
