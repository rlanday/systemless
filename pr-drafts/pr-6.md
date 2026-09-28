Follow-up to #3070-#3074. Stores antialiasing ink as a small fixed block inline with each text cell, and moves those blocks through copies whole.

## How it works today

Each retained text cell has 16 subpixel indices, and each partly covered sample also has ink: a foreground index, an alpha and the background it was drawn over. After #3071 each screen tile slot and each offscreen slot owns its ink as its own small heap-allocated list of `(sample, Ink)`, and an `Ink`'s background is an `IndexedColor` that may own boxes. So:

- **every copy of a text cell chases pointers into cold memory:** once to read the source's ink list, once to drop the destination's old list. Profiling a one-row scroll of a screen of text (the benchmark below) put a quarter of its time on that one cache-missing load;
- **capture unpacks and paste repacks:** the row copy (#3073) clones each sample's `Ink`, maps it through the colour table, then compares and stores it at the destination.

## What changes

1. **Packed ink.** Ink over a single background colour, which is all ink in practice (an instrumented EV Override run saw 3.2 million ink samples, none blended), packs into four bytes: foreground, alpha, background and a flag bit. A cell's ink is a fixed block (`CellInk`: a presence mask, a blended-sample mask and 16 packed values) held in a flat array beside the screen tiles, with no heap list per cell. Ink over a blended background (text drawn over text of another colour, or transfer modes) sets the flag and keeps its full `Ink` in a side table keyed by slot and sample.
2. **Blocks through copies.** A copied cell carries its packed block, mapped through the colour table byte by byte; paste compares and assigns the block and colours its samples straight from it. Cells with blended ink keep the list path.
3. **Sparse offscreen ink.** An offscreen chunk (256 addresses) holds ink blocks only for its inked slots, found through a one-byte index per slot and reused when cleared. (Packing alone gave every chunk a 17 KB block array the first time any slot had ink, which made copies into fresh buffers slower.)

## Work per operation

| Per text cell | Before | After |
| --- | --- | --- |
| read the source's ink in a copy | follow a heap pointer; clone each `Ink` | read a 68-byte block in a flat array |
| map through a colour table | clone and map each `Ink` | two table lookups per inked sample, in place |
| compare with the destination | per-sample `Ink` equality | block comparison |
| replace the destination's ink | drop a heap list, push each `Ink` | assign the block |
| offscreen memory for ink | a heap list per inked slot | 68 bytes per inked slot, no per-slot allocation |

## Measurements

Per-operation benchmark (`text_operation_costs`: 640x480 8-bit screen at 4x detail, a third of pixels text), current master (with #3070-#3074) vs this PR:

TBD

- **EV Override** (Windows, fixed 9,000-tick replay): TBD.
- **SimCity 2000** (Linux fixed-work replay, 2,500 frames): TBD.
- **Tests:** a unit test round-trips packed and side-table ink; the six-way row-copy differential test now includes a cell drawn over by text of another colour (blended ink, list path) alongside packed cells; full suite TBD.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)
