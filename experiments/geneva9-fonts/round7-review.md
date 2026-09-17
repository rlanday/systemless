# Coppet: R middle bar, ampersand and i entry stroke

The user said round six looked better, then asked about adding the short horizontal entry stroke visible in original Geneva, sharpening the ampersand at 9 pixels, and sharpening R's horizontal bar. The new trials keep round six's rightward, aligned i; aligned curved-foot l; and selected aligned T. No renderer settings change.

| Trial | Version | Changes relative to round six |
| --- | --- | --- |
| `Coppet-Round7-Sharp.ttf` | 0.022 | R middle-bar placement and ampersand upper-loop fitting |
| `Coppet-Round7-Entry.ttf` | 0.023 | A small entry stroke on lowercase i |
| `Coppet-Round7-Combined.ttf` | 0.024 | Both treatments |

The user compared the separate treatments and said **both changes look better**. `selection.json` therefore selects the combined version 0.024 as the new comparison baseline. This does not make it a production default or approve every other glyph. The same Windows Systemless proof, city and New City replay are available at 100% and 138%, with a 4× proof for inspecting shapes.

## Why the R middle bar looks soft

R's middle bar occupied outline y=276…347 at UPEM 900: about 2.76…3.47 logical pixels at size 9. Its retained rendering spread coverage over two final pixel rows. Move that bar up 38 units to y=314…385, keeping its 71-unit thickness. Adjacent curves and the diagonal leg's join move continuously; the baseline, cap height and bowl-side landmark remain fixed. The upper counter is consequently a little shorter, which should be judged in the enlarged and 138% views.

At an interior bar column, the retained raster's native-size coverage changes from 114.75/255 in one row and 63.75/255 in the next to 178.5/255 in one row and zero in the next. The coverage is concentrated without increasing the sum at that sample. This is a local coverage diagnostic, not a general perceptual-sharpness score. R's 9-ppem guest bitmap is identical to the previous version.

## Ampersand

The upper loop's near-vertical sides previously straddled final pixel columns, adding gray to the small counter while leaving the sides faint. Fit those sides closer to native pixel centers at x=1.5 and 4.5, with a gradual transition into the crossing. This opens and slightly widens the upper loop. The overall x=100…600 ink bounds, advance 800, and accepted surrounding whitespace are unchanged. This is an outline change; it does not turn off antialiasing.

At the upper loop's middle row, the side coverages increase from about 117/139 to 205/200 out of 255. The two counter pixels decrease from about 83/60 to 3/4. The total retained ink coverage increases about 6.9%, despite similar side-stroke widths, because the loop is wider. Review whether it now looks too broad or heavy. Its guest bitmap deliberately changes too: the upper left side now survives the monochrome threshold.

## Lowercase i entry stroke

Draw a short leftward extension using Coppet's existing ~72-unit stroke weight. It occupies x=25…185 and y=437…509, adding 89 units to the left of the unchanged x=114…185 shaft. The original dot contour and the three-pixel advance remain exact. This fills some of the blank space before i while retaining the native alignment that the user preferred. Check minimum, Citizens and Rail for a cramped or overly busy appearance.

The old i guest mask was one column wide; the new one has a visible two-column entry row, the same separate dot, and the same main-stem column. No negative bearing or collision with a neighboring character cell is introduced. The accepted l foot's existing 9-ppem hint remains unchanged.

## Source and licensing rationale

`refine-round7.py` reads only the existing OFL Inter-derived Coppet font as its artwork input. The entry stroke is constructed from Coppet's own dimensions, and the R/ampersand edits transform the existing licensed contours. No Apple font data or traced Apple contours are imported into the derivative. The original System 6 Geneva reference remains local and separate. Coppet retains Inter attribution and the OFL.

The U.S. Copyright Office generally excludes typeface shapes from copyright, while sufficiently original font-generating software can be protected. That distinction supports drawing our own functional entry stroke; it does not authorize copying Apple's font software. Other jurisdictions differ: UK law explicitly addresses copyright in typeface designs. This is a documented design/provenance approach, not a worldwide legal-clearance opinion.

Sources checked 2026-09-17:

- [U.S. Copyright Office Circular 33, Typeface, Fonts, and Lettering](https://www.copyright.gov/circs/circ33.pdf), page 3.
- [Copyright Office Compendium §723](https://www.copyright.gov/comp3/chap700/ch700-literary-works.pdf#page=53), font-generating programs.
- [UK Copyright, Designs and Patents Act §54](https://www.legislation.gov.uk/ukpga/1988/48/section/54), typeface-design provisions.
- [OFL modification guidance](https://openfontlicense.org/how-to-modify-ofl-fonts/).

## Validation and reproduction

Run `refine-round7.py` after the prior build/refinement scripts. It regenerates hints using the same ttfautohint settings and reinstates the existing l-foot hint. Run the included `run-round7.ps1` with the existing native `audit-pedantic.exe` and `render-round3.exe`, then `verify-round7.py CAPTURE_ROOT`.

- Strict Windows Skrifa hint execution passes at guest 9 ppem and retained 36 ppem for all 95 ASCII glyphs in each candidate.
- Every advance and baseline metric is unchanged.
- Unrelated glyph pixels and placements are identical. R's guest bitmap is unchanged.
- Only & and/or i change in guest rendering; only &, R and/or i change in retained rendering, according to the selected trial.
- All non-space guest glyphs retain ink, and i's dot, gap and entry row are checked explicitly.
- All three trials have native and 138% proof/city/dialog captures. Their hashes and the local coverage measurements are in `validation-round7.json`.

The experiment still needs wider glyph review, GUI/clipping/font-precedence checks and native/scaled performance measurements against current master before a production PR.
