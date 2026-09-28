# Retained-text performance work: handoff (2026-09-28)

## Where things stand

**Merged upstream:** #3070-#3074 (offscreen chunks, ink with cells, glyph row runs, row copies in every direction, bulk paths). On master `37bcbe9b`: EV Override crawl window (ticks 2,400-3,000) 3.7-3.8 s CPU; SimCity 2000 -7.7% host instructions vs the pre-stack master; both exact.

**Unmerged, pushed to `rlanday/systemless`** (each based on the previous; authored by Ryan, co-authored by Claude):

| Branch | Content | Validated |
| --- | --- | --- |
| `perf/text-6-packed-ink` | packed 4-byte ink inline per cell; packed blocks through copies; sparse offscreen ink | as part of the stack below: suite, SC2K, EV exact; the PR-6-only tree's own suite/SC2K run was interrupted |
| `perf/text-7-powerpc-rows` | PowerPC CopyBits uses the span copy | new differential test passes; PR-7-only suite run interrupted |
| `perf/text-8-glyph-painting` | one-pass glyph cell painter; blank cells painted as one packed block | full suite 5,934/0; SC2K identical to master 37bcbe9b (-0.07% instr); EV run was interrupted |
| `perf/text-small-wins` | glyph-span backgrounds on the stack; skip unchanged kiosk margin rescans (+ test) | not compiled yet |

Measured on the stack up to text-8 minus the fast path (EV vs master 37bcbe9b, exact): crawl 3.7/3.8 s -> 2.7/2.4 s; 9,000-tick run 24.8 -> 23.8 s. Benchmark (`bench/text_bench.rs`, 640x480 8-bit, 4x detail): full-screen one-row scroll 81 ms (merged stack) -> 21.6 ms; offscreen text drawing 3.69 ms (packed) -> 2.98 ms with the blank-cell fast path.

PR descriptions for 6-8 are drafted in `pr-drafts/` (TBDs are the numbers the interrupted runs would have filled in). The five merged PRs' bodies are there too as the style reference.

## Next steps, in order

1. **Finish validating 6-8 and the small wins:** full suite per branch (touch `src` first and confirm the log shows `Compiling systemless v`), SC2K exactness + instruction counts vs current master, EV exactness + crawl timing, and the per-operation benchmark. Fill the TBDs, then open 6, 7, 8 as stacked PRs (each against master, "review the commits after #N"). Ask before publishing.
2. **Open question:** offscreen drawing got ~20% slower between packed ink and the follow-ups (3.69 -> 4.41 ms) before the fast path fixed it. Either the one-pass painter or the sparse chunk ink growth. Benchmark a tree with packed ink + painter but not sparse storage to split them.
3. **Remaining phases** (see `design.md`, "Revised after measurement"): screen-tile paste per-cell work (~18% of the crawl), cached/stamped glyph spans beyond the blank-cell path, row-level skip and vectorised mapping, compact snapshots (SavedPixels still holds an Arc'd cell + HashMap of ink per pixel), transfer modes (srcOr etc.) over text, on-screen glyph drawing. Re-profile after each; the goal is 7% of a core for the crawl, so at some point the remaining cost will be the emulator, not text.

## How to resume with Claude Code on another machine

1. Clone your fork and fetch these branches:
   ```
   git clone https://github.com/rlanday/systemless.git && cd systemless
   git remote add upstream https://github.com/benletchford/systemless.git && git fetch upstream
   git fetch origin perf/text-6-packed-ink perf/text-7-powerpc-rows perf/text-8-glyph-painting perf/text-small-wins notes/opus-text-perf
   git worktree add ../systemless-notes origin/notes/opus-text-perf
   ```
2. Restore Claude's memory notes: copy `memory/*.md` into `~/.claude/projects/<project-dir>/memory/` (the directory Claude Code creates for your checkout, e.g. `-home-<you>-src-systemless`), or just point Claude at them.
3. Start Claude Code in the checkout and say something like: "Read ../systemless-notes/HANDOFF.md, progress-log.md and design.md, then continue the retained-text performance work from 'Next steps'."
4. Rebuild the validation setup (what this laptop had):
   - **Rust + tests:** `cargo test --profile ci-test --lib --no-default-features --features jit,test-support` (full suite, ~20 min cold). Use a separate `--target-dir` per worktree, or touch `src` before each run: a shared target dir silently reused another tree's test binary here.
   - **SC2K counters (Linux):** `tools/build-sc2k-variant.py --platform linux` builds a frozen replay binary from a worktree using `tools/reuse-compact-profile.rs` as the driver; `tools/run-sc2k-variant-linux.py public a` runs it; `tools/check-linux-exact.py <baseline-run> <variant-run>` compares; `tools/opus-measure-retired.py` counts instructions/cycles (perf_event). Needs the SC2K test archive (`sc2k-expanded-test.kpak`), which is not in this branch, and a master baseline built the same way. Edit the paths at the top of the scripts (`W = R / 'systemless-<tree>'`, the m68k crate path).
   - **EV Override (Windows):** `tools/run-opus-ev.ps1 -Run <dir> -Binary <exe> -Mode public -Ticks 9000 -ExactnessOnly -InputScript <frozen-input.txt>` runs the headless replay and writes state/image hashes and CPU seconds. Needs the EV Override 1.0.1 archive (set `<EV_ARCHIVE_DIR>` in both scripts) and the frozen input script, `tools/ev-frozen-input.txt` (ticks with clicks and key presses: create a pilot, skip the story crawl, fly briefly; checkpoints at 2,400, 3,000 and 9,000 ticks). Time only on AC power; compare against a master exe built the same way; assert the exe hashes differ (a shared cargo target dir once produced a byte-identical "variant").
   - **Profiles (Windows):** build `tools/sample-stacks.c` / `sample-stacks-busiest.c` with `x86_64-w64-mingw32-gcc -O2 -municode ... -ldbghelp -lwinmm -lpsapi`; `run-opus-ev-sampled-stacks.ps1` samples an EV run; `tools/opus-evstack.py <samples.csv> <exe> 50` prints inclusive/self tables. For a Rust test (benchmark loop), use the busiest-thread sampler with `SAMPLE_BUSIEST_THREAD=1`, since libtest runs tests on a worker thread.
   - **Benchmark:** add `bench/text_bench.rs` as `src/systems/macintosh/memory/presentation/text_bench.rs` with `#[cfg(test)] mod text_bench;` in `presentation.rs`, then `cargo test --profile fast --lib --no-default-features --features jit,test-support -- --ignored --nocapture --test-threads 1 text_operation_costs`.

## Rules that applied throughout

- Commits authored by Ryan Landay <rlanday@gmail.com>; Claude only in `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (CLA check).
- Push to the fork over HTTPS, open PRs with `gh pr create -R benletchford/systemless --head rlanday:<branch>`; PR bodies explain today's code, the change and why, and per-operation work before/after, and end with the Claude Code line.
- Confirm before publishing; one cargo build at a time; never bare `git stash`; don't run `cargo fmt` on the tree; no SC2K regressions.
