# Coppet: aligned i moved one pixel right

The user requested “Align i and l” with i moved right while retaining alignment at 9 pixels. Version 0.021, `Coppet-Round6-Right.ttf`, implements a **whole logical pixel** move into the adjacent native column. This interpretation was stated before generating the comparison. It starts from round-five IL; aligned l and the selected aligned T remain unchanged.

i's outline moves +100 units at UPEM 900, so its stem now spans x=1.14…1.85 at logical size 9, instead of x=0.14…0.85. Its advance remains 3. The dot moves with the shaft; neither shape nor weight changes. This adds one logical pixel before i and removes one after it, while preserving the ending pen position and total word width. Review minimum, Rail, Citizens and il/li in the updated native/138% proof.

The previous extra 9-ppem i hint is removed: the outline itself now occupies the accepted guest position, so keeping the old +1-pixel correction would incorrectly shift it twice. l's +20/64-pixel guest-size hint remains to preserve its curved foot.

`refine-round6.py` reproduces the candidate. `verify-round6.py` checks the same native Windows proof/replay and strict glyph audits:

- i is the only changed outline, and every contour point is translated exactly +100 units in x with y unchanged.
- All 95 ASCII advances, baseline font metrics, and guest bitmap pixels/extents/placements are identical to round-five IL.
- All 95 retained raster mask contents are identical. Only i's retained placement changes: four pixels right in the 4× raster, exactly one logical pixel.
- Aligned l/T and all other letters are unchanged. Strict native hint execution passes.

Font and screenshot hashes are recorded in `validation-round6.json`. The proof and full-city/New City views use the same fixed-clock replay at 100% and 138%. The user said this looked better, then asked about an i entry stroke and R/ampersand clarity; those trials are documented in [round7-review.md](round7-review.md). GUI compatibility, broader character coverage and native/scaled performance checks remain necessary before production use.
