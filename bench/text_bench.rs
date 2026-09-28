//! Per-operation costs of drawing and moving retained outline text, for
//! before/after comparisons. It uses only APIs master shares, so the same
//! file measures both. Run:
//!
//! cargo test --profile fast --lib --no-default-features --features jit,test-support \
//!     -- --ignored --nocapture text_operation_costs

use super::*;
use crate::copy_bits::{BytePixmap, RowCopy, RowCopyOutcome};
use std::time::{Duration, Instant};

const W: u32 = 640;
const H: u32 = 480;
const SCREEN: u32 = 0x10_0000;
const OFF: u32 = 0x20_0000;
const OFF2: u32 = 0x30_0000;

fn glyph() -> OutlineGlyph {
    let (width, height) = ((W * 4) as i32, ((H + 2) * 4) as i32);
    OutlineGlyph {
        pixels: (0..width * height)
            .map(|i| [0u8, 255, 128, 64, 255, 0, 200][((i * 31 + i / width * 17) % 7) as usize])
            .collect(),
        width,
        height,
        left: 0,
        top: 0,
    }
}

fn fresh() -> MacMemoryBus {
    let mut bus = MacMemoryBus::new(8 * 1024 * 1024);
    let palette = std::array::from_fn(|i| [i as u8, (i * 3) as u8, (255 - i) as u8]);
    bus.fill_bytes(SCREEN, W * H, 0);
    bus.enable_outline_presentation((SCREEN, W, W as u16, H as u16, 8), palette, 4);
    bus
}

/// Text-like detail: 12-pixel lines every 16 rows, glyph pixels on three of
/// every five columns, as a page of body text covers about a third of it.
fn paint_text(bus: &mut MacMemoryBus, glyph: &OutlineGlyph, base: u32, rows: std::ops::Range<u32>) {
    set_glyph(bus, glyph);
    draw_glyph_rows(bus, base, rows);
    bus.end_outline_glyph();
}

/// Install `glyph` for drawing (a 5 MB copy, kept out of timed regions).
fn set_glyph(bus: &mut MacMemoryBus, glyph: &OutlineGlyph) {
    bus.presentation.as_mut().unwrap().glyph = Some((glyph.clone(), 0, 0));
}

/// `draw_glyph_rows` through row runs, as the QuickDraw shape loop draws.
fn draw_glyph_spans(bus: &mut MacMemoryBus, base: u32, rows: std::ops::Range<u32>) {
    for y in rows {
        if y % 16 >= 12 {
            continue;
        }
        for x in (0..W).step_by(5) {
            bus.outline_glyph_span(base + y * W + x, (x as i16, y as i16), 3.min((W - x) as usize), 1, 200);
        }
    }
}

/// Draw the installed glyph's pixels over `rows` (the glyph stays installed).
fn draw_glyph_rows(bus: &mut MacMemoryBus, base: u32, rows: std::ops::Range<u32>) {
    for y in rows {
        if y % 16 >= 12 {
            continue;
        }
        for x in 0..W {
            if x % 5 < 3 {
                bus.outline_glyph_pixel(base + y * W + x, x as i16, y as i16, 200 + (x % 7) as u8);
            }
        }
    }
}

fn pixmap(base: u32, rows: u32) -> BytePixmap {
    BytePixmap { base, row_bytes: W, depth: 8, bounds: [0, 0, rows as i32, W as i32] }
}

fn copy(bus: &mut MacMemoryBus, from: (u32, [i32; 4]), to: (u32, [i32; 4]), palette: Option<&[u8; 256]>) {
    let copy = RowCopy {
        mode: 0,
        source: pixmap(from.0, H + 2),
        destination: pixmap(to.0, H),
        source_rect: from.1,
        destination_rect: to.1,
        clip: [0, 0, H as i32, W as i32],
        palette,
    };
    assert_eq!(copy.execute(bus), RowCopyOutcome::Completed);
}

fn report(name: &str, pixels: u64, mut samples: Vec<Duration>) {
    samples.sort();
    let median = samples[samples.len() / 2];
    println!(
        "{name:<52} {:>9.1} ns/pixel {:>10.3} ms",
        median.as_nanos() as f64 / pixels as f64,
        median.as_secs_f64() * 1e3
    );
}

/// Median time of `op` on a bus prepared by `setup` (not timed), fresh each run.
fn cold(name: &str, pixels: u64, runs: usize, setup: impl Fn() -> MacMemoryBus, op: impl Fn(&mut MacMemoryBus)) {
    let samples = (0..runs)
        .map(|_| {
            let mut bus = setup();
            let start = Instant::now();
            op(&mut bus);
            start.elapsed()
        })
        .collect();
    report(name, pixels, samples);
}

/// Median time of the `i`th repetition of `op` on one prepared bus.
fn steady(name: &str, pixels: u64, runs: usize, mut bus: MacMemoryBus, op: impl Fn(&mut MacMemoryBus, usize)) {
    op(&mut bus, 0);
    let samples = (1..=runs)
        .map(|i| {
            let start = Instant::now();
            op(&mut bus, i);
            start.elapsed()
        })
        .collect();
    report(name, pixels, samples);
}

