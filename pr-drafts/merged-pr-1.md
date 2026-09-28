First of five stacked PRs that make retained outline text (#1524) cheap to draw, erase and move. This one changes how offscreen text detail is stored and copies offscreen text rows to the screen directly. EV Override's opening crawl is the motivating case: it draws about ten lines of text into an offscreen GWorld every frame and CopyBits it to the screen, and on master that costs close to a core.

## How it works today

Each guest pixel that holds outline text has a retained cell: 16 subpixel palette indices (4x4) plus antialiasing ink for partially covered samples. Offscreen cells (GWorlds, save-behind buffers) live in a `BTreeMap<u32, Arc<DetailCell>>`, one entry per pixel, where a `DetailCell` owns a `Vec<u8>` of indices and a `HashMap<usize, Ink>`. So every offscreen text pixel is a B-tree entry plus two or three heap allocations, and:

- drawing a glyph sample does a B-tree lookup, then a copy-on-write clone of the `Arc`'d cell (allocations) to change one sample;
- a store over offscreen text (an erase) removes and frees one cell per byte, O(n log N);
- CopyBits to the screen captures a `SavedPixels` snapshot (a `HashMap` from offset to a cloned `Arc` per text pixel), then writes each destination pixel through `copy_saved_pixel_through` -> `store_detail_pixel` -> `put_detail`: a colour-table clone of the cell (cached per cell), a comparison and a rebuild of the screen tile.

## What changes

1. **Address chunks.** `OffscreenDetail` stores cells in 256-byte address chunks (`BTreeMap<u32, Box<Chunk>>`). A chunk holds each slot's value, sample count and 16 indices inline, a presence bitmask, and the ink. An `Arc<DetailCell>` is built only when a snapshot asks for a cell and cached until that cell changes, so unchanged text in snapshots still shares one cell.
2. **Bulk offscreen stores.** A bulk store (`write_bytes`) wholly offscreen used to fall back to one `write_byte` per byte once the span held text. It now drops the span's cells a range at a time (out of line, so `write_bytes` keeps its shape).
3. **Offscreen-to-screen row copy.** When CopyBits copies rows from offscreen memory to screen rows (srcCopy, unscaled, rectangular clip, 8/16/32-bit), each destination row is written from the source chunks directly: per byte, either a plain store (exactly what `write` would do) or the source cell mapped through the colour table, compared with the destination and written in place only if different. #3073 generalises this to any source and destination.

## Work per operation

| Operation | Before | After |
| --- | --- | --- |
| Draw one offscreen glyph sample | B-tree lookup, O(log N), plus Arc/Vec/HashMap clone-on-write | chunk lookup, O(log N/256), plus an in-place array write; no allocation |
| Erase n bytes over offscreen text | n B-tree removes (O(n log N)) and n frees | one chunk lookup per 256 bytes and a bitmask clear per 64 slots |
| Snapshot a span | range walk cloning an Arc per cell | bitmask walk; an Arc built once per unchanged cell |
| CopyBits offscreen->screen, per text pixel | HashMap insert + Arc clone to capture; cell clone per table; put_detail | 16 table lookups into a stack array; compare; in-place tile write if changed |
| Memory per offscreen text pixel | three allocations (~150-250 B) | 18 bytes inline, plus ink |

## Validation

Measured on master `0c377eed`; revalidated on current master `519dd13f` (below).

- **EV Override** (Windows, fixed 9,000-tick replay): final state, image and audio identical to master at ticks 2,400, 3,000 and 9,000. CPU for the crawl window (ticks 2,400 to 3,000): master 9.1-9.7 s, this PR 4.8-5.2 s (about -48%).
- **SimCity 2000** (Linux fixed-work replay): all 2,500 frame records and the RAM, register, PNG and compact checkpoints identical; host instructions -0.06% (all six pairs).
- **Tests:** a model test replays 20,000 random operations against a `BTreeMap` reference; a differential test compares the row copy with the per-pixel copy (plain, other text and identical text at the destination, with and without a colour table). Full library suite passes.
- **Whole stack on current master `519dd13f`:** full suite passes (5,860); SimCity 2000 identical with host instructions -7.71%; EV Override identical at every checkpoint, crawl window 8.8-8.9 s -> 3.9-4.1 s (-55%), whole 9,000-tick run 34.0 s -> 28.6 s.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)