# GitHub organisation commit history

An interactive, static web page that shows every commit of every repository in a GitHub
organisation: one circle per commit, clustered by month and sized by the lines it changed. The
visual is Nadieh Bremer's [ORCA commit history](https://nbremer.github.io/ORCA/commit-history/)
(MPL-2.0), changed only to finish the two stretch goals its header listed: the dimming on hover
fades in and out, and the month circles glide into their final, tighter pack after loading. It is
wrapped in an organisation page with a repository table, a repository switcher, a combined
all-repositories view and a rule for which contributors are drawn as hexagons: bots, contributors
from outside the organisation, members, or a hand-written list.

A Python collector with no dependencies beyond the standard library reads the history through
the GitHub GraphQL API, so nothing is cloned, and writes the CSV files the visual reads. A
GitHub Actions workflow runs it on a schedule and publishes the site to GitHub Pages without
committing any data. For a repository that is not on GitHub, a second command reads a local
clone with `git log`, the way the original visual did.

Built and checked on 5 November 2026 against a 17-repository organisation (213 commits in 24
seconds for 36 GraphQL points) and against mozilla/pdf.js, the repository the original visual
showcases (24,401 commits in 14 minutes for 273 points). On the commits both datasets hold, the
result matches the original's published data on every author email and release tag and on 95.8%
of non-merge commits' line counts exactly; the rest differ by git's rename detection, which
GitHub's diff does not apply. The workflow was run live the same day from a public repository
in that organisation with its own token: 10 public repositories, 58 commits, 22 points, emails
redacted, deployed to GitHub Pages at the first attempt once the actions were SHA-pinned.
Statements about GitHub in these pages were read from GitHub's documentation or checked against
its API on that date; both change.

## What the page shows

- **One repository at a time**, chosen with the switcher or `?repo=<name>` in the address, or
  all repositories together when the organisation has at most 50,000 commits.
- **Every commit on the default branch** as a circle: turquoise ring for more insertions than
  deletions, pink ring for more deletions, yellow dot for no change (merge commits), a ring for
  a release tag.
- **Hexagons** for highlighted contributors. With the default rule those are automation
  accounts such as Dependabot and GitHub Actions; `--highlight outside` marks everyone who is not
  a member of the organisation, which is the closest analogue to the original's "ORCA
  recipients".
- **Hover, click and search** by author name, exactly as on the original page.
- **A repository table** with commits, contributors, first and last commit, lines added and
  removed, the share of highlighted commits and the read status of each repository.
- **Data details** stating when the data was read, from where, under which rule, and the
  limits that apply.

## Quick start: see your organisation locally

You need Python 3.11 or later and either the GitHub CLI logged in (`gh auth status`) or a token
in `GITHUB_TOKEN` that can read the repositories. Nothing is written anywhere but `site/data`.

```bash
cd github-commit-history
uv venv .venv && uv pip install -e '.[dev]' --python .venv/bin/python   # or: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/commit-history collect --org <ORGANISATION> --output site/data
cd site && python3 -m http.server 8000
```

Open <http://localhost:8000/>. The collector prints one line per repository; this is the pilot
run, trimmed:

```text
EG2development: listing repositories via https://api.github.com/graphql (token from gh auth token)
EG2development: 17 repositories visible, 17 selected
EG2development/gcp-terraform: 91 commits, 0 releases, 0 highlighted (3.7s)
EG2development/terraform-aws-vpc: 6 commits, 1 releases, 1 highlighted (1.1s)
EG2development: wrote 17 repositories, 213 commits to site/data (36 requests, 36 points)
```

Useful variations:

```bash
commit-history collect --org <ORGANISATION> --highlight outside        # hexagons = non-members (needs read:org)
commit-history collect --org <ORGANISATION> --repo api --repo web      # a few repositories only
commit-history collect --org <ORGANISATION> --since 2024-01-01         # recent history only
commit-history collect --org <your-login>                              # a personal account works the same way
commit-history from-git --repo-dir ~/src/legacy --name <ORGANISATION>/legacy   # a local clone, no API
```

The exit status is 0 when every repository was written, 1 when some failed (the rest are
published and the failures are listed in the table), 2 for a token or usage problem. Every flag
is listed in the [CLI reference](docs/reference/cli.md).

