Stacked on #PR6; review the commit after it. Gives PowerPC programs the row copy for retained text that 68k programs got in #3073.

## How it works today

A PowerPC program's CopyBits resolves its arguments in the PowerPC import and then runs the same `RowCopy` as the 68k trap, but against its own address space (`GuestAddressSpace`). That memory adapter has no row path for retained text, so copying text still snapshots a `SavedPixels` with an `Arc<DetailCell>` per text pixel and restores it with a `put_detail` per pixel; through a colour table, each cell is cloned and mapped (`Arc::make_mut`) per pixel.

## What changes

- **The span copy is split into a presentation half and a memory half.** The capture/store/paste core (`copy_detail_spans`, `copy_saved_spans`) moves onto the shared presentation slot and takes a closure that stores guest memory. The 68k bus keeps its own checks (tracing and probe gates, address translation, writable RAM) and passes a store into its RAM.
- **The PowerPC adapter implements the row path.** It admits destinations that are a plain writable region or lie wholly within writable shared mappings (the screen, in a PowerPC process, is a shared alias of the bus's RAM), checks all of them before writing anything, stores them without re-running the presentation's own store handling (the copy updates the presentation itself), and still retires writable-code tokens for the pages it writes. Anything else declines to the existing per-pixel path.

A copied cell records the byte actually stored as its value, as on the 68k side. The PowerPC per-pixel fallback records the source cell's value instead; the two agree whenever a cell's value equals its pixel byte, which every normal store keeps true, so no output changes.

## Work per operation

| Per text pixel, PowerPC CopyBits | Before | After |
| --- | --- | --- |
| capture | `Arc` clone + `HashMap` insert | copy the cell into a reused buffer |
| through a colour table | clone and map the whole cell | table lookups on indices and packed ink |
| store | `write_bytes` + `put_detail` | bulk store + in-place cell write if changed |

## Validation

- **Tests:** `powerpc_rows_copy_like_the_per_pixel_copy` compares the new path with the PowerPC fallback (offscreen to screen, and a screen scroll that overlaps itself, with and without a colour table); full suite TBD.
- **SimCity 2000 and EV Override** (68k; the bus half was refactored): TBD.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)
