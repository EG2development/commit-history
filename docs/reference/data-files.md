# Data files

The collector writes one directory per repository plus an index under the data directory
(`site/data` by default). The page reads nothing else. Paths are relative to that directory.

```text
index.json
<repository>/commits.csv
<repository>/highlights.csv        (absent with --highlight none)
_all/commits.csv                    (the combined dataset, when written)
_all/highlights.csv
```

`<repository>` is the repository name as GitHub spells it; characters outside `A-Z a-z 0-9 . _ -`
become `-`. The name `_all` is reserved for the combined dataset.

## index.json

| Field | Type | Meaning |
|---|---|---|
| `schema` | integer | Format version of this file, currently `1`. |
| `generated_at` | string | UTC time the run finished, `YYYY-MM-DDTHH:MM:SSZ`. |
| `organisation` | string | Login of the organisation or user account that was read, in GitHub's spelling. |
| `title` | string | Display name, `--title` or the login. |
| `host` | string | Host passed with `--host`; `github.com` by default. |
| `source` | string | `graphql` for `collect`, `git log` for `from-git`. |
| `since` | string or null | The `--since` date, when one was given. |
| `emails` | string | `included`, or `redacted` when the run used `--redact-emails`. |
| `highlight.rule` | string | `none`, `bots`, `outside`, `members` or `file`. |
| `highlight.label` | string or null | Sentence the page shows after "those are …"; null for `none`. |
| `combined` | object or null | Summary of `_all` (same count fields as a repository plus `slug`, `skipped`, `limit`); `skipped: true` with `slug: null` when the total exceeded `--combined-max`; null when disabled or nothing was collected. |
| `totals.repositories` | integer | Repositories listed, including failed and empty ones. |
| `totals.repositories_ok` | integer | Repositories with status `ok`. |
| `totals.repositories_failed` | integer | Repositories with status `error`. |
| `totals.commits`, `totals.highlighted_commits`, `totals.insertions`, `totals.deletions` | integer | Sums over repositories with status `ok`. |
| `run.token_source` | string or null | `GITHUB_TOKEN`, `GH_TOKEN` or `gh auth token`; null for `from-git`. |
| `run.graphql_requests`, `run.graphql_points` | integer | Requests sent and points charged in this run. |
| `site_repository` | string | Added by the workflow: URL of the publishing repository, used by the credit line. Absent in local runs. |
| `repositories` | array | One entry per repository, fields below. |

Each entry in `repositories`:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Repository name. |
| `full_name` | string | `owner/name`. |
| `slug` | string | Data directory name. |
| `url` | string | Browser URL of the repository. |
| `default_branch` | string or null | Branch that was walked; the `--ref` for `from-git`. |
| `private`, `archived`, `fork` | boolean | Repository flags from GitHub; `private` is null for `from-git`. |
| `pushed_at` | string or null | Last push as GitHub reports it. |
| `status` | string | `ok`, `empty` (no default branch or no commits), or `error`. |
| `error` | string or null | GraphQL or lookup error for status `error`. |
| `commits` | integer | Rows in `commits.csv`. |
| `contributors` | integer | Distinct author names, compared case-insensitively. |
| `first_commit`, `last_commit` | string or null | Oldest and newest commit time in UTC ISO 8601. |
| `insertions`, `deletions` | integer | Sums of line insertions and deletions. |
| `releases` | integer | Commits whose tags contain `v` followed by a digit. |
| `merge_commits` | integer | Commits with more than one parent. |
| `highlighted_commits` | integer | Commits the highlight rule matches. |
| `files_unavailable` | integer | Commits for which GitHub returned no file count. |

## commits.csv

UTF-8, comma separated, header row, newest commit first. The first twelve columns are the
schema of the original visual and are read by it; the last three are additions that the
visual ignores.

| Column | Type | Meaning |
|---|---|---|
| `commit_hash` | string | Full SHA. |
| `decorations` | string | Tags pointing at the commit in `git log --format=%D` form, `tag: v1.2.0, tag: latest`; version-like tags first; empty when none. Branch decorations are never included. |
| `committer_email` | string | Committer email; empty with `--redact-emails`. |
| `committer_name` | string | Committer name. |
| `commit_time` | string | Committer date, `YYYY-MM-DD HH:MM:SS +0000`; always UTC from `collect`, the committer's offset from `from-git`. |
| `author_email` | string | Author email; empty with `--redact-emails`. |
| `author_name` | string | Author name. |
| `author_time` | string | Author date, same form as `commit_time`. |
| `commit_title` | string | First line of the message. In `_all/commits.csv` it is prefixed with the repository name and a colon. |
| `files_changed` | integer or empty | Files changed; `0` for merge commits; empty when GitHub did not report it. |
| `line_insertions` | integer | Lines added; `0` for merge commits. |
| `line_deletions` | integer | Lines removed; `0` for merge commits. |
| `repository` | string | `owner/name` the row came from. |
| `author_login` | string | GitHub login linked to the author email; empty when none or from `from-git`. |
| `parents` | integer | Number of parent commits. |

## highlights.csv

UTF-8, comma separated, header row. The visual draws a commit as a hexagon when its
`author_email` equals an `email` here, or its `author_name` equals a `name` here ignoring case.

| Column | Type | Meaning |
|---|---|---|
| `name` | string | Author name as it appears in the commits. |
| `email` | string | Author email as it appears in the commits, or the placeholder `redacted` with `--redact-emails` (it must not be empty: the visual would treat an empty email as matching every commit whose email is empty). |
| `contribution` | string | For built-in rules, `<rule>: <login>` or `<rule>: no linked GitHub account`; for a hand-written list, whatever the list said. |

For the built-in rules the file lists every distinct name and email pair seen on a matching
commit, so matching is exact. For `--highlight path.csv` the file is the supplied list,
copied to every repository.
