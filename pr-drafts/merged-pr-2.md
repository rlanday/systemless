Stacked on #3070; review the two commits after it. Second of five PRs making retained outline text cheap.

## How it works today

Antialiased ink (a foreground index, an alpha and the background it was drawn over, per partially covered sample) is stored in two places:

- **Screen:** one screen-wide `HashMap<usize, Ink>` keyed by `cell * 16 + sample`, mirrored by `ink_mask: Vec<u16>`. Every changed text cell of every copy removes and inserts each of its ink samples in that map: two hash operations per ink sample, plus rehashing as text scrolls.
- **Offscreen (after #3070):** each 256-byte chunk keeps all its ink in one list sorted by slot and sample. Drawing an antialiased sample binary-searches the chunk's whole list and inserts in the middle, moving every later entry: O(ink in the chunk) per sample, up to 4,096 entries.

## What changes

- **Screen ink lives with its tile.** Each tile slot in the sample pool owns its cell's ink as a short list sorted by sample, emptied (capacity kept) when the tile is released. `ink_mask` still mirrors it. A palette change recolours ink by walking the tile slots' lists, so it costs the text on screen, not the screen's size.
- **Offscreen ink lives with its slot**, the same way: clearing a slot empties its list.

## Work per operation

| Operation | Before | After |
| --- | --- | --- |
| Replace a screen cell's ink (i samples) | 2i hash operations on a map of all screen ink | clear + push i entries in the tile's own list |
| Compare a screen cell's ink | i hash lookups | one slice comparison |
| Add or remove one offscreen ink sample | binary search + memmove over the chunk's list | scan of at most 16 entries |
| Palette change | walk the ink map | walk the tile slots' lists |

A first version walked every screen cell's slot on a palette change, which SimCity 2000's colour cycling turned into +1.02% host instructions; walking the slots' own lists fixed it.

## Validation

- **EV Override:** identical at 2,400, 3,000 and 9,000 ticks. Crawl-window CPU 4.9 s -> 3.6-3.8 s (about -25% on #3070); whole 9,000-tick run 30.5 s -> 27.4 s.
- **SimCity 2000:** identical; host instructions -0.14% vs master (-0.08% over #3070).
- **Tests:** the ink-mask invariant is checked by the existing detail tests and a new restore test; full suite passes.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)