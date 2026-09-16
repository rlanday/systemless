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

The current candidate is `generated/Coppet-Refined.ttf`, version 0.010. Rebuild it with `python refine-spacing.py` followed by `python refine-stems.py` after the t revision. See [spacing-weight.md](spacing-weight.md) for the diagnosis, optical changes, native-size placement checks, and remaining review items. Intermediate fonts remain comparison inputs; none is a production default.

The user called the first spacing/stem revision a big improvement, while reporting a narrow/light c and blurry i/l at native size. Version 0.010 addresses those reports and still needs visual review. A previous fractional-position trial produced empty one-bit i/l masks; it was rejected during compatibility validation. All non-space ASCII masks must contain ink before a candidate is considered usable.

`validation-name.json` verifies that adopting the final name Coppet changed no outline, metric, mapping or hinting tables in the six comparison font files. The existing native rendering checks therefore apply to the renamed fonts.
