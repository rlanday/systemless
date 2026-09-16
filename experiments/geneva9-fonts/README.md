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

The comparison needs visual selection before further refinement or a PR. Small text must preserve the accepted weight, and both native and fractional-size city views must be reviewed. Performance measurements for any production proposal must include both sizes on the same base and report power conditions.
