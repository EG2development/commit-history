---
status: "proposed"
date: 2026-11-05
decision-makers: repository owner (to confirm)
---

# Collect organisation commit history through the GitHub GraphQL history connection

## Context and Problem Statement

The `github-commit-history/` pack reproduces the ORCA commit-history visual for every repository of a GitHub organisation. The visual needs, for each commit, the hash, tags, author and committer identity, timestamps, title, the number of files changed and the lines inserted and deleted. The original obtains these by cloning one repository and parsing `git log --shortstat`. An organisation has tens to thousands of repositories, many of them private, and the collection has to run unattended on a schedule in GitHub Actions. How should the pack obtain per-commit line statistics for every repository without cloning them all?

## Decision Drivers

* Run unattended in a GitHub Actions job, in minutes for small and medium organisations, without disk space for full clones.
* Per-commit insertions and deletions, not weekly aggregates, that agree with `git log --shortstat` so the visual's legend stays truthful.
* Work with a GitHub App installation token, a fine-grained personal access token or the workflow token, on github.com, GHE.com and GitHub Enterprise Server.
* Standard library only, like the sibling packs.
* Keep a route that needs no GitHub API, for mirrors and repositories that are not on GitHub.

## Considered Options

* The GraphQL `history` connection on the default branch, which returns `additions`, `deletions` and `changedFilesIfAvailable` for 100 commits per request, plus `refs` for tags.
* REST: `GET /repos/{owner}/{repo}/commits` for the list and one `GET /repos/{owner}/{repo}/commits/{sha}` per commit for the statistics.
* Clone every repository and run `git log --shortstat`, as the original does.
* The repository statistics endpoints (`/stats/contributors`, `/stats/code_frequency`), which are weekly aggregates.

## Decision Outcome

Chosen option: "The GraphQL history connection", because it is the only option that returns per-commit line statistics in bulk: one request per 100 commits, each costing one point of the hourly budget, so a 100,000-commit organisation costs about 1,000 points and no disk. The REST route costs one request per commit, the clone route needs every repository on disk, and the statistics endpoints lose the per-commit grain the visual draws.

Merge commits are written with zero files and zero lines, which is what `git log --shortstat` prints for them. GitHub does report line counts for merge commits (the pilot organisation's merge of pull request #3 shows 14 additions), so copying its numbers would count a pull request's lines twice. Timestamps are normalised to UTC, which is also how the visual groups months. The `from-git` subcommand keeps the clone route for one repository at a time.

### Consequences

* Good, because the measured run over the 17-repository pilot organisation (213 commits) took 24 seconds and 36 GraphQL points on 5 November 2026.
* Good, because for a 91-commit repository with 2 merge commits the GraphQL output and the `git log --shortstat` output of a clone agreed on every commit and every field: 280 files, 5,764 insertions, 5,165 deletions.
* Bad, because `changedFilesIfAvailable` can be null for very large commits; the row keeps its line counts, the file count is left blank and the repository's `files_unavailable` count records it.
* Bad, because only the default branch is walked and rename detection follows GitHub's diff rather than `-M20`; both are also true of the original visual's command.
* Bad, because a page of a very large repository can exceed GitHub's time limit and return 502; `--page-size` lowers the page size at the cost of more requests.

### Confirmation

`tests/test_collect.py` covers node translation, paging, tag resolution and merge handling, and `tests/test_cli.py` covers partial failure (exit status 1) and the index.

The large-repository check was run on 5 November 2026 against mozilla/pdf.js, the repository the original visual showcases: 24,401 commits in 828 seconds over 273 requests (273 points), with no retries and no missing file counts. The original's published dataset for the same repository (20,226 commits from `git log --shortstat --tags -M20 -C20`) shares 20,206 commits with ours; on those, author emails agree in full, author names in all but 9 (the clone applied the repository's `.mailmap`, GitHub does not), release tags in all 76, and merge handling in all 8,181. File counts agree on 99.9%, insertions on 99.4% and deletions on 97.5%; 95.8% of non-merge commits are identical on all three. The remainder is git's rename and copy detection, which GitHub's diff does not apply. The 20 commits only the original holds sit on release branches that `--tags` walked and the default branch does not reach.

## More Information

* GitHub GraphQL: [Commit object](https://docs.github.com/en/graphql/reference/objects#commit) and [rate limits](https://docs.github.com/en/graphql/overview/rate-limits-and-node-limits-for-the-graphql-api). Field shapes were checked live against the pilot organisation on 5 November 2026.
* Token minting is left to the workflow (`actions/create-github-app-token`); the collector takes a ready token, unlike the sibling pack in [ADR-0003](0003-authenticate-as-a-github-app-with-the-standard-library.md).
* Related: [ADR-0005](0005-reuse-the-orca-commit-history-visual-behind-an-organisation-page.md) covers the visual this data feeds.
