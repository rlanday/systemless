//! Same deterministic SC2K input for all five font treatments. Diagnostic only.
use std::path::{Path,PathBuf};
use systemless::{display,game};
fn main() {
    let args:Vec<_>=std::env::args().collect();let out=PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out).unwrap();
    let mut r=game::new_runner();r.set_app_start_time(3_871_497_600);
    let app=game::load_game_from_path(&mut r,Path::new(&args[1])).unwrap();game::init_game(&mut r,&app);
    r.prepare_text_presentation();r.set_instructions_per_tick(415_628);
    for frame in 0..1100 {
        match frame {
            60|150|240|320|700|780=>{r.push_key_down(0x24,13);r.push_key_up(0x24,13);},
            120=>for ch in b"Systemless Test" {r.push_key_down(0,*ch);r.push_key_up(0,*ch);},
            _=>{}
        }
        let target=r.guest_tick()+1;let mut work=0;
        while work<game::MAX_INSTRUCTIONS_PER_FRAME {
            let (n,running)=r.run_gui_cpu_slice(50_000,target);work+=n;
            if !running||r.guest_tick()>=target||n==0||(n<50_000&&r.is_ui_tracking_active()){break;}
        }
        r.prepare_text_presentation();r.composite_frame();r.finish_gui_frame();
        let scene=match frame {499=>"new-city",999=>"city",_=>continue};
        let d=r.dispatcher();let mut raw=Vec::new();
        display::render_screen_argb_with_gamma(r.bus(),d.screen_mode,&d.device_clut,&d.device_gamma(),&mut raw);
        for (w,h,label) in [(800,600,"100"),(1104,828,"138")] {
            let mut pixels=Vec::new();r.bus().presented_argb_resized(&raw,&raw,(w,h),&mut pixels).unwrap();
            image::RgbaImage::from_raw(w,h,pixels.iter().flat_map(|p|[(p>>16)as u8,(p>>8)as u8,*p as u8,255]).collect()).unwrap().save(out.join(format!("{scene}-{label}.png"))).unwrap();
        }
    }
    println!("SC2K reference replay complete.");
}
