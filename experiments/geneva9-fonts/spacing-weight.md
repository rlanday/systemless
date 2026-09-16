# Coppet: headline spacing and stroke weight

The initial fitted Inter study used the historical substitute's per-glyph ink bounds. Matching advance widths preserved text layout, but those independent transformations did not preserve a consistent typeface weight or balance the visible space between letters.

The SC2K resource and native DrawString trace both contain exactly `Citizens Demand Road&Rail`. There is no space inside Demand or around the ampersand. Its 25 ASCII bytes are drawn in a single DrawString call. The reported splits after both i characters and after m were visual gaps inside the unchanged advance cells.

Inside Macintosh: Text, [Font Measurements](https://dev.os9.ca/techpubs/mac/Text/Text-186.html), distinguishes the glyph's ink bounding box and side bearing from its origin-to-origin advance. These changes adjust artwork within the existing cells. They add no pair kerning or tracking and preserve all 95 ASCII advances, string lengths, and baseline GetFontInfo measurements.

## Spacing changes at logical size 9

| Glyph | Advance | Earlier ink x bounds | Revised ink x bounds | Reason |
| --- | ---: | ---: | ---: | --- |
| c | 5 | 0–3 | 0–4 | Match the width of other round lowercase letters; reduce the gap in city and correct its unusually light stroke |
| i | 3 | 0–1 | 1–2 | Redistribute the excess space on the right while placing its dot and stem within logical pixel column 1 |
| m | 8 | 0–6 | 0–7 | Expand each inner counter by 0.5, retaining the three straight stem widths |
| & | 8 | 0–5 | 1–6 | Balance the visible gaps in d&R: approximately 1/3 becomes 2/2 |
| l | 3 | 0–1 | 1–1.8 | Reduce stem weight and align its left edge at logical x=1 for clearer native-size rendering |

Bounds describe the font outline, not a guarantee of identical visible pixel gaps after hinting and filtering. i retains its original contour shape and dot-to-stem relationship; translating both keeps them centered together.

## Stroke consistency

| Straight stem | Earlier logical width | Revised width |
| --- | ---: | ---: |
| n/h reference | approximately 0.80–0.81 | unchanged |
| m reference | 0.73–0.74 | unchanged |
| j | 0.90 | 0.80 |
| r | 1.27 | 0.80 |
| l | 1.00 | 0.80 |
| t | 0.88 | 0.80 |

r's oversized stem came from fitting a narrow Inter glyph to a much wider box. The correction narrows that stem while retaining the shoulder's outer extent. j retains its dot and hook extent. t retains the accepted height, crossbar and vertical coordinates; only the shaft is thinned. c's horizontal expansion brings its middle stroke from roughly 0.58 to 0.77 logical pixels, close to o. These are optical corrections to selected letters, not a requirement that every curve or diagonal have the same horizontal cross-section.

## Native-size clarity and guest bitmap validity

Systemless draws an aliased one-bit mask at logical size for guest QuickDraw operations and retains grayscale outline coverage at 4× for host presentation. A good-looking enlarged glyph does not establish that its guest mask or native-size presentation is correct.

An early trial centered the thin i/l stems between logical pixels. This split their coverage into two pale columns at 100%, and neither column met the guest's threshold. Both guest glyphs became blank. The final placement puts the narrow i and l strokes within logical pixel column 1; geometry alone concentrates their coverage in one column without artificially emboldening them.

The font contains ttfautohint instructions, but [ttfautohint does not perform horizontal hinting](https://freetype.org/ttfautohint/doc/ttfautohint.html). Requesting a monochrome target cannot invent missing x-axis instructions. Native diagnostics confirmed hinting was enabled and completed without interpreter errors. This was a limitation of the generated font's instructions and the chosen placement, not evidence of a general Systemless hint-interpreter failure.

Verification covers all 95 ASCII advances, unchanged font metrics, binary-mask ink for every non-space character, and per-glyph raster comparisons at 9-pixel monochrome and 36-pixel retained grayscale sizes. Only &, c, i, j, l, m, r, and t may differ from the accepted t-only baseline. The other 87 must remain identical. Full city and New City screenshots use the same fixed-clock input replay at native size and 138%. `validation-refinement.json` records the results; interaction and performance validation remain pending.

## Remaining visual review

- j's dot is larger than i's, and there is still extra space after j. Check “jumps.”
- h's arch is about 0.32 logical pixels higher than n's. Compare h, n and m.
- Compare the apparent darkness of a/e/s/o; evaluate curved strokes optically, not by horizontal scanline width alone.
- Review capitals, figures and punctuation in a later systematic pass. The current family is still a 9-point ASCII study; it does not cover all Mac Roman characters or other optical sizes.

Keep the current changes separate from new glyph edits until the user reviews native-size clarity and the corrected headline. Before a production proposal, validate controls, selection/inversion, caret erasure, clipping, guest-font precedence and native/scaled performance on the current master base.