#[test]
#[ignore = "benchmark; run with --ignored --nocapture"]
fn text_operation_costs() {
    let glyph = glyph();
    let full = u64::from(W * H);
    let whole = [0, 0, H as i32, W as i32];
    let table: [u8; 256] = std::array::from_fn(|i| (i as u8).wrapping_mul(7));
    let with_offscreen_text = || {
        let mut bus = fresh();
        paint_text(&mut bus, &glyph, OFF, 0..H + 2);
        bus
    };
    let with_screen_text = || {
        let mut bus = fresh();
        paint_text(&mut bus, &glyph, SCREEN, 0..H);
        bus
    };
    println!("{:<52} {:>18} {:>13}", "operation (640x480 8-bit, 4x detail)", "per pixel", "per call");

    cold("draw text into an offscreen buffer (per glyph pixel)", u64::from(W * 64), 3, || {
        let mut bus = fresh();
        set_glyph(&mut bus, &glyph);
        bus
    }, |bus| draw_glyph_rows(bus, OFF, 0..64));
    cold("draw text onto the screen (per glyph pixel)", u64::from(W * 64), 3, || {
        let mut bus = fresh();
        set_glyph(&mut bus, &glyph);
        bus
    }, |bus| draw_glyph_rows(bus, SCREEN, 0..64));
    cold("draw text into an offscreen buffer (row runs)", u64::from(W * 64), 5, || {
        let mut bus = fresh();
        set_glyph(&mut bus, &glyph);
        bus
    }, |bus| draw_glyph_spans(bus, OFF, 0..64));
    steady("CopyBits offscreen->screen, destination unchanged", full, 5, with_offscreen_text(), |bus, _| {
        copy(bus, (OFF, whole), (SCREEN, whole), None)
    });
    steady("CopyBits offscreen->screen via table, text moved 1 row", full, 6, with_offscreen_text(), |bus, i| {
        let shift = (i % 2) as i32;
        copy(bus, (OFF, [shift, 0, H as i32 + shift, W as i32]), (SCREEN, whole), Some(&table))
    });
    cold("CopyBits screen->screen, scroll up 1 row", full, 3, with_screen_text, |bus| {
        copy(bus, (SCREEN, [1, 0, H as i32, W as i32]), (SCREEN, [0, 0, H as i32 - 1, W as i32]), None)
    });
    cold("CopyBits screen->screen, scroll down 1 row", full, 3, with_screen_text, |bus| {
        copy(bus, (SCREEN, [0, 0, H as i32 - 1, W as i32]), (SCREEN, [1, 0, H as i32, W as i32]), None)
    });
    cold("CopyBits screen->screen, scroll left 1 pixel", full, 3, with_screen_text, |bus| {
        copy(bus, (SCREEN, [0, 1, H as i32, W as i32]), (SCREEN, [0, 0, H as i32, W as i32 - 1]), None)
    });
    cold("CopyBits offscreen->offscreen", full, 3, with_offscreen_text, |bus| {
        copy(bus, (OFF, whole), (OFF2, whole), None)
    });
    cold("CopyBits screen->offscreen 300x200 (save-behind)", 300 * 200, 3, with_screen_text, |bus| {
        copy(bus, (SCREEN, [40, 40, 240, 340]), (OFF2, [0, 0, 200, 300]), None)
    });
    cold("EraseRect over screen text (fill per row)", full, 3, with_screen_text, |bus| {
        for y in 0..H {
            bus.fill_bytes(SCREEN + y * W, W, 0);
        }
    });
    cold("EraseRect over offscreen text (fill per row)", full, 3, with_offscreen_text, |bus| {
        for y in 0..H {
            bus.fill_bytes(OFF + y * W, W, 0);
        }
    });
    let saved_menu = || {
        let mut bus = with_screen_text();
        let rows: Vec<SavedPixels> = (40..340).map(|y| bus.save_pixel_bytes(SCREEN + y * W + 40, 200)).collect();
        for y in 40..340 {
            bus.fill_bytes(SCREEN + y * W + 40, 200, 3);
        }
        (bus, rows)
    };
    let samples = (0..3)
        .map(|_| {
            let (mut bus, rows) = saved_menu();
            let start = Instant::now();
            for (i, row) in rows.iter().enumerate() {
                bus.restore_saved_pixels(SCREEN + (40 + i as u32) * W + 40, row, 0, 200);
            }
            start.elapsed()
        })
        .collect();
    report("restore a 200x300 menu's save-behind over text", 200 * 300, samples);
    cold("BlockMove offscreen rows with text (per row)", full, 3, with_offscreen_text, |bus| {
        for y in 0..H {
            assert!(bus.copy_ram_bytes(OFF + y * W, OFF2 + y * W, W));
        }
    });
}
/// The screen scroll alone, repeated, for a sampling profiler.
#[test]
#[ignore = "profiling loop; run with --ignored"]
fn scroll_profile_loop() {
    let glyph = glyph();
    let mut bus = fresh();
    paint_text(&mut bus, &glyph, SCREEN, 0..H);
    for i in 0..60 {
        let (from, to) = if i % 2 == 0 { (1, 0) } else { (0, 1) };
        copy(
            &mut bus,
            (SCREEN, [from, 0, from + H as i32 - 1, W as i32]),
            (SCREEN, [to, 0, to + H as i32 - 1, W as i32]),
            None,
        );
    }
}
