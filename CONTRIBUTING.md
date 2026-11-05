# Contributing

Thank you for helping. This page says who owns which part of the project, where a change
belongs, and how to propose one so that it can be merged quickly.

By taking part you agree to the [code of conduct](CODE_OF_CONDUCT.md). A security problem
goes through the [security policy](SECURITY.md), never through a public issue.

## Who owns what

The repository combines work under two licences. The owner of each part decides where a
change goes.

| Part | Files | Owner and licence | Where a change goes |
| --- | --- | --- | --- |
| The visual | `site/createORCAVisual.js`, `site/css/chart.css`, `site/css/style.css`, `site/img/legend_*.png` | Nadieh Bremer, Visual Cinnamon: the [ORCA commit-history visual](https://github.com/nbremer/ORCA/tree/main/commit-history), MPL-2.0 | Upstream first, see below |
| Bundled libraries and fonts | `site/lib/`, `site/css/awesomplete.css`, `site/fonts/` | Their authors, listed in [`site/THIRD_PARTY_NOTICES.md`](site/THIRD_PARTY_NOTICES.md) | Replace the file with a newer release and update the notice |
| Everything else | collector, page script, workflow, tests, documentation | This project, MIT | Here |

### Changes to the visual go upstream first

Nadieh Bremer designed and wrote the visual and maintains it in
[nbremer/ORCA](https://github.com/nbremer/ORCA). This project is one of its users, not its
owner. A change to how the chart looks or behaves is therefore proposed there first, as an
issue or pull request on the upstream repository, and arrives here when the new upstream
file is vendored. That keeps one version of the visual in the world and credits the work
where it is done.

Carry a change here only when it cannot go upstream or has not been taken yet, and then:

1. Keep the upstream header naming the author, and every licence notice in the file; the
   MPL-2.0 (section 3.4) does not allow them to be removed or altered. The file stays under
   the MPL-2.0 (section 3.1) whatever licence the rest of your change uses.
2. Describe the change in the comment at the top of the file and name the functions you
   touched, as the current header does, so that a diff against the upstream commit explains
   itself.
3. Record the upstream commit you started from and the change in
   [`site/THIRD_PARTY_NOTICES.md`](site/THIRD_PARTY_NOTICES.md).
4. Do not rename, re-licence or re-attribute the file, and leave the credit line on the page
   as it is.

When upstream moves on, re-vendor: copy the new upstream file, re-apply the changes named in
the header, and update the commit hash in the header and in the notices.

### Credit every source

Code, text, data or images adapted from anywhere else are credited where they are used:
author, source, licence and version in the file's header comment, and an entry in
[`site/THIRD_PARTY_NOTICES.md`](site/THIRD_PARTY_NOTICES.md) when the file ships with the
site. [`CITATION.cff`](CITATION.cff) lists the visual under `references` so that anyone citing
this project cites its original author too; add a reference there for any further work the
project comes to build on. Not crediting a source breaks the code of conduct and, usually,
the source's licence.

## Setting up

Python 3.11 or later; nothing outside the standard library is needed at run time.

```bash
uv venv .venv && uv pip install -e '.[dev]' --python .venv/bin/python
.venv/bin/python -m pytest          # no network needed
.venv/bin/ruff check src tests
```

To see the page, run the collector against an organisation you can read (see the
[README](README.md#quick-start-see-your-organisation-locally)) and serve `site/` with any
static server.

## Making a change

- Branch from `main` and keep one change per pull request.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `ci:`, `test:`).
- The collector stays standard-library only, tests must not need the network, and new files
  stay under 500 lines. `pytest` and `ruff check src tests` must pass.
- Text that users read is British English. A statement about GitHub says when it was read,
  because GitHub changes.
- Documentation follows [Diátaxis](https://diataxis.fr/): how-to guides in `docs/how-to/`,
  reference in `docs/reference/`, and the README stays the overview.
- A change that alters a design decision gets a decision record in the MADR format next to
  [ADR-0004 and ADR-0005](docs/decisions/README.md); propose it, do not accept it yourself.
- Keep author emails, tokens and real commit data out of code, tests, fixtures, issues and
  pull requests. `tests/fakes.py` shows how to build synthetic data.

## Pull requests

Fill in the pull request template; its checklist is the review checklist. For a change to a
vendored file, link the upstream issue or pull request and include the diff against the
upstream commit.

## Bugs and feature requests

Use the issue forms. They ask where the problem is, because a request about the chart itself
belongs on the upstream project's tracker, which the form chooser links to.
