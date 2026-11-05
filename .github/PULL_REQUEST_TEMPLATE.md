<!-- Thanks. Keep author emails, tokens and real commit data out of the description, the diff and the tests. -->

## What and why

<!-- One or two sentences, and the issue this closes, if any: "Closes #123". -->

## Checklist

- [ ] `pytest` and `ruff check src tests` pass locally.
- [ ] Documentation that this changes is updated (README, `docs/how-to/`, `docs/reference/`), and any statement about GitHub says when it was read.
- [ ] Nothing adapted from elsewhere is left uncredited: author, source, licence and version are in the file header, and in `site/THIRD_PARTY_NOTICES.md` if the file ships with the site.
- [ ] No author emails, tokens or real commit data anywhere in this pull request.

### Only if a vendored file changed

(`site/createORCAVisual.js`, `site/css/chart.css`, `site/css/style.css`, `site/img/legend_*.png`, `site/lib/`, `site/fonts/`)

- [ ] The change was proposed upstream first, or this description says why it cannot be: upstream issue or pull request: <!-- link -->
- [ ] Nadieh Bremer's header, the licence notices and the credit line on the page are untouched; the file stays under its own licence.
- [ ] The file's header comment names the change and the functions touched, and `site/THIRD_PARTY_NOTICES.md` records the upstream commit and the change.
- [ ] The diff against the upstream commit is attached or linked.

### Only if a design decision changed

- [ ] A decision record in the MADR format is proposed in the decisions folder, not accepted by its author.
