# Text operations and their retained-detail paths (survey 2026-09-27, tree systemless-rows2 @ f5ada091)

Fast (row-level) today: only CopyBits offscreen->screen, srcCopy, unscaled, rect clip, depth 8/16/32, 68k (RowCopy::execute -> copy_rows_with_detail).
Offscreen bulk erase via bus write_bytes -> write_offscreen_bytes (span remove_range).

Per-pixel today (ranked, likely slowest first):
1. CopyBits srcOr/transparent/other modes over text: transfer_saved_pixel builds a fresh DetailCell (Vec+HashMap+Box Mix)+Arc per text pixel; legacy path snapshots full row_bytes width (quickdraw.rs ~3861/21065, 4216/21402).
2. ScrollRect (quickdraw.rs:5770; PPC loader/ppc/mod.rs:16833): per-byte read_byte, per-row capture_pixel_detail (per byte), per-pixel copy_saved_pixel/write_byte for the whole rect; all four directions identical (snapshot). Treats every port as 1 byte/pixel.
3. Legacy 8bpp srcCopy with regions/masks (copy_bits_src_copy_rows_8bpp ~20505): copy_saved_pixel on every pixel incl. plain.
4. RowCopy fallback for screen->screen, offscreen->offscreen, screen->offscreen, 24-bit, closed gates: per-byte capture (capture_copy_detail -> capture_pixel_detail), per detail pixel put_detail; offscreen destinations with existing detail lose the bulk plain path (write_plain_copy_span declines).
5. Menu dropdown restore (menu.rs ~5830) calls restore_saved_pixels per byte (len 1); copy_ram_bytes/BlockMove over observed ranges copies per byte.
6. Fills over on-screen text: bus write_bytes/fill_bytes/fill_zeros per byte -> Presentation::write -> clear_text_cell (sync_screen_row_over_text only used by CopyBits). Offscreen fill_bytes/fill_zeros per byte. InvertRect per byte.
7. Text drawing: glyph_pixel per glyph pixel (shapes.rs:1705 outline_glyph_pixel), run_ink HashSet insert per inked sample in opaque runs. TEScroll redraws + re-snapshots dialog (per-row capture).
PPC: GuestAddressSpace has no copy_rows_with_detail; restore_copy_detail per byte put_detail, palette => Arc::make_mut clone per pixel.

Tests covering these: test_scroll_rect, outline_detail_survives_copybits_scrollrect_and_invertrect, plain_copy_rows_match_the_per_pixel_copy, copying_text_matches_the_full_store_and_detail, shared_row_copy_retains_native_detail_in_indexed_and_direct_formats, offscreen_round_trip_overlap_and_palette_translation_preserve_detail, offscreen_rows_copy_to_the_screen_like_the_per_pixel_copy, snapshot_row_copy_matches_pixel_copy_with_overlap_palette_and_outline_detail, indexed_transfers_keep_edges_and_identical_xor_clears_them, glyph_row_blit_matches_the_per_pixel_painter, text_run_overhang_survives_adjacent_erase_but_not_a_new_run, bulk_memory_paths_invalidate_only_overlapping_offscreen_detail, bulk_native_erase_discards_only_touched_outline_cells, cached_menu_bar_restores_outline_coverage_and_tracks_live_inputs, window_frames_at_menu_boundary_preserve_pixels_and_outline_detail, dialog_snapshot_replay_retains_unchanged_outline_detail, copy_ram_bytes_handles_overlap_and_bounds.

Plan (user asks: classic-Mac parity for all text ops; PRs explain before/after work and complexity):
- General detail row copy for any source/destination (screen<->offscreen, overlap-safe), used by RowCopy fallback and ScrollRect.
- Span fills over screen text (write_bytes/fill_bytes on screen via a row-span clear), offscreen fill span.
- Menu restore per row, not per byte.
- Transfer modes (srcOr/transparent) row path later.
- Microbenchmark per operation (ns/pixel before/after).
