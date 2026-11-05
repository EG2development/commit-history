# Command line

`commit-history` is installed by `pip install .`; `python -m commit_history` runs the same
program. `commit-history <command> --help` prints the options below.

## Exit status

| Status | Meaning |
|---|---|
| 0 | Every selected repository was written. |
| 1 | At least one repository failed; the others were written and `index.json` records each failure. |
| 2 | Usage, token or configuration problem; nothing may have been written. |
| 130 | Interrupted. |

## Token

`collect` uses the first of: `GITHUB_TOKEN`, `GH_TOKEN`, the output of `gh auth token`
(with `--hostname` when `--host` is not github.com). The token needs read access to the
repositories' contents and, for `--highlight outside` and `members`, to the organisation's
members. `from-git` needs no token.

## commit-history collect

Reads every repository of an organisation through the GitHub GraphQL API.

| Option | Default | Meaning |
|---|---|---|
| `--org LOGIN` | required | Organisation to read. A user account works too: its own repositories are listed, and for `outside` and `members` the account itself is the only member. The login is recorded with GitHub's spelling. |
| `--repo NAME` | all | Only this repository; repeat the option for several. `owner/name` is accepted. A name that does not exist or is not visible is recorded with status `error`. |
| `--since YYYY-MM-DD` | none | Ignore commits made before this date (UTC). |
| `--include-archived` | off | Also read archived repositories. Ignored when `--repo` is given. |
| `--include-forks` | off | Also read forks. Ignored when `--repo` is given. |
| `--highlight RULE` | `bots` | `none`, `bots`, `outside`, `members`, or the path of a CSV file with `name`, `email` and optional `contribution` columns. |
| `--combined-max N` | `50000` | Write `_all/commits.csv` when the organisation has at most N commits; `0` disables it. |
| `--page-size N` | `100` | Commits per GraphQL request, 1 to 100. Lower it when a large repository returns HTTP 502. |
| `--host HOST` | `github.com` | `github.com`, `<subdomain>.ghe.com` or a GitHub Enterprise Server host name or URL. |
| `--title TEXT` | the login | Display name used on the page. |
| `--output DIR` | `site/data` | Data directory the site reads. |
| `--clean` | off | Delete the output directory before writing. Without it, directories of repositories that no longer exist stay on disk but are not listed. |
| `--redact-emails` | off | Write empty `author_email` and `committer_email` columns and the placeholder `redacted` in `highlights.csv`; the visual then matches highlighted contributors by name only. `index.json` records `"emails": "redacted"`. |

Repositories without a default branch, or marked empty by GitHub, are listed with status
`empty` and cost no history request.

## commit-history from-git

Reads one local clone with `git log` and merges the result into the index.

| Option | Default | Meaning |
|---|---|---|
| `--repo-dir PATH` | required | Path of the clone (a working tree with `.git`, or a bare repository). |
| `--name OWNER/NAME` | required | Repository name to display; `OWNER` becomes the organisation when the index does not exist yet. |
| `--ref REF` | `HEAD` | Branch or ref to walk, for example `origin/main`. |
| `--highlight RULE` | `bots` | `none`, `bots` or a CSV path. `outside` and `members` are rejected because membership is not known. |
| `--host HOST` | `github.com` | Host used to build the repository link. |
| `--title TEXT` | existing title or `OWNER` | Display name used on the page. |
| `--output DIR` | `site/data` | Data directory the site reads. |
| `--redact-emails` | off | As for `collect`. |

The command runs:

```text
git -C <PATH> log <REF> --pretty=format:<record> --shortstat --decorate=short -M20 --encoding=UTF-8 --no-color
```

where `<record>` separates `%H %D %ce %cN %ci %ae %aN %ai %s %P` with the unit separator
character, so titles containing commas or quotes need no escaping. An existing `index.json`
keeps its other repositories and its `combined` entry; `source` becomes `git log`.