## Publish it

[How to publish the site with GitHub Pages](docs/how-to/publish-with-github-pages.md) walks
through creating the repository, choosing a token (GitHub App, fine-grained token or the
workflow's own token), enabling Pages and running the workflow in `.github/workflows/`.

Mind the data: `commits.csv` carries author names, and emails unless you pass
`--redact-emails` (the workflow redacts by default). A Pages site on a public repository is
public. Keep the publishing repository private and check the Pages visibility options of your
plan before the first run. The data directory is ignored by git, so nothing personal lands in
the repository's history. Everything that comes from commits
(author names, titles, hashes, tags) is rendered as plain text in the tooltip, the status
message, the search list and the table, so a crafted commit message cannot inject markup into
viewers' browsers.

## Data files, decisions and tests

- [Data files](docs/reference/data-files.md) documents `index.json`, `commits.csv` and
  `highlights.csv`, including the twelve columns the visual needs and the three this project adds.
- Two decision records explain the design: [ADR-0004](docs/decisions/0004-collect-organisation-commit-history-through-the-graphql-history-connection.md)
  on reading history through GraphQL rather than cloning, and [ADR-0005](docs/decisions/0005-reuse-the-orca-commit-history-visual-behind-an-organisation-page.md)
  on reusing the visual with only its own stretch goals added.
- `.venv/bin/python -m pytest` runs 69 tests that need no network; `.venv/bin/ruff check src tests`
  lints. The GraphQL path was also compared with `git log --shortstat` on a cloned repository:
  every one of its 91 commits agreed on every field.

## Contributing, conduct, security and citation

The repository carries the community health files that GitHub's community standards
checklist looks for, and each one names the original author of the visual where that matters:

- [`CONTRIBUTING.md`](CONTRIBUTING.md) says who owns which part of the code. Changes to the
  chart itself go to Nadieh Bremer's [nbremer/ORCA](https://github.com/nbremer/ORCA) first and
  arrive here by re-vendoring; every other source is credited in its file header and in the
  third-party notices.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) is the Contributor Covenant 3.0, which counts
  failing to credit sources among its restricted behaviours.
- [`SECURITY.md`](SECURITY.md) explains private vulnerability reporting and that a problem in
  the visual is passed on to the upstream project so that it is fixed at the source.
- `.github/ISSUE_TEMPLATE/` and `.github/PULL_REQUEST_TEMPLATE.md` ask where a change belongs
  and whether attribution and notices were kept; the issue chooser links to the upstream
  tracker.
- [`CITATION.cff`](CITATION.cff) makes GitHub's "Cite this repository" cite the ORCA visual by
  Nadieh Bremer as well as this project.
- [`ACCESSIBILITY.md`](ACCESSIBILITY.md), GitHub's optional accessibility page, states what the
  site does, the barriers inside the canvas chart and the text alternatives for them.

On the pilot repository GitHub's community profile reported every item added on
5 November 2026.

## Known limits

- Only the default branch is walked, and only commits reachable from it, as `git log` does.
- Hover highlights match on author name, and a release is a tag containing `v` followed by a
  digit; both rules come from the visual and are explained on the page.
- GitHub may omit the number of changed files for very large commits; the line counts stay.
- Switching repositories reloads the page.

## Licence and attribution

The collector, page script, workflow, tests and documentation are MIT licensed. `LICENSE`
holds the plain MIT text only, so that GitHub detects the licence; this paragraph and the
notices file describe the split. The visual, its chart stylesheet and legend images are
copyright Nadieh Bremer, Visual Cinnamon, under the Mozilla Public License 2.0, and are listed
with the other vendored libraries in [`site/THIRD_PARTY_NOTICES.md`](site/THIRD_PARTY_NOTICES.md).
The visual's header keeps her credit banner, carries the MPL's source-code notice, and names
every function changed: the two stretch goals, and writing text that comes from commits with
`textContent` instead of `innerHTML`; nothing else in it was touched. The page's footer credits
her and links to the upstream repository. The Atkinson Hyperlegible font files in `site/fonts`
are copyright Braille Institute of America under the SIL Open Font License 1.1, so the page
makes no third-party requests at all.
