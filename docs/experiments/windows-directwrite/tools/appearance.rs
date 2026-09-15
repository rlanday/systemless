//! Appearance-only SC2K replay. Render matching city states at both sizes.
//! This is not a performance benchmark.
use std::{path::PathBuf, time::Instant};
use systemless::{display, game, memory::MemoryBus};

fn ms(start: Instant) -> f64 { start.elapsed().as_secs_f64() * 1000.0 }

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let out = PathBuf::from(&args[2]);
    let width: u32 = args[3].parse().unwrap();
    let height: u32 = args[4].parse().unwrap();
    assert!(!out.exists());
    std::fs::create_dir_all(&out).unwrap();
    let mut r = game::new_runner();
    r.set_app_start_time(3_871_497_600);
    let app = game::load_game_from_path(&mut r, std::path::Path::new(&args[1])).unwrap();
    game::init_game(&mut r, &app);
    r.prepare_text_presentation();
    r.set_instructions_per_tick(415_628);
    let (mut raw, mut presented, mut scaled) = (Vec::new(), Vec::new(), Vec::new());
    let mut rows = Vec::new();
    let mut screenshots = Vec::new();
    let mut guest_frames = Vec::new();
    let mut resize_rows = Vec::new();
    for frame in 0..1100 {
        match frame {
            60 | 150 | 240 | 320 | 700 | 780 => {
                r.push_key_down(0x24, 13); r.push_key_up(0x24, 13);
            }
            120 => for ch in b"Systemless Test" {
                r.push_key_down(0, *ch); r.push_key_up(0, *ch);
            },
            520 => r.push_mouse_down(292,465), 522 => r.push_mouse_up(292,465),
            550 => r.push_mouse_down(292,346), 552 => r.push_mouse_up(292,346),
            580 => r.push_mouse_down(312,465), 582 => r.push_mouse_up(312,465),
            610 => r.push_mouse_down(312,346), 612 => r.push_mouse_up(312,346),
            _ => {}
        }
        let total = Instant::now();
        let start = Instant::now();
        let target = r.guest_tick() + 1;
        let mut work = 0;
        while work < game::MAX_INSTRUCTIONS_PER_FRAME {
            let (n, running) = r.run_gui_cpu_slice(50_000, target);
            work += n;
            if !running || r.guest_tick() >= target || n == 0
                || (n < 50_000 && r.is_ui_tracking_active()) { break; }
        }
        let cpu = ms(start);
        let start = Instant::now(); r.prepare_text_presentation(); let prepare = ms(start);
        let start = Instant::now(); r.composite_frame(); let compose = ms(start);
        let start = Instant::now(); r.finish_gui_frame(); let finish = ms(start);
        if ![499,649,849,999,1099].contains(&frame) { continue; }
        let start = Instant::now();
        let d = r.dispatcher();
        display::render_screen_argb_with_gamma(r.bus(), d.screen_mode,
            &d.device_clut, &d.device_gamma(), &mut raw);
        let logical = (u32::from(d.screen_mode.2), u32::from(d.screen_mode.3));
        let raster = ms(start);
        let start = Instant::now();
        let scale = display::outline_output_scale(logical, (width,height));
        let size = r.bus().presented_argb_scaled(&raw, &raw, scale, &mut presented).unwrap();
        let outline = ms(start);
        let start = Instant::now();
        display::resize_argb_coverage(&presented, size, (width,height), &mut scaled);
        let resize = ms(start);
        let start = Instant::now();
        #[cfg(native_text)]
        r.bus().overlay_native_text(&raw, &raw, (0,0,width as usize,height as usize),
            width as usize, &mut scaled);
        let native = ms(start);
        std::hint::black_box(&scaled);
        let total = ms(total);
        let stage = if (400..500).contains(&frame) { "new_city" }
            else if (700..780).contains(&frame) { "newspaper" }
            else if frame >= 850 { "city" } else { "warmup" };
        rows.push(format!("{frame},{stage},{},{work},{cpu:.6},{prepare:.6},{compose:.6},{finish:.6},{raster:.6},{outline:.6},{resize:.6},{native:.6},{total:.6}",r.guest_tick()));
        if [499,649,849,999].contains(&frame) {
            screenshots.push((format!("frame-{frame}-{width}x{height}.png"),width,height,scaled.clone()));
            guest_frames.push((format!("guest-frame-{frame}.bin"),raw.clone()));
        }
        if frame == 499 || frame == 849 || frame == 999 {
            // Same dialog state, first-use resize and warm-cache samples. These
            // are outside the active-frame timings above and have no CPU work.
            for (rw,rh) in [(800,600),(1104,828),(800,600)] {
                for iteration in 0..1 {
                    let total=Instant::now();
                    let start=Instant::now();
                    let scale=display::outline_output_scale(logical,(rw,rh));
                    let size=r.bus().presented_argb_scaled(&raw,&raw,scale,&mut presented).unwrap();
                    let outline=ms(start);
                    let start=Instant::now();
                    display::resize_argb_coverage(&presented,size,(rw,rh),&mut scaled);
                    let resize=ms(start);
                    let start=Instant::now();
                    #[cfg(native_text)]
                    r.bus().overlay_native_text(&raw,&raw,(0,0,rw as usize,rh as usize),rw as usize,&mut scaled);
                    let native=ms(start); let total=ms(total);
                    resize_rows.push(format!("{rw},{rh},{iteration},{outline:.6},{resize:.6},{native:.6},{total:.6}"));
                }
                screenshots.push((format!("scene-{frame}-{rw}x{rh}.png"),rw,rh,scaled.clone()));
            }
        }
    }
    std::fs::write(out.join("timings.csv"),format!("frame,stage,tick,instructions,cpu_ms,prepare_ms,compose_ms,finish_ms,raster_ms,outline_ms,resize_ms,native_ms,total_ms\n{}\n",rows.join("\n"))).unwrap();
    std::fs::write(out.join("resize-timings.csv"),format!("width,height,iteration,outline_ms,resize_ms,native_ms,total_ms\n{}\n",resize_rows.join("\n"))).unwrap();
    std::fs::write(out.join("final-ram.bin"),r.bus().read_bytes(0,9*1024*1024)).unwrap();
    for (name,pixels) in guest_frames {
        std::fs::write(out.join(name),pixels.iter().flat_map(|p|p.to_le_bytes()).collect::<Vec<_>>()).unwrap();
    }
    for (name,w,h,pixels) in screenshots {
        image::RgbaImage::from_raw(w,h,pixels.iter().flat_map(|p|[(p>>16)as u8,(p>>8)as u8,*p as u8,255]).collect())
            .unwrap().save(out.join(name)).unwrap();
    }
    println!("Completed 1100 frames at {width}x{height}; logs and screenshots saved.");
}
