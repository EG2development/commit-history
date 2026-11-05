# Third-party notices

The site in this directory bundles the following works. Each keeps its own
licence; the project's MIT licence covers only the files it lists.

## ORCA commit-history visual

- Source: <https://github.com/nbremer/ORCA>, directory `commit-history`, commit
  `77745774d9d189818ab1ba27e07979897434abf9` (copied on 5 November 2026)
- Author: Nadieh Bremer, Visual Cinnamon, made possible through the MIECO/Builder
  program of Mozilla
- Licence: Mozilla Public License 2.0, reproduced in `LICENSE-ORCA.txt`
- Files used **unmodified**: `css/chart.css`, `img/legend_insertions.png`,
  `img/legend_deletions.png`, `img/legend_similar.png`, `img/legend_no_change.png`,
  `img/legend_version.png`
- Files **modified** (still MPL-2.0):
  - `createORCAVisual.js`: the two stretch goals the upstream header listed as TODOs
    were implemented on 5 November 2026 (a fade for the hover dimming layer, and an
    animated transition from the first to the second circle pack), and text taken from
    the commit data is written to the tooltip and the message with `textContent`
    instead of `innerHTML`. The header of the file names every function that was added
    or changed; a diff against the upstream commit shows nothing else.
  - `css/style.css`, derived from the upstream `css/style.css`; the page text and
    layout ideas of `index.html` also follow the upstream showcase page

The MPL-2.0 is a file-level licence. You may use these files alongside code under
another licence, as this project does, provided the MPL-covered files, this notice
and the licence text stay with the site.

## D3

- `lib/d3.v7.js`, D3 v7.7.0, copyright 2010-2022 Mike Bostock
- Licence: ISC, <https://github.com/d3/d3/blob/main/LICENSE>

## seedrandom

- `lib/seedRandom.min.js`, seedrandom by David Bau
- Licence: MIT, <https://github.com/davidbau/seedrandom/blob/released/LICENSE>

## Awesomplete

- `lib/awesomplete.min.js` and `css/awesomplete.css`, Awesomplete by Lea Verou
- Licence: MIT, <https://github.com/LeaVerou/awesomplete/blob/gh-pages/LICENSE>

## Atkinson Hyperlegible

- `fonts/AtkinsonHyperlegible-{Regular,Italic,Bold,BoldItalic}.woff2`, copyright 2020
  Braille Institute of America, Inc., copied on 5 November 2026 from
  `fonts/webfonts/` of <https://github.com/googlefonts/atkinson-hyperlegible>
  (archived, read-only since 19 April 2026)
- Licence: SIL Open Font License 1.1, reproduced in `fonts/OFL.txt`
- Declared in `css/style.css`; the page makes no request to Google Fonts. Code
  snippets use the visitor's system monospace font instead of Fira Code.
