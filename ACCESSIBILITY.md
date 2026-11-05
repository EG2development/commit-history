# Accessibility

This page says what the published site does for accessibility, what it cannot do yet, and
how to report a barrier. It was written on 5 November 2026 from the page's markup and from
driving it in a browser; it is not a formal audit against WCAG.

## What the site does

- **Text alternatives for the chart.** The chart is drawn on a `<canvas>` and carries
  `role="figure"` with a label that says what it shows and that the repositories table below
  lists the same data as text. The table has real header cells, can be sorted and filtered,
  and the **download** button gives the commits as CSV for any other tool.
- **Legend images have alt text** that states the rule each colour encodes, and the hexagon
  legend is an inline SVG with a role and label. Highlighted contributors differ by shape
  (hexagon against circle), not only by colour.
- **Controls are native elements.** The repository switcher is a labelled `<select>`, the
  filter is a labelled search input, and the download is a `<button>`, so they work with a
  keyboard and a screen reader.
- **Type.** Text is set in Atkinson Hyperlegible, a typeface designed for low vision, served
  from the site itself. Nothing flashes, and the two animations (a fade on hover and a
  one-off glide of the month circles) stop within about a second.
- **No third-party requests**, so no tracking scripts interfere with assistive technology.

## Known barriers

- **Individual commits cannot be reached with a keyboard.** Hover and click on the canvas
  are the only way to open a commit's tooltip or to highlight an author. The search box can
  highlight an author by name from the keyboard, but it cannot step through commits.
- **The tooltip is positioned next to the pointer** and is not announced by screen readers
  as it changes.
- **Colour carries meaning in the chart** (turquoise for more insertions, pink for more
  deletions, yellow for no change). The legend explains it in words and the table holds the
  numbers, but a reader who cannot tell the rings apart has no in-chart alternative.
- **Reduced motion is not detected.** The two animations run regardless of the operating
  system's reduced-motion setting.

The chart itself is Nadieh Bremer's ORCA commit-history visual (MPL-2.0). The barriers inside
the canvas therefore belong to that project too: a keyboard model or reduced-motion support
is proposed upstream first, as [`CONTRIBUTING.md`](CONTRIBUTING.md) explains, and taken here by
re-vendoring the file. The page around it, the table and the download are this project's and
are fixed here.

## Reporting a barrier

Open an issue with the bug report form and choose **Page** as the area, or, if you would
rather not post publicly, write to a maintainer or an organisation owner as the
[code of conduct](CODE_OF_CONDUCT.md) describes. Say which assistive technology or setting you
use, what you tried to do and what happened. Barriers are treated as bugs.

## Ownership

The maintainers of this repository own this page and review it when the page markup or the
vendored visual changes.
