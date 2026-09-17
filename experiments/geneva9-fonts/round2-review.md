# Coppet: second optical review

The user accepted the improved Demand spacing and ampersand balance, but reported excess space after c and before l, an overly long r shoulder, heavy t/l/r stems, unequal i/j dots, a heavy s, and the T–o gap in Tool. This revision keeps the Inter-derived outline approach, with shared parameters in `refine-round2.py`. A possible METAFONT-based redesign is deferred at the user's request.

The scope remains 95 printable ASCII glyphs at logical size 9. Version 0.010 is retained as the before case. Two new candidates share every change except lowercase l:

- `Coppet-Round2-Plain.ttf`, version 0.011: a thinner straight l moved left.
- `Coppet-Round2-Foot.ttf`, version 0.012: Inter's existing `l.ss02` curved-foot alternate, fitted to the same advance and narrow stem parameter.

Neither l variant is a final selection. Inter's OFL attribution is retained, and no original Apple artwork was used to construct the candidates.

## Shared parameters and optical changes

At UPEM 900 and logical size 9, 100 font units equal one logical pixel. These are outline dimensions, not final hinted pixel bounds.

| Glyph | Change | Purpose / tradeoff |
| --- | --- | --- |
| c | Keep x ≤ 80 unchanged; extend right side from 400 to 450 | Reduce c–i blank space by 0.5 without thickening the left stem or moving the accepted i off its clear pixel position |
| t | Shaft 80 → 72, centered at x=127 | Match the accepted i/m stem weight more closely; preserve accepted t height and crossbar |
| l, plain | Stem 80 → 72; left edge 100 → 25 | Reduce space before l by 0.75; necessarily leaves more space after the straight stroke |
| l, alternate | Fit Inter l.ss02 with a 72-unit stem and left edge 25 | Curved foot fills more of l's three-pixel cell; compare this shape separately |
| r | Stem 80 → 72; left edge 20; total width 400 → 340 | Shorten the long shoulder; leaves additional space on its right, so check river/ruler |
| j | Move shaft center 137 → 150; copy i's complete dot contour and position | Equal dots centered on the stems; hook's left extent retained |
| s | Inter weight 400 → 360, fitted to the same 400 × 500 outer box | Modestly reduce curve weight without changing its advance or outline bounds |

The shared narrow-stem parameter is 72, close to i's approximately 71 and m's 73–74. This is not a rule that every curved or diagonal cross-section must have the same width. Curves need optical balancing. The accepted Demand and ampersand outlines are byte-identical to version 0.010; h/n/m are also unchanged for comparison.

## Tool is a remaining spacing decision

Inspection of the captured SC2K status-panel drawing code and GrafPort shows **Geneva 9 bold**, not size 12. The captured port at 0x435fe8 has txFont=3, txSize=9, txMode=1 and spExtra=0. The header/body sequence, with unrelated color and icon work omitted, is equivalent to:

```c
// Font setup selects Geneva 9.
TextFace(bold);                     // 0x23d68e
MoveTo(4, 12);                     // 0x23d6ae
DrawString("Centering Tool");       // 0x23d6b2
TextFace(normal);                   // 0x23d724, ordinary body-text path
MoveTo(4, 22);                     // 0x23d72c
DrawString("Citizens Demand Road&Rail"); // 0x23d730
```

No TextFont or TextSize call separates the two DrawString calls in this path. `render-round2.rs` includes a matching Geneva 9 bold diagnostic row. An initial local proof used size 12 for that row; it was corrected before this review. The full-city captures execute the game's own drawing code.

The current T advance is 6 logical pixels, with ink bounds 0–5; o's advance is 5, with bounds 0–4. Systemless's existing bold style adds one to each advance and smears the shape one pixel right. The T arm sits above the o, so the visible opening beside its narrower stem is larger than the one-pixel bounding-box gap suggests. This is an optical explanation for the perceived gap, not proof that all text-spacing behavior is correct.

The T–o pair is unchanged in both new candidates. A shorter advance or newly applied pair kerning would change guest string measurements/pen positions; moving T's artwork would also affect its other neighbors. Compare the plain/bold samples and original Geneva before selecting a shape adjustment or proposing a separate spacing behavior change. Do not imply that this report fixes Tool.

[Inside Macintosh: Font Measurements](https://dev.os9.ca/techpubs/mac/Text/Text-186.html) distinguishes ink bounds and side bearings from the origin-to-origin advance, and describes pair kerning separately. These candidates keep the existing advance policy; they add no kerning tables or renderer tracking correction.

## Native Windows validation

All cases use the same frozen Systemless comparison library, based on master 724e18f including #1997, with Skrifa 0.43.2 and zeno. `audit-detail.rs` checks 9-pixel monochrome guest masks and 36-pixel grayscale retained masks. `verify-round2.py` checks:

- All 95 ASCII advances, the baseline GetFontInfo metrics, and line metrics remain unchanged.
- Only c/j/l/r/s/t outlines change; the other 89 glyphs have identical native raster output and placement in both targets.
- Every one of the 94 non-space glyphs retains ink in both targets. The complete accepted guest i bitmap is unchanged.
- The i/j dot pixels, including their relative position, are identical in both targets.
- Only c/l/r guest binary masks change. All six edited letters change in the retained grayscale target.
- The two alternatives differ only in l, in both outline data and native raster output.

The new proof includes human, humane, hammer and separate h/n/m combinations. It also includes city/cities/civic, kl/lk/ll/li/il, ij/ji, river/ruler/street and s/e/o comparisons. It is rendered at 100%, 138% and 4× through Systemless, rather than using browser font rasterization. Full city and New City captures use a fixed clock and identical input replay at 800 × 600 and 1104 × 828. Hashes are recorded in `validation-round2.json`.

## Remaining work

Visual review is pending. Check the l tradeoff in both directions, whether shortening r creates an apparent split in river, whether s is now too light, and whether h's taller arch needs adjustment. Native-size readability takes priority over making enlarged contours mechanically uniform.

Tool and a systematic capital/figure/punctuation pass remain open. Before a production PR, validate guest-font precedence, controls, selections/inversions, caret erasure, clipping, and native/scaled performance against the then-current master. Equal advances and nonempty masks do not establish all of those behaviors.
