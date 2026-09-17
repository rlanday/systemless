# Coppet: Rail, minimum, P/y/j weight, and Tool

The user selected the curved-foot l, then reported that i/l were too close in Rail, P/y/j looked too heavy, minimum appeared split as “m in imum,” and Tool still looked like “T ool.” The chosen l shape is retained; its placement remains under review. These candidates build on version 0.012 without changing any character advance or Systemless spacing code.

## Outline changes

`refine-round3.py` generates a common weight/spacing revision and two separate T placement trials. At logical size 9, 100 font units equal one logical pixel.

| Glyph | Change | Expected effect and tradeoff |
| --- | --- | --- |
| P | Straight stem 93 → 80 units; redistribute the remaining bowl width while keeping outer bounds 0–500 | Reduce the oversized vertical stroke without narrowing the character |
| y | Refit Inter weight 360 instead of 400 to the existing 500 × 700 bounds | Reduce diagonal weight; advance, x-height and descender bounds remain unchanged |
| j | Shaft 80 → 72, centered at 150; blend into the existing hook | Match the narrower i/t/l/r strokes; retain the dot's outline |
| i | Translate outline 25 units left | Reduce m-i blank space and increase i-n space; fractional placement can reduce native-size darkness |
| l | Translate the selected curved-foot outline 20 units right | Open the i-l gap and reduce unused space after the foot; the shape is unchanged |
| T, small trial | Translate outline 25 units right | Modestly close the gap in T-o, at the cost of more space before T |
| T, larger trial | Translate outline 100 units right | Stronger correction after T, but greater risk of awkward A-T/T-T spacing |

The m/n artwork is unchanged, as are the accepted Demand and ampersand. At the straight stem, the m-i gap changes from approximately 2.14 to 1.89 logical pixels, while i-n changes from 1.15 to 1.40. The i-l gap increases by 0.45. These describe contour coordinates, not guaranteed visible pixel gaps after filtering.

The candidate files are:

- `Coppet-Round3-Weight.ttf` (0.013): P/y/j weight and i/l placement; T unchanged.
- `Coppet-Round3-T25.ttf` (0.014): common changes plus the small T shift.
- `Coppet-Round3-T100.ttf` (0.015): common changes plus the larger T shift.
- `Coppet-Round3-T50-AuditOnly.ttf` (0.016): **rejected diagnostic**, not a review candidate. Its half-pixel T shift erases the one-bit stem.

The user selected the **small T shift**, while reporting that the other weight/spacing changes still need adjustment. Version 0.014 is the current review candidate, not a fully accepted design. Its selected features are the curved-foot l shape and quarter-pixel T translation; specific remaining spacing/weight defects are being clarified. The comparison also includes version 0.012 and a local original-Geneva reference.

## Why i needs a size-specific hint

The first fractional i placement retained its shaft but lost the dot in the 9-pixel monochrome guest mask. Merely testing that each glyph has some ink would have missed this. The dot crossed the coverage threshold differently from the rectangular shaft.

After ttfautohint runs, the generator appends a small instruction sequence to i's glyph program. At exactly 9 pixels per em it moves all real contour points +16/64 pixel along x, restoring the accepted guest placement. It does not move phantom points or change advances. At the 36-pixel retained size, the condition is false and the outline keeps its new quarter-logical-pixel placement. No renderer branch or glyph-specific engine code is added.

Equivalent instruction logic:

```text
set projection/freedom vectors to x
if pixels_per_em == 9:
    select glyph zone for moved points
    shift every real contour point +16/64 pixel along x
```

The [OpenType TrueType instruction specification](https://learn.microsoft.com/en-us/typography/opentype/spec/tt_instructions#shift-point-by-a-pixel-amount) defines SHPIX's displacement in 1/64-pixel units. `audit-i-hint.rs` uses Skrifa's strict interpreter mode and compares the final font with an otherwise identical freshly autohinted font lacking this addition. Hinting is enabled; there are no interpreter errors. At 8, 10 and 36 pixels, output and placement are identical with/without the added hint. At 9 pixels the monochrome dot is restored. The complete resulting guest i bitmap and pen-relative placement match version 0.012.

This is a narrowly scoped experimental hint. The display outline's fractional placement can still look softer at 100%, because the retained 36-pixel coverage is reduced for native-size presentation. That visual tradeoff must be reviewed. The hint does not solve general horizontal grid fitting for the rest of the typeface or arbitrary sizes.

## T-o investigation

The local original Geneva 9 has T advance 6 / bitmap width 5 / left bearing 0, and o advance 5 / bitmap width 4 / left bearing 0: these match Coppet's current advance and outer-box policy. Its 96-byte FOND 3 resource has `ffKernOff=0` at byte offset 20. [Inside Macintosh's FOND description](https://dev.os9.ca/techpubs/mac/Text/Text-269.html) specifies that a zero table offset means the optional table is absent. Thus this System 6 reference supplies no T-o kerning pair to restore. This finding is specific to the supplied reference, not every later Geneva release.

Inter's source font, instantiated at optical size 14 / weight 400, does contain a T-o GPOS pair adjustment of -160 units at UPEM 2048. That is approximately -0.703 pixels at an ordinary 9-pixel em. It is evidence that this source design normally benefits from pair kerning, not a value to copy into independently fitted Coppet glyphs. Coppet's compatibility advances and drawing path do not apply that pair adjustment.

The two displayed trials move T's artwork within its six-pixel advance cell. Neither changes the six-pixel advance, the string's ending pen position, or applies context-dependent kerning. Moving T also changes spacing on its left, so the proof includes Tool/Tools/Total/Town/Time/Today/Toad and AT/TA/TT/LT/ST/STREET/STOP/CITY, in addition to the game's Geneva 9 bold header style.

The half-pixel trial was rejected: its narrow stem straddles two columns and neither reaches the guest coverage threshold. Only the crossbar remains. The quarter-pixel and full-pixel trials retain the stem. The quarter-pixel trial adds a transparent column to the guest mask's bounding box but does not change any guest ink position; the full-pixel trial moves T's guest ink right by one. These differences still require GUI clipping/inversion checks before production use.

## Native validation and review

`verify-round3.py` records these checks in `validation-round3.json`:

- All 95 ASCII advances and baseline font metrics remain unchanged.
- Only P/i/j/l/y outlines change in the common revision; the T trials additionally change T. All other glyphs have identical outlines and native raster output.
- All 94 non-space glyphs retain guest and retained ink; i's complete guest dot/stem and each viable T stem are specifically checked.
- i/j dot shapes match in both targets, allowing their intentionally different bearings.
- The common revision has identical guest glyph masks and placement for all 95 ASCII characters. Its changes appear in retained grayscale rendering.
- The quarter-pixel T trial preserves guest ink positions; only its transparent bitmap bound changes. The larger T trial changes only T's guest ink position.
- The rejected half-pixel trial's missing stem and the unpatched i trial's missing dot are explicitly reproduced by the audit.

Native and 138% full-city/New City screenshots use the same fixed-clock SC2K replay and comparison library as the preceding round. The proof sheet also includes minimum/minimal/mineral, Rail/ail/il/li, P/H/R/B, y/v/x and j/i. Visual preference is pending. Guest-font precedence, GUI interactions, selection/inversion, clipping and native/scaled performance remain necessary before a production proposal.
