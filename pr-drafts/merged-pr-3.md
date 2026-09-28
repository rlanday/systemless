Stacked on #3071; review the commit after it. Third of five PRs making retained outline text cheap.

## How it works today

The QuickDraw shape loop (`draw_generic_shape`, which draws text as `ShapeOp::Glyph`) calls `outline_glyph_pixel` once for every pixel of a glyph's clipped rectangle, after its clip and region tests. Each call borrows the presentation, reads that pixel's background byte, marks the pixel's 4 KiB page in the offscreen page index (`include_offscreen_address`) and looks up its 256-byte chunk, before painting the pixel's 16 samples.

## What changes

Before drawing a row's pixels, the loop finds that row's runs of clipped glyph pixels (the same clip, region and row-width tests) and hands each run to the presentation in one `outline_glyph_span` call. The span call reads the run's background bytes at once, marks each page once and looks each chunk up once, then paints each pixel with the same function the per-pixel call uses, so both produce identical cells. A run touching the screen still goes pixel by pixel. The opaque-run ink set now uses the presentation's sample-offset hasher instead of SipHash.

Each row's runs are handed over before the row's pixels are drawn, so every glyph pixel still sees its background as it was before the text, as it did when the call came just before each pixel's store.

| Per glyph pixel of a run | Before | After |
| --- | --- | --- |
| presentation borrow and background read | 1 each | 1 per run |
| offscreen page mark | 1 | 1 per page |
| chunk lookup | 1 | 1 per 256 bytes |
| sample painting | unchanged | unchanged |

## Why, given the numbers

This removes per-pixel overhead but not the sample painting, which is where offscreen glyph time goes; EV Override's crawl is unchanged within noise. It is the entry point the next step builds on: cached glyph spans, which stamp precomputed cells for a whole run when the destination is blank.

## Validation

- **EV Override:** identical at 2,400, 3,000 and 9,000 ticks; crawl window unchanged within run-to-run noise (3.3-4.0 s).
- **SimCity 2000:** identical; host instructions -0.18% vs master (-0.04% over #3071).
- **Tests:** `glyph_spans_match_the_per_pixel_calls` compares span and per-pixel calls for 1-, 2- and 4-byte pixels, opaque and transparent runs, within a chunk, across a chunk boundary and across a page; full suite passes.

— Opus 5.5

🤖 Generated with [Claude Code](https://claude.com/claude-code)