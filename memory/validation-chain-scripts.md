---
name: validation-chain-scripts
description: "Pitfalls in the detached validation-chain scripts under target/windows-validation (grep waits, pgrep self-matches, one build at a time, stale desktop binaries)"
metadata:
  node_type: memory
  type: project
  originSessionId: 9b3958db-52bb-4ed6-93f4-7f250fbc2210
  modified: 2026-09-26T15:57:21.267Z
---

The perf validation chains live in `target/windows-validation/opus-*.sh`, run detached (`setsid nohup ... &`) so they survive Claude Code restarts, and are polled by grepping their `.out` files.

**Why:** three separate times a poll or a queued script's wait matched the word `failed` in a passing suite line ("0 failed"), which either ended the wait early or started a queued build on top of a running one, breaking the one-build-at-a-time rule and disturbing cycle counts. `pgrep -f`/`pkill -f` patterns have also matched the invoking shell itself (exit 144) more than once. And on 2026-09-26 a phase-1 EV comparison was silently master-vs-master: two worktrees built into one shared `desk-target`, cargo judged the second tree's binary fresh (0.38 s, no compile), and the copied exe was byte-identical to master's.

**How to apply:** wait on explicit markers (`... DONE`, `build failed`, `chain skipped`), never on bare `failed`; write pgrep patterns with the bracket trick (`[o]pus-foo.sh`) and kill by PID; keep only one cargo build/test running at a time (shared CPU); `--profile ci-test` suites take ~10 min to compile. Build each tree's desktop exe into its own target dir (`desk-target-<tree>`) and assert the copied exe's sha256 differs from the baseline's before measuring. Don't edit a worktree while a chain is compiling from it. The same staleness hits `cargo test` in the shared `mojo-test-target`: on 2026-09-28 two suites "passed" without compiling their tree (a sibling's test binary was reused; the tree did not even compile). Touch the tree's `src` before every test run and check the log has a `Compiling systemless v` line before trusting a result. Related: [[commit-authorship-cla]].
