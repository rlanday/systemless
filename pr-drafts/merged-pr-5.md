Stacked on #3073; review the three commits after it. Last of five PRs making retained outline text cheap: the bulk memory paths that still touched text one byte at a time.

## How it works today

- **Fills.** `write_bytes`, `fill_bytes` and `fill_zeros` over a range the presentation observes (any screen row, or offscreen memory holding text) fall back to one `write_byte` per byte, so EraseRect, FillRect or PaintRect over text pays a presentation update (and, over text, a `clear_text_cell`) per pixel.
- **Menus.** A drop-down's save-behind reads the screen a byte at a time; its restore calls `restore_saved_pixels` once per byte, so even an unchanged row is proved byte by byte and a changed one pays a store and a detail comparison per byte.
- **BlockMove.** `copy_ram_bytes` and `copy_mapped_ram_bytes` (BlockMove, PICT, indexed blitters) copy any observed range through `copy_saved_pixel` one byte at a time, plain bytes included.

## What changes

- **Fills** apply a row span in one pass when the presentation can: offscreen spans drop their cells a range at a time, plain screen rows update their values together (`sync_plain_screen_row`), and screen rows over text clear their cells in one walk (`sync_screen_row_over_text`). These are the exact equivalents CopyBits already uses for plain spans.
- **Menus** save each row with one read and restore whole rows, which `restore_saved_pixels` proves unchanged in one comparison. Inside any restore, a run of bytes without text becomes one bulk store; bytes with text keep their per-byte restore.
- **BlockMove** over a range within one screen row or wholly offscreen uses #3073's span copy; other ranges keep the byte copy.

| Operation on n bytes | Before | After |
| --- | --- | --- |
| fill a plain screen row | n `write_byte` calls | one RAM fill + one row sync |
| fill a screen row over text | n `write_byte` + `clear_text_cell` | one RAM fill + one walk clearing text cells |
| fill offscreen over text | n `write_byte` + removes | one RAM fill + one range removal |
| restore an unchanged menu row | n proofs | one proof |
| BlockMove within a row or offscreen | n `copy_saved_pixel` | one span copy |

## Measurements

Per-operation benchmark (as in #3073), master `0c377eed` vs the whole stack:

| Operation | master | stack |
| --- | --- | --- |
| EraseRect over screen text (a fill per row) | 151 ms | 17 ms |
| EraseRect over offscreen text | 38 ms | 8.1 ms |
| restore a 200x300 menu save-behind over text | 39 ms | 14 ms |
| BlockMove offscreen rows with text | 47 ms | 35 ms |

- **SimCity 2000:** identical; host instructions -7.71% vs master with this PR, -1.54% of it from this PR (mostly the fills).
- **EV Override:** identical at 2,400, 3,000 and 9,000 ticks.
- **Tests:** `bulk_stores_over_text_match_byte_stores`, `span_restores_match_byte_restores` and `observed_block_moves_match_byte_copies` compare against the byte-at-a-time behaviour on screen rows with and without text, spans past a row's width, and offscreen text. Full suite passes.

## Still per pixel after this stack

- CopyBits transfer modes other than srcCopy (srcOr, transparent, ...) over text build a fresh cell per text pixel.
- PowerPC CopyBits and packed inline ink are follow-ups already written and in validation.
- Drawing text onto the screen is still one presentation call per glyph pixel.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)