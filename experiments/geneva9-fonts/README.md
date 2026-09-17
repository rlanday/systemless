# Geneva 9 comparison studies

These are three initial optical studies for review, not replacement defaults or production fonts. The scope is the 95 printable ASCII characters at 9 logical points. Other sizes, extended Mac Roman glyphs, and other families retain the current renderer. The branch is based on master 724e18f, including merged #1997.

| File | Source design | Construction |
| --- | --- | --- |
| kurrajong-curves.ttf | Historical OFL Kurrajong 24 | Potrace cubic contours converted to quadratics, fitted to the ink boxes and advances of Kurrajong 9 |
| inter-fitted.ttf (Cedar Nine Study) | Inter Regular, optical size 14 | Original outline contours fitted to Kurrajong 9 ink boxes and advances |
| nimbus-fitted.ttf (Harbor Nine Study) | Nimbus Sans Regular | Original vertical dimensions retained; horizontal ink bounds and advances fitted to Kurrajong 9 |

All three have newly generated hints from ttfautohint 1.8.4; old instructions were not retained after contour modification. Automatic x-height enlargement is disabled. Unhinted files are included for a subsequent controlled hinting comparison. The first pass changes design, fitting and hints together; it does not isolate which causes any perceived improvement. Potrace tracing is a starting point for manual curve refinement, not finished type design.

## What the game sees

Set `SYSTEMLESS_GENEVA9_COMPARISON` to an absolute candidate TTF path before launching this branch's Windows binary. It only affects bundled Geneva/Application size 9, after guest resource fonts have been considered. ASCII advances use the existing compatibility table. GetFontInfo metrics and extended glyphs come from the control. Glyph artwork still supplies the guest binary mask and retained outline samples; changing that artwork can affect pixels read by a game, so equal metrics alone do not establish compatibility. Validation should cover controls, inversions, caret erasure and clipping before any production change.

Inside Macintosh: Text (1993), pp. 3-66 and 3-74, describes GetFontInfo; pp. 4-7–4-9 and 4-18–4-19 describe outline strikes. Preserve those logical measurements and guest QuickDraw transfer operations while comparing host presentation. No kerning or arbitrary tracking correction is added.

Original Apple Geneva 9 is a separate local bitmap reference extracted from the user-provided System 6.0.8 disk. All 95 ASCII advances match the existing compatibility table. Apple artwork is not an input to these derivatives and is not included in this branch. Kurrajong is an independent substitute and must not be labeled original Geneva.

## Rebuild

Requires FontTools 4.65.0, Potrace 1.16, and ttfautohint 1.8.4. Run `python build.py`; `POTRACE` and `TTFAUTOHINT` can select tool paths. Inputs and their SHA-256 hashes are under `sources/`; each source keeps its OFL license. Inter and Nimbus derivatives use new family names. Generated fonts remain OFL-1.1. Review the output in Systemless at actual screen size: browser font rasterization is not a substitute for the game's Skrifa/retained-coverage path.

The selected study still needs visual and compatibility validation before a production PR. Small text must preserve the accepted weight, and both native and fractional-size city views must be reviewed. Performance measurements for any production proposal must include both sizes on the same base and report power conditions.

## Selected direction: Coppet

The user preferred fitted Inter and named the derivative **Coppet**. Version 0.002 is `generated/Coppet-Regular.ttf`. It corrects lowercase t only: fit the crossbar to the five-pixel lowercase height using Inter’s original x-height, instead of stretching the glyph to the seven-pixel cap-height bitmap bounds. Its outline height changes from 7 to approximately 6.19 logical pixels. The advance remains 4.

Run `python refine-inter-t.py` after `python build.py` to reproduce this revision. Original study files remain available for before/after comparisons. Font names and filenames reflect Coppet; Inter’s attribution and OFL license are retained. This remains a 9-point ASCII optical study.

Native Windows Skrifa/zeno checks compare each ASCII glyph at the 9-pixel monochrome guest size and 36-pixel retained grayscale size: only t changes in either mode. The other 94 glyphs have identical raster pixels and placements. All advances and bearings are unchanged. `validation-t.json` records the check and font hash. Native and 138% samples and city screenshots were rendered through the same Systemless build. The user accepted the t proportions.

## Spacing and stroke weight refinement

