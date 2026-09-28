Stacked on #PR7; review the two commits after it. Makes painting outline text into offscreen buffers cheaper, the largest remaining cost in EV Override's scrolling text.

## How it works today

For each guest pixel of a glyph's clipped rectangle, the offscreen painter walks the pixel's 16 samples one at a time. For each sample it recomputes the glyph coordinates and bounds, reads the coverage, and for a covered sample calls into the cell: `set_index` and `remove_ink` for full coverage, or `update_ink` for partial coverage, which looks up the sample's ink, unpacks it into an `Ink`, updates it and packs it back. Each of those calls also forgets the cell's cached snapshot `Arc`.

## What changes

1. **One pass per cell.** The painter reads the cell's coverage from the glyph one row slice per sample row, then hands the whole cell to one `paint_glyph` call: fully covered samples take the foreground in one pass, ink is looked up once, and the snapshot is forgotten once.
2. **Blank cells as one block.** Text is usually drawn onto an erased buffer, where a painted cell has no ink yet. Its ink is then fully determined: each partly covered sample gets the foreground at its coverage over the sample's current index. `paint_glyph` builds that packed block directly and assigns it. Cells that already have ink keep the general path, which handles a different foreground (blending) and repeated coverage (maximum alpha).

| Per glyph pixel | Before | After |
| --- | --- | --- |
| coordinates and bounds | per sample | per sample row |
| calls into the cell | one to three per covered sample | one |
| partly covered sample on a blank cell | look up, unpack, update, repack | four bytes written into a block |

## Measurements

Drawing 640x64 pixels of text into an offscreen buffer (the benchmark from #PR6, glyph setup outside the timed region):

TBD

- **EV Override:** TBD.
- **SimCity 2000:** TBD.
- **Tests:** `glyph_cell_paint_matches_per_sample_painting` replays 20,000 random paints (full, partial and zero coverage; three foregrounds, so blending too; 4, 9 and 16 samples) against the former per-sample painting, from blank cells and cells with ink; full suite TBD.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)
