Stacked on #3072; review the three commits after it. Fourth of five PRs making retained outline text cheap: it moves text rows in one pass for every kind of copy, not just offscreen-to-screen.

## How it works today

After #3070 only CopyBits from offscreen memory to the screen copies text rows directly. Every other copy of text goes pixel by pixel through a snapshot of `Arc<DetailCell>` values:

- **CopyBits screen->screen** (a program scrolling a window), **offscreen->offscreen** (composing into a back buffer) and **screen->offscreen** (save-behind) capture a cell per text pixel and store each through `put_detail`; an offscreen destination builds and inserts an `Arc`'d cell per pixel, and plain bytes landing on offscreen text are removed one at a time.
- **ScrollRect** reads its rect byte by byte, snapshots detail for every byte, then writes every pixel of the rect through `copy_saved_pixel` or `write_byte`.
- **Region-clipped 8-bit CopyBits** snapshots whole `row_bytes`-wide source rows with a `detail` query per byte, then copies every pixel of every span through `copy_saved_pixel`, plain pixels included.

## What changes

1. **One span copy for any source and destination** (`copy_detail_spans`, replacing #3070's offscreen-to-screen function). It declines, changing nothing, unless every span lies within one screen row or wholly off the screen, no diagnostic observes individual stores, and no glyph capture, CPU recolouring or text erase is in progress (each gives stores per-byte behaviour). Otherwise it:
   - captures the source spans' cells (screen tiles via the text-cell flags, offscreen chunks via their bitmasks) into one reused buffer, colour table applied once, before writing anything, so overlapping copies are exact in any direction;
   - stores each destination span's bytes in bulk;
   - pastes each destination byte: a copied cell is compared and written in place only if different (screen tile, or offscreen slot via `store_parts`, with no `Arc`); a plain byte gets what `write` would do, with offscreen runs dropped a range at a time.
2. **ScrollRect** on a colour port hands the moved part of each row to the span copy; only the exposed strip is written byte by byte. Without a presentation, moved spans are plain bulk stores. When the span copy declines, the per-pixel scroll runs as before.
3. **Region-clipped CopyBits** plans its spans, then copies them with the span copy: all at once from the saved snapshot when the copy works from one (`copy_saved_spans`, which reads cells from the snapshot, never live memory), or span by span otherwise, matching the loop's read and write order.
4. **Snapshots by range.** `capture_pixel_detail` now uses the range walk (`capture_detail`), which visits only text cells and offscreen cells and finds exactly the cells a `detail` query per byte would.

## Work per operation

| Operation, per text pixel | Before | After |
| --- | --- | --- |
| capture | `Arc` clone + `HashMap` insert | 16 bytes + ink entries appended to a reused buffer |
| store to screen | `put_detail`: cell compare, tile rebuild | compare; in-place tile write if changed |
| store offscreen | build + insert an `Arc`'d cell | in-place slot write if changed |
| plain bytes over offscreen text | a remove per byte | one range removal per run |
| snapshot of n bytes | a `detail` query per byte | a flag test per screen byte; offscreen cells only |

## Measurements

Per-operation benchmark, 640x480 8-bit screen at 4x detail, a third of pixels text (`text_operation_costs`, master `0c377eed` vs the whole stack):

| Operation | master | stack |
| --- | --- | --- |
| CopyBits screen->screen, scroll up / down / left | 645 / 721 / 639 ms | 81 / 82 / 83 ms |
| CopyBits offscreen->screen via a table, text moved one row | 447 ms | 53 ms |
| CopyBits screen->offscreen, 300x200 save-behind | 59 ms | 8.7 ms |
| CopyBits offscreen->offscreen | 78 ms | 46 ms |

- **SimCity 2000:** identical; host instructions -6.17% vs master with this PR (on current master `519dd13f`; about -6% from this PR), almost all from the region-clipped path and range snapshots, which SimCity 2000's clipped CopyBits uses constantly. Full suite passes on this PR's tree.
- **EV Override:** identical at 2,400, 3,000 and 9,000 ticks; crawl unchanged within noise (its copy was already direct after #3070).
- **Tests:** differential tests against the former per-pixel sequences: six copy cases (offscreen->screen; screen up, down and left with overlap; offscreen->offscreen with overlap; screen->offscreen) with and without prior text and a colour table; ScrollRect for vertical, horizontal, diagonal and oversized deltas; the existing region-path test, including a live source changed after the snapshot. Full suite passes.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)