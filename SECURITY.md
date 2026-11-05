# Security policy

## Supported versions

The `main` branch is the only supported version. There are no releases yet: a fix lands on
`main` and the next workflow run publishes it.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Report it privately through GitHub: open the repository's **Security** tab and choose
**Report a vulnerability**. That creates a draft security advisory that only the maintainers
can see. If the option is missing, the organisation that publishes the site has not enabled
private vulnerability reporting; write privately to one of its owners instead.

Say what you found, where (file, page, workflow step), how to reproduce it and what an
attacker could do with it. You will get an acknowledgement as soon as a maintainer reads the
report, normally within a week, and updates until the fix is published. There is no bug
bounty.

## What counts as a vulnerability

- Markup or script from commit data (author names, commit titles, tags, repository names)
  running in a viewer's browser. Everything that comes from commits is rendered as text; a way
  round that is a vulnerability.
- A token, or data the token should not have been able to read, reaching the workflow log,
  the Pages artifact or the published site.
- Author or committer emails appearing in the published data when `--redact-emails` is on.
- A problem in a bundled library or font (`site/lib/`, `site/fonts/`) or in one of the pinned
  GitHub Actions.

Something in the published data about you, such as your name on a commit or a mistaken
attribution, is a privacy request rather than a vulnerability: write to the organisation that
publishes the site. The data is rebuilt from the repositories on every run, so the fix is in
the repository or in the collector's options.

## The visual

`site/createORCAVisual.js` is Nadieh Bremer's ORCA commit-history visual (MPL-2.0), changed
only as its header says. A vulnerability in it almost certainly affects the upstream project
and every other site that uses it. Report it here through the channel above; the maintainers
fix the vendored copy and pass the report, with your name on it if you wish, to the upstream
project at <https://github.com/nbremer/ORCA> so that it is fixed at the source. Please give
both a chance to fix it before publishing details.

## How the project limits risk

- Every GitHub Action is pinned to a commit SHA and Dependabot keeps the pins current.
- The workflow needs read access only; the how-to describes a GitHub App with the minimum
  permissions.
- No commit data is committed; it travels inside the Pages artifact and emails are redacted
  by default.
- Text from commits is written with text nodes everywhere it appears (tooltip, status
  message, search list, table); this was checked with a crafted repository on
  5 November 2026.
