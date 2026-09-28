# Retained text detail as rows: design and plan of record

## Problem

EV Override's opening crawl costs about 0.8 of a native core (more in the browser), against a target of 7%. Every frame it:

1. erases an offscreen GWorld;
2. draws about ten lines of text into it;
3. CopyBits it to the screen through a colour table.

The text shifts one row per frame. A native port does three memory operations per frame.

Systemless also keeps retained outline-text detail: 4×4 subpixel indices plus antialiasing ink for each guest pixel that holds text (#1524). On the screen, detail lives in a per-pixel grid of pooled tiles. Offscreen, it lives in `BTreeMap<u32, Arc<DetailCell>>`, one heap cell per address. The crawl pays for that per pixel, every frame:

- **Glyph drawing** (`glyph_pixel`, 21%): a B-tree insert, an `Arc` allocation and ink compositing, for every glyph pixel.
- **Erase** (`Presentation::write` via EraseRect, 14%): cell-by-cell clears and B-tree removes.
- **CopyBits:**
  - `capture_pixel_detail` builds a `SavedPixels` detail map per pixel.
  - `store_detail_pixel` / `put_detail` rebuild each screen cell, including its resolved RGB.
  - The copy loop itself costs 15%.
- **B-tree insert and remove:** about 10% in total.

Cheaper cells (per-cell ink storage) removed the hash-map costs and bought only 7%, because the cost is the per-pixel, per-address structure itself.

## Key finding

The code that draws text and copies pixels knows the pixmap geometry, but the presentation layer doesn't.

- `draw_generic_shape` (`src/trap/shapes.rs:1187-1236`) resolves the destination's `(pix_base, row_bytes, pixel_size, bounds)` and then calls `outline_glyph_pixel(address, x, y, fg)` once per pixel.
- `RowCopy` (`src/copy_bits.rs:466`) carries source and destination `BytePixmap { base, row_bytes, depth, bounds }`, but captures detail per byte into a flat `SavedPixels` keyed by byte offset.

So detail can only be stored and moved per address, because that's all the presentation is told.

## End state

A frame of the crawl should cost what a native port's does: a few memory operations per row of text. The layout and API below are fixed from phase 1, so later phases change implementations, not formats.

### Decision 1: detail is stored in rows

A **surface** is a pixmap whose geometry the presentation knows: `{ base, row_bytes, width, height, depth }`. It holds one optional `DetailRow` per pixel row, and rows without text cost nothing. A `DetailRow` contains:

- the row's subpixel indices, contiguous: `scale²` bytes per column, i.e. 16 bytes per pixel at 4×;
- a text bitmask, one bit per column;
- the row's ink, as a small column-sorted list of `(column, sample, Ink)`, since antialiasing ink is sparse;
- a row revision, for change tracking.

Copying text between rows starts as a loop over set bits and becomes a `memcpy` of the index bytes plus a table-lookup pass for colour mapping. It's the same code getting faster, not a new format.

### Decision 2: the screen is a surface

The screen uses the same `DetailRow` storage, so scrolls within the screen, CopyBits from offscreen to screen, and CopyBits between offscreen buffers are all one row-copy operation. The screen's current tile grid (`DetailSamples`, `text_cells`, `ink_mask`, `detail_cache`) is replaced in phase 2, not kept alongside.

### Decision 3: rows hold indices and ink only; colour is resolved when composing

Screen tiles currently store resolved RGB per subpixel and recompute it on every `put_detail`: a palette lookup per subpixel, per copy, per frame. In the end state, RGB is resolved only when a changed row is composed. A palette change marks rows changed instead of repainting stored samples.

### Decision 4: the presentation API is span-level

The operations are:

- `erase_span(surface, row, columns)`
- `copy_rows(src_surface, dst_surface, src_rect, dst_origin, colour_map)`
- `draw_glyph(surface, origin, glyph, style, colours)`
- `capture_span` / `restore_span` for snapshots
- `mark_rows_changed(surface, rows)`

Today's per-address entry points become thin wrappers that resolve the address to a (surface, row, column) and call the span operations, so every existing caller keeps working:

- `glyph_pixel`, `write`, `put_detail`, `copy_saved_pixel`, `capture_pixel_detail`
- `restore_saved_pixels`, `observes_range`

Callers then migrate to span calls one at a time, starting with `draw_generic_shape`, `RowCopy` and the rect fills.

### Fallback

Addresses outside every registered surface keep today's `BTreeMap<u32, Arc<DetailCell>>`. Paths and games that never register a surface behave exactly as now. The fallback is both the safety net and the migration path. It can be retired once every surface-producing path registers geometry.

### Snapshots

`SavedPixels` keeps `Arc<DetailCell>` at its boundary in phases 1–2. Capture builds cells from rows, with a per-row identity cache like today's `detail_cache`. Moving snapshots to row spans is a later, optional step.

## Phases

Each phase is shipped and measured separately. Gate for every phase: SC2K and EV exact, the full suite passes, and no SC2K host-instruction regression.

### Phase 1: `DetailRow`, surfaces and the span API, for offscreen buffers

- Add `DetailRow` and the surface registry.
- Plumb geometry from `draw_generic_shape` (text) and `RowCopy` (CopyBits destination) to register offscreen surfaces.
- Implement the span operations for offscreen surfaces:
  - `glyph_pixel` into rows;
  - `erase_span` over rows, skipping rows with no text;
  - capture and restore through the snapshot boundary.
- The per-address wrappers route offscreen addresses to a surface when one covers them, and to the B-tree otherwise. The screen is unchanged.
- **Tests:**
  - The ~35 existing offscreen-detail tests pass unchanged. They don't know which storage is used.
  - New differential tests replay operation sequences against both storages and compare `capture_detail_range` and the rendered screen byte for byte.

Expected: removes the B-tree and per-pixel `Arc` costs for drawing and erasing offscreen text.

### Phase 2: the screen becomes a surface, CopyBits copies rows, compose resolves colour

- The screen adopts `DetailRow` storage, retiring `DetailSamples`, `text_cells`, `ink_mask` and the per-tile RGB.
- `RowCopy` with detail becomes `copy_rows` with colour mapping.
- Compose and compact export read rows and resolve colour per changed row. Change tracking moves to row revisions (tile epochs become derived).
- This is the structural step that makes the crawl a row copy. It touches compose, compact export and the resolved-output caches, so it needs the closest review.

Expected: removes per-pixel `put_detail`, `capture_pixel_detail` and `SavedPixels` detail maps from CopyBits.

### Phase 3: cached glyph spans

- A glyph drawn onto a uniform background produces a small stack of `DetailRow` spans relative to its origin, keyed by (mask identity including style, scale, foreground, background index).
- Drawing a cached glyph is span copies. Overlapping text or a non-uniform background composites as now.

Expected: removes most per-sample rasterisation.

### Phase 4: closing the gap, by tuning the same structures

- `copy_rows` skips destination rows whose content is unchanged (compare row revisions and source identity).
- Vectorise the index mapping.
- Compose only changed rows.

These are tuning steps, not new formats.

## Estimates (not yet measured)

| After phase | EV crawl, native |
| --- | --- |
| today | ~0.8 core |
| 1 | ~0.55–0.65 |
| 2 | ~0.25–0.35 |
| 3 | ~0.15–0.2 |
| 4 | toward the 7% target; the remaining floor is the guest's own QuickDraw work and compose of changed rows |

## Costs and risks

- **Phase 1 is heavier than a direct port.** It defines `DetailRow` and the span API rather than reusing the screen's tile code.
- **Memory.** A text row costs its full width: 16 bytes per pixel at 4×, about 10 KB for a 640-pixel row, but only for rows that hold text. A registered surface costs one pointer per row. The surface count is capped, with LRU eviction to the fallback.
- **Geometry plumbing.** Passing pixmap geometry into text drawing and `RowCopy` touches their signatures. Indexed vs. direct depths (lanes) need care. PowerPC paths use the same bus APIs and keep the fallback until they register.
- **Lifetime.** Plain stores over a surface clear its rows exactly as they clear B-tree entries today, which covers freed and reused GWorld memory. A surface with no text for N frames is dropped.
- **Phase 2 changes the screen's representation.** It touches compose, compact export and resolved outputs. It extends Ben's #1524 design, so his review is wanted before phase 2 at the latest, and ideally before phase 1.

## Revised after measurement (2026-09-28)

What was built differs from the phases above, because profiles pointed elsewhere.

- **Phase 1 as planned in spirit, not in form.** Offscreen detail lives in 256-byte address chunks rather than registered surfaces: no geometry plumbing and no fallback store. CopyBits copies offscreen rows straight to the screen.
- **Phase 2 was partly done by another route.**
  - Done: a general row copy (`copy_detail_spans`) between any screen and offscreen rows, overlap-safe, used by CopyBits, ScrollRect, region-clipped copies and BlockMove; screen ink stored with its tile; fills and menu restores a row at a time.
  - Not done: replacing the screen's tile pool with `DetailRow` storage, and resolving colour at compose time. Measurements showed the copy cost was ink hashing, then pointer-chasing into per-cell heap ink lists, not the tile layout. Compose re-renders the whole frame from stored RGB, so resolving colour there would add work to every frame for static text (SC2K) unless a per-row RGB cache were added too. Revisit only if a profile shows copy-time colour resolution matters.
  - Row revisions: deferred to phase 4; a byte comparison of packed cells may suffice.
- **Packed ink (added).** Ink over one background colour packs into four bytes inline with each cell; blended backgrounds go to a side table. This makes a cell's detail fixed-size plain data, which phases 3 and 4 build on.
- **Phase 3.** Glyph pixels are handed over in row runs (no measurable crawl gain alone). Cached glyph spans remain: stamp precomputed cells when the destination is blank.
- **Order from here:** validate packed ink; cached glyph spans; row-level skip and vectorised mapping; compact snapshots (SavedPixels still holds an Arc'd cell with a HashMap of ink per pixel); then the PowerPC CopyBits hookup and transfer modes.
