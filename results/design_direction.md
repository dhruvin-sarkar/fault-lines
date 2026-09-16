# Design direction

Written before any frontend code. Everything below is a constraint on the build, not a mood board.

## The idea: a measuring instrument, not an article

The site reports a destructive experiment on a wiring diagram. The reader should feel they are reading an
instrument panel during a controlled failure: dense, exact, legible at a glance, with numbers that can be
compared against each other without effort. Nothing decorative earns its place unless it carries a value.

Three consequences:

1. **Data first, prose second.** Every section opens with the measurement, then explains it. Headlines are
   numbers with units, not slogans.
2. **One continuous visual system.** The site and the figures in the paper share the same six strategy colors
   and the same axis conventions, so a plot lifted from the repository looks native on the page.
3. **The reader can break it themselves.** The interactive sections are the argument, not an ornament.

### The motif

A single hairline rule runs down the page as the spine of the layout. At each section boundary the rule is
offset horizontally by a few pixels, the way a fault displaces a stratum. It is the only ornament in the design
and it is drawn with one CSS border, never animated.

## What this is not

Explicitly ruled out, because these are the defaults everything drifts towards:

- No cream background, serif headings and terracotta accents. No editorial or "long-read" costume.
- No near-black surface with neon green or cyan accents, no glow, no terminal cosplay.
- No generic SaaS component kit: no rounded cards with drop shadows in a three-up grid, no gradient buttons,
  no pill badges announcing features.
- No all-caps letterspaced eyebrow labels, no middle dots between metadata items, no arrows appended to link
  text, no `01 / 02 / 03` section numbering.
- No oversized hero sentence with one word in a highlight color.
- No fade-up-on-scroll applied to every block. Scroll position does not trigger decoration.
- No stock photography, no illustration of a fly, no brain clip art.

## Type

Two typefaces, each with one job. Both are variable fonts served locally from the build, not from a CDN.

| Role | Face | Usage |
|---|---|---|
| Headings, body, UI | Archivo | Grotesque with a narrow cast; set headings at tight tracking (-0.02em) and weight 600, body at 400/17px, line height 1.55. |
| Numbers, labels, code, axis ticks, table cells | Spline Sans Mono | Every figure quantity, every table column of numbers, every control label. Tabular by construction, so columns align and a changing number does not shift the layout. |

Rules: a number that a reader may compare with another number is always monospaced. Body text never goes above
20px or below 14px. Headline sizes step 40 / 28 / 20 / 17. No italics except for species names.

## Color

Light surface only; the palette is the one already validated for the figures, so the site and the plots agree.

| Token | Value | Use |
|---|---|---|
| `--paper` | #f4f5f3 | page background |
| `--panel` | #fcfcfb | plot and table surfaces |
| `--ink` | #0b0b0b | primary text |
| `--ink-2` | #52514e | secondary text, captions |
| `--muted` | #898781 | random baseline, disabled, axis labels |
| `--rule` | #e1e0d9 | hairlines, grid, the fault spine |
| `--axis` | #c3c2b7 | axis lines |
| `--break` | #d1344b | the failure signal: threshold markers, the point where flow halves |

Strategy colors are fixed and never reassigned by rank or filtering:

| Strategy | Color |
|---|---|
| sensory-motor betweenness | #2a78d6 |
| betweenness | #eb6834 |
| PageRank | #1baf7a |
| weighted out-degree | #eda100 |
| weighted in-degree | #e87ba4 |
| random | #898781 |

Color never carries identity alone: every series is directly labeled or listed in a legend, and the strategy
tables repeat the same values in text.

## Layout

A 12-column grid, 1120px maximum content width, 24px gutters, 16px side margins on phones. Sections are
separated by the offset hairline and 96px of space, not by boxes. Figures may break out to the full width;
text never exceeds 68 characters per line. Tables are plain: a header hairline, row hairlines at 8% opacity,
no zebra striping, no borders around the table.

## Motion

Two kinds only:

1. **Data motion.** The percolation animation advances through removal batches; the collapse race runs six
   strategies at once. Both are driven by the data and controlled by the reader (play, pause, scrub).
2. **State feedback.** Hover and focus change color in 120ms. Focus rings are visible and never removed.

Nothing else moves. No parallax, no scroll-linked reveal, no counters that tick up.

## Sections

| Section | Content | Visual |
|---|---|---|
| Hero | The headline threshold from the critical-threshold analysis, stated as a number with its comparison to random removal, plus a live percolation visualization running behind or beside it. | Animated flow-capacity curve drawn from static JSON. |
| Break it yourself | The reader picks a strategy and a removal fraction and sees the resulting flow capacity, reachability and critical threshold. | Interactive curve with a draggable removal fraction. |
| Collapse race | All six strategies advancing together to the halving point, so the reader sees which order of removal destroys routing first. | Six-series animation with a shared clock and a finishing order. |
| Findings | One block per result (thresholds, null model, literature agreement, brain against nerve cord, avalanches, synthetic-lethal pairs, bilateral redundancy, the hidden bottleneck), each with its own anchor so it can be linked directly, each with a figure or table. | The result figures, restyled as native charts where they are interactive and as images where they are not. |
| Methods and validation | The graph construction, the removal protocol, the null model and its p-values, and the limits of the claims. | Table of the validation results and a link to the paper. |

Every section is reachable from a persistent table of contents on wide screens, and each finding has a stable
`#id`.

## Data

The site loads static JSON only, exported from the pipeline into `web/public/data`. No API, no runtime
computation of anything that the pipeline can precompute, no client-side graph library. Percolation curves are
downsampled to the removal batches that exist in the results; nothing is smoothed or interpolated for looks.

## Accessibility

Contrast at least 4.5:1 for text and 3:1 for interface elements against `--paper`. Every interactive control
is reachable and operable by keyboard, animations respect `prefers-reduced-motion` by rendering the final
state, and every figure has a text alternative: either a table of the same numbers or a short description of
the trend with its endpoints.
