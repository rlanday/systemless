---
name: perf-pr-expectations
description: "What perf PRs must explain, and the performance bar for text/graphics paths (classic-Mac parity, all text operations)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 9b3958db-52bb-4ed6-93f4-7f250fbc2210
  modified: 2026-09-27T04:23:52.769Z
---

Perf PR descriptions must explain each optimization in detail: how the code works today, what it changes to and why, and how computational complexity and work per operation change (e.g. per pixel/per sample/per row, allocations, hash lookups).

Performance bar: if an operation was fast (enough) on Classic Mac OS, it must be fast in Systemless. Don't optimize only the one measured game path. Anticipate other text operations games do (scrolling up/down/left/right on screen, offscreen-to-offscreen copies, menu save-behind, drawing text directly on screen, other depths/modes) and make sure they are fast too, ideally with a microbenchmark per operation.

**Why:** the user said so on 2026-09-27 during the retained-text-detail row work (EV crawl), after phase 1 showed a big win on one path.

**How to apply:** when drafting PR bodies, include a before/after table of per-operation work and complexity; when designing fast paths, enumerate sibling operations and measure them. Related: [[commit-authorship-cla]], [[validation-chain-scripts]].
