# Coppet: R/T weight, minimum spacing and T clarity

After the third comparison, the user reported that R and T were too heavy, i was still too far right in minimum, and the larger T shift disrupted STREET. The small T shift was a reasonable spacing compromise but made the vertical stem softer. The curved-foot l shape remains selected.

`refine-round4.py` starts from the version 0.014 review candidate and changes only R, T and i. The previous P/y/j and l outlines are retained; this is not a claim that every preceding change has been accepted.

| Feature | New trial |
| --- | --- |
| R | Inter weight 360 instead of 400, fitted to the same 500 × 700 outer bounds; lightens bowl and leg as well as the stem |
| T shaft | 80 units wide instead of 85 |
| T crossbar | 72 units high instead of 79; cap height 700 and bar bounds x=25…525 retained |
| i | Another 25 units left, totaling 50 units left of version 0.012 |
| i guest hint | At 9 ppem only, move real contour points +32/64 pixel to preserve the accepted guest bitmap; advances/phantom points are untouched |

There are two versions, differing only in T:

- **Shifted (0.017):** T's shaft and crossbar both remain centered at x=275, the previously preferred quarter-pixel whole-letter shift.
- **Aligned (0.018):** the shaft returns to x=250 while the crossbar remains centered at x=275. The 80-unit shaft occupies x=210…290, within native logical pixel column 2. Its top bar is slightly asymmetric around the shaft. This tests a shape compromise, not a new renderer filter or added weight.

At logical size 9, 100 font units equal one pixel. The shifted shaft spans x=235…315, dividing its coverage across two native columns. The aligned option concentrates it within one column. This may improve native clarity but gives back some of the space beside T's stem in Tool; the top bar still retains the small rightward movement. Compare both normal-size clarity and enlarged proportions, along with AT/TT/STREET. The larger whole-letter shift is excluded from this round following the user's feedback.

i's additional movement brings the outline gap from m to i to about 1.64 logical pixels and from i to n to about 1.65 (previously 1.89 and 1.40). That balances the measured ink spacing, but native-size readability remains a visual question: its fractional placement can split a thin grayscale stroke across columns. The retained host raster is still generated at 4× logical size and reduced for native presentation; the guest-size hint alone cannot eliminate that display tradeoff. Rail is included because moving i also increases i-l spacing.

## Validation

`verify-round4.py` checks the strict native Windows Skrifa/zeno glyph audits, the same fixed-clock SC2K city/New City replay at 100% and 138%, and the seven-case i hint audit from `audit-i-hint.rs`. `render-round3.rs` supplies the same proof sheet; only the selected font changes.

- All 95 ASCII guest bitmap pixels, extents, placements, advances and baseline font metrics are identical to version 0.014. This includes i's complete dot/stem and T's full shaft.
- Only R/T/i outlines and retained grayscale rasters change; the other 92 characters are identical in both targets.
- The two alternatives differ only in T's outline and retained raster.
- All non-space glyphs contain ink. Strict hint execution succeeds with hinting enabled.
- The added i hint restores the accepted guest result at 9 ppem and has no effect at 8, 10 or 36 ppem compared with the otherwise identical autohinted font lacking the extra instruction sequence.

`validation-round4.json` records font and screenshot hashes. The user preferred the **aligned T stem**, but reported that i and l still look soft. Their placement is the next refinement. GUI interactions, clipping/inversion, guest-font precedence and native/scaled performance remain pending before production use. Neither candidate is a default font replacement.