The first refinement is `generated/Coppet-Refined.ttf`, version 0.010. Rebuild it with `python refine-spacing.py` followed by `python refine-stems.py` after the t revision. See [spacing-weight.md](spacing-weight.md) for the diagnosis, optical changes, native-size placement checks, and remaining review items. Intermediate fonts remain comparison inputs; none is a production default.

The user called the first spacing/stem revision a big improvement, while reporting a narrow/light c and blurry i/l at native size. Version 0.010 addresses those reports and still needs visual review. A previous fractional-position trial produced empty one-bit i/l masks; it was rejected during compatibility validation. All non-space ASCII masks must contain ink before a candidate is considered usable.

`validation-name.json` verifies that adopting the final name Coppet changed no outline, metric, mapping or hinting tables in the six comparison font files. The existing native rendering checks therefore apply to the renamed fonts.

## Second optical review

The user selected the curved-foot lowercase l in `generated/Coppet-Round2-Foot.ttf` (0.012) at 100% and 138%. `selection.json` records current choices and their scope; they do not imply acceptance of every other recent glyph edit. `generated/Coppet-Round2-Plain.ttf` (0.011) remains a comparison input. Run `python refine-round2.py` after the previous steps. The variants preserve the accepted Demand/ampersand treatment, adjust c/j/l/r/s/t, and differ from each other only in lowercase l. See [round2-review.md](round2-review.md) for shared design parameters, spacing tradeoffs, the remaining Tool pair, and native validation.

`render-round2.rs` produces the current proof sheet and deterministic SC2K city/dialog screenshots through the comparison branch's Windows renderer. `verify-round2.py CAPTURE_ROOT` verifies the resulting glyph audits and records hashes in `validation-round2.json`. Original Geneva remains a local reference only. The current approach continues to modify Inter outlines; a METAFONT redesign is deferred.

## Rail, minimum and Tool follow-up

The user chose the curved-foot l shape, then requested further i/l spacing and P/y/j weight corrections. `refine-round3.py` generates those changes plus two separately reviewable T placement trials. The user initially selected the small T shift in `generated/Coppet-Round3-T25.ttf` (0.014). The other weight/spacing changes still needed adjustment. See [round3-review.md](round3-review.md) for the new size-specific i hint, native validation, T-o kerning investigation and rejected half-pixel T trial. `render-round3.rs`, `audit-i-hint.rs` and `verify-round3.py` reproduce the proof and checks.

The user subsequently reported heavy R/T, i still too far right in minimum, and a soft T stem after the small shift. `refine-round4.py` and [round4-review.md](round4-review.md) compare lighter R/T and a farther-left i, with either the shifted T shaft or a shaft aligned to its original native pixel column. Both preserve all guest glyphs; only R/T/i change in retained rendering. The user preferred the aligned T in `generated/Coppet-Round4-Aligned.ttf` (0.018), which is the current review baseline. Run `verify-round4.py CAPTURE_ROOT` after the native captures to reproduce the recorded checks.

The user still found i/l soft. `refine-round5.py` and [round5-review.md](round5-review.md) compare native-column placement of l alone or i/l together, preserving the selected T. These comparisons expose how sharper native strokes can worsen spacing; the user requested the IL treatment with i moved right, implemented below. `verify-round5.py CAPTURE_ROOT` checks the guest masks, metrics and scope; the 9-ppem hints preserve i's dot and l's curved foot.

The latest review baseline is `generated/Coppet-Round6-Right.ttf` (0.021): round-five IL with i moved one whole logical pixel right, preserving native alignment and leaving l/T unchanged. See [round6-review.md](round6-review.md). Rebuild with `refine-round6.py`; `verify-round6.py CAPTURE_ROOT` verifies that only retained i placement changes and that every guest bitmap and advance remains identical. The user said this looked better, then requested the further checks below.

`refine-round7.py` compares R/ampersand clarity and an independently drawn i entry stroke, separately and together (0.022–0.024). See [round7-review.md](round7-review.md) for the raster diagnosis, geometry changes, licensing sources and tradeoffs. `verify-round7.py CAPTURE_ROOT` checks strict native glyph rendering, unchanged advances/metrics and unrelated glyphs, and native/scaled proof/city/dialog captures. The user selected both changes, making `generated/Coppet-Round7-Combined.ttf` (0.024) the current comparison baseline. Wider glyph and production validation remain pending.
