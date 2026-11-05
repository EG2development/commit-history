---
status: "proposed"
date: 2026-11-05
decision-makers: repository owner (to confirm)
---

# Reuse the ORCA commit-history visual behind an organisation page with minimal, documented changes

## Context and Problem Statement

The request was a project "like" the ORCA commit-history page by Nadieh Bremer for an organisation's own repositories. The visual is about 1,370 lines of canvas and d3 code (`createORCAVisual.js`) published under the Mozilla Public License 2.0, built for one repository per page and for a second dataset of "ORCA recipients" drawn as hexagons. Its header lists two unfinished stretch goals: an opacity animation on hover and an animation between the first and second circle pack. How should `github-commit-history/` provide that visual for many repositories, finish those two goals, and stay easy to update and clear about licensing?

## Decision Drivers

* The look and interactions the request points at, without re-implementing the force layout and canvas drawing.
* An update path when the upstream visual changes.
* Licence obligations that are simple to meet and visible to whoever publishes the site.
* No "ORCA" wording on an organisation's page, since the hexagons will mean something else there.
* The two stretch goals, which can only be implemented inside the drawing loop.

## Considered Options

* Vendor `createORCAVisual.js` unmodified and write a new page around it; leave the stretch goals undone.
* Vendor it, write the new page around it, and change the file only for its two stretch goals and for escaping text that comes from the data, with every change named in its header.
* Fork the visual freely: rename the ORCA concept, add repository switching inside it, restyle.
* Rewrite the visual from scratch.
* Point the upstream page at our data (not possible: it loads fixed data paths).

## Decision Outcome

Chosen option: "Vendor it, write the new page around it, and change the file only for its two stretch goals and for escaping text that comes from the data", because the visual reads just two CSV files, a handful of fixed element ids and one page-level constant (`FONT_FAMILY`), so everything organisation-specific fits in the surrounding page, while the stretch goals touch internal state that no wrapper can reach. The second dataset becomes a generic *highlighted contributors* list (name, email, contribution) that the collector derives from a rule (`bots`, `outside`, `members`, `none` or a hand-written CSV), and repository switching is a page reload with `?repo=<slug>`.

The first version of the pack, earlier on the same day, vendored the file byte-for-byte. The two stretch goals were then implemented in place: the dimming layer of the hover canvas now fades in and out over 300 ms, and after the loading animation the month circles glide over 1.2 s from the first pack to the tighter second one (skipped above 30,000 commits: at 24,401 commits the glide ran at 20 animation frames per second in software-rendered headless Chrome on 5 November 2026, against 62 for a 213-commit dataset). A third change came from reading the file for those goals: it wrote author names, commit titles, hashes and release tags into the tooltip and the status message with `innerHTML`, and the page's search list used Awesomplete's default `innerHTML` renderer, so a crafted commit message in any repository could run script in every viewer's browser. Both now render text nodes only. All changes are confined to functions named in the file's header. `css/chart.css` and the legend images are used unmodified; `css/style.css` is derived from the upstream file and keeps the MPL header. `site/THIRD_PARTY_NOTICES.md` lists every vendored file with the upstream commit (`7774577`) and `site/LICENSE-ORCA.txt` carries the licence text.

### Consequences

* Good, because an upstream fix is still adopted by taking the new upstream file and re-applying the named additions; a diff between the vendored file and upstream shows only the header and those functions.
* Good, because the MPL-2.0 is file-scoped: the collector, workflow, tests and page script stay MIT, and the obligations are the licence text and notices that already travel with the site.
* Bad, because the vendored file is no longer byte-identical to upstream, so verifying provenance means reading a diff rather than comparing a checksum.
* Bad, because switching repositories reloads the page; the visual binds to one container once and offers no teardown.
* Bad, because two upstream rules are inherited unchanged: a commit is a release only when a tag contains `v` followed by a digit, and hover matching uses the author name only. The page explains both.
* Good, because the page is self-contained: the Atkinson Hyperlegible web fonts are served from the site under the SIL Open Font License 1.1, so neither the page nor the visual's canvas text depends on a request to Google Fonts.

### Confirmation

A diff of `site/createORCAVisual.js` against upstream commit `7774577` must show only the header comment and the functions it names. A test repository whose author name and commit title carry an `<img onerror>` payload must show that text literally and run nothing; on 5 November 2026 the payload executed with the upstream file and not with the changed one. On 5 November 2026 a headless Chrome driven over the DevTools protocol measured the hover canvas's mean alpha rising from 4 to 18 over about 300 ms on hover, holding under a click and returning to 0 on leave or reset, and the main canvas changing across 10 sampled frames before settling, with no exceptions.

## More Information

* Upstream: <https://github.com/nbremer/ORCA/tree/main/commit-history>, read on 5 November 2026; licence: <https://www.mozilla.org/en-US/MPL/2.0/>.
* Related: [ADR-0004](0004-collect-organisation-commit-history-through-the-graphql-history-connection.md) covers how the data is collected.
