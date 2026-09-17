# Coppet: native clarity of i and l

The user preferred round four's aligned T stem but still found i and l soft. These trials preserve that T and every other letter. They compare different placement of the existing narrow strokes; their outline shape and weight are unchanged.

The retained host image is rasterized at 4× logical size and resized for the window. At 100%, round four's i stem occupies x=0.64…1.35 and l's stem x=0.45…1.17 within their respective advance cells. Both spread coverage across adjacent native columns. The following placements concentrate the strokes within column 0:

| Trial | i | l |
| --- | --- | --- |
| Before: round-four aligned T | Existing placement | Existing placement |
| L (0.019) | Unchanged | Move 0.31 logical pixel left: stem x=0.14…0.86 |
| IL (0.020) | Move 0.5 logical pixel left: stem x=0.14…0.85 | Same placement as L |

The i dot moves with its shaft, and l's selected curved-foot shape moves as a whole. Both advances remain 3. The two new alternatives differ only in i.

## Spacing tradeoff

Moving i left changes minimum's approximate contour gaps from m-i=1.64 / i-n=1.65 to m-i=1.14 / i-n=2.15. This may sharpen the native stroke while reopening uneven spacing on the other side. The comparison must not present sharper stems as an unconditional improvement.

Moving l left reduces the gap before it and increases the space after it. Review Rail, Citizens, il/li, little and minimum at native size, 138%, and enlarged. Native-column placement also cannot promise alignment at every fractional window size. If neither choice has acceptable spacing and clarity, retain the alternatives as diagnostic evidence rather than silently changing advances or adding contrast.

## Protecting guest bitmaps

The shifted l originally lost the visible foot in its 9-pixel monochrome bitmap: the bottom pixel moved into the same column as the stem. The generator now appends a 9-ppem-only x hint moving its real contour points +20/64 pixel, restoring the accepted guest foot. The difference between 20/64 and the geometric 0.31 is below a TrueType 1/64-pixel step; exact guest raster equality is checked rather than assumed.

i retains the size-specific hint introduced in the prior rounds. Its correction is +32/64 in L and +64/64 in IL to restore the accepted guest position. Neither glyph program moves phantom points, changes advances, or alters the 36-ppem retained outline placement. These are experimental font instructions, not new Systemless rendering branches.

## Native checks

`refine-round5.py` reproduces both fonts. The same `render-round3.rs` proof/replay and strict `audit-pedantic.rs` helper provide native Windows captures. `verify-round5.py` records:

- All 95 ASCII advances and baseline metrics unchanged.
- All 95 guest glyph bitmaps, extents and placements identical to round four, including the full i dot/stem and l foot.
- Only l's retained raster changes in L; only i/l change in IL. All other outlines and rasters, including the accepted T, are identical.
- Both variants differ only in the retained i. Every non-space glyph has ink, and strict native hint execution succeeds.
- Full-city/New City captures use the same fixed clock and input replay at 100% and 138%.

The preceding round-four checks separately establish that the extra size-specific instruction pattern is inactive at 8/10/36 ppem. Round five's strict all-glyph audits check the changed amounts at the actual 9/36 targets. Font and screenshot hashes are in `validation-round5.json`.

The user requested IL with i pushed right while keeping native alignment. [Round six](round6-review.md) implements that follow-up. These remain 9-point ASCII studies; broader font coverage, GUI compatibility and native/scaled performance are still required before a production proposal.
