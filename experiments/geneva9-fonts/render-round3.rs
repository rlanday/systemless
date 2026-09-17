use systemless::{cpu::{M68kCpu,Register},memory::{MacMemoryBus,MemoryBus},trap::TrapDispatcher,display,quickdraw::fonts};

fn samples() {
    let out=std::path::PathBuf::from(std::env::args().nth(1).unwrap());
    std::fs::create_dir_all(&out).unwrap();
    let mut audit=String::new();
    for id in [1,3,21] { for size in [9,12] {
        let f=fonts::get_font_face(id,size).unwrap();
        audit+=&format!("family={id} size={size} metrics={},{},{},{} advances={:?}\n",f.metrics.ascent,f.metrics.descent,f.metrics.wid_max,f.metrics.leading,f.glyphs.iter().map(|g|g.advance).collect::<Vec<_>>());
    }}
    std::fs::write(out.join("guest-metrics.txt"),audit).unwrap();
    let mut d=TrapDispatcher::new();let mut c=M68kCpu::new();let mut b=MacMemoryBus::new(8*1024*1024);
    let (w,h)=(440u16,250u16);let base=0x400000;d.set_screen_mode_for_test(base,u32::from(w),w,h,8);
    let palette=display::rgba_palette_from_clut_with_gamma(&d.device_clut,&d.device_gamma()).map(|v| {let [r,g,b,_]=v.to_le_bytes();[r,g,b]});
    b.enable_outline_presentation(d.screen_mode,palette,4);
    c.write_reg(Register::A5,0x20000);c.write_reg(Register::A7,0x10000);b.write_long(0x10000,0x21000);d.dispatch(0xa86e,&mut c,&mut b).unwrap();
    for (op,value) in [(0xa887,3),(0xa88a,9),(0xa889,1)] {
        c.write_reg(Register::A7,0x10000);b.write_word(0x10000,value);d.dispatch(op,&mut c,&mut b).unwrap();
    }
    for (y,text) in [
        (20,"Citizens Demand Road&Rail  Rail ail il li"),
        (40,"minimum minimal mineral  mini imi mim imi"),
        (60,"Power Plant Needed  P H R B  y v x j i  jumps"),
        (80,"Tool Tools Total Town Time Today Toad"),
        (100,"AT TA TT LT ST  STREET STOP CITY  your young year"),
        (120,"city little silk milk look  kl lk ll li il  ij ji"),
        (140,"human humane hammer  h n m  nh hn hm mh"),
        (160,"river ruler street  r n m t l  s e o a"),
        (180,"abcdefghijklmnopqrstuvwxyz & 0123456789")
    ] {
        c.write_reg(Register::A7,0x10000);b.write_word(0x10000,y);b.write_word(0x10002,10);d.dispatch(0xa893,&mut c,&mut b).unwrap();
        b.write_pstring(0x11000,text.as_bytes());c.write_reg(Register::A7,0x10000);b.write_long(0x10000,0x11000);d.dispatch(0xa884,&mut c,&mut b).unwrap();
    }
    // SC2K draws the status header in Geneva 9 bold, then restores plain
    // for its second line. Use that same style for the Tool comparison.
    for (op,value) in [(0xa88a,9),(0xa888,1)] {
        c.write_reg(Register::A7,0x10000);b.write_word(0x10000,value);d.dispatch(op,&mut c,&mut b).unwrap();
    }
    c.write_reg(Register::A7,0x10000);b.write_word(0x10000,210);b.write_word(0x10002,10);d.dispatch(0xa893,&mut c,&mut b).unwrap();
    b.write_pstring(0x11000,b"Centering Tool  Tool Total Town  AT TT");c.write_reg(Register::A7,0x10000);b.write_long(0x10000,0x11000);d.dispatch(0xa884,&mut c,&mut b).unwrap();
    let mut pen_trace=String::new();
    let f=fonts::get_font_face(3,9).unwrap();
    for text in ["Citizens Demand Road&Rail  Rail ail il li","Power Plant Needed"] {
        let mut x=0;
        pen_trace+=&format!("{text}\n");
        for ch in text.bytes(){
            let g=&f.glyphs[usize::from(ch-b' ')];
            pen_trace+=&format!("{} origin={} advance={} guest_left={} guest_width={}\n",ch as char,x,g.advance,g.origin_x,g.width);
            x+=u32::from(g.advance);
        }
        pen_trace+=&format!("end={x}\n");
    }
    std::fs::write(out.join("headline-placement.txt"),pen_trace).unwrap();
    let mut raw=Vec::new();
    display::render_screen_argb_with_gamma(&b,d.screen_mode,&d.device_clut,&d.device_gamma(),&mut raw);
    for (dw,dh,name) in [(440,250,"100"),(607,345,"138"),(1760,1000,"400")] {
        let mut rendered=Vec::new();b.presented_argb_resized(&raw,&raw,(dw,dh),&mut rendered).unwrap();
        image::RgbaImage::from_raw(dw,dh,rendered.iter().flat_map(|p|[(p>>16)as u8,(p>>8)as u8,*p as u8,255]).collect()).unwrap().save(out.join(format!("samples-{name}.png"))).unwrap();
    }
}

mod city {
//! Same deterministic SC2K input for all five font treatments. Diagnostic only.
use std::path::{Path,PathBuf};
use systemless::{display,game,memory::MemoryBus};
pub fn main() {
    let args:Vec<_>=std::env::args().skip(1).collect();let out=PathBuf::from(&args[2]);
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
        if frame==999 {
            std::fs::write(out.join("headline-code.bin"),r.bus().read_bytes(0x23d400,0x600)).unwrap();
            std::fs::write(out.join("headline-port.bin"),r.bus().read_bytes(0x435fe8,128)).unwrap();
        }
        let d=r.dispatcher();let mut raw=Vec::new();
        display::render_screen_argb_with_gamma(r.bus(),d.screen_mode,&d.device_clut,&d.device_gamma(),&mut raw);
        for (w,h,label) in [(800,600,"100"),(1104,828,"138")] {
            let mut pixels=Vec::new();r.bus().presented_argb_resized(&raw,&raw,(w,h),&mut pixels).unwrap();
            image::RgbaImage::from_raw(w,h,pixels.iter().flat_map(|p|[(p>>16)as u8,(p>>8)as u8,*p as u8,255]).collect()).unwrap().save(out.join(format!("{scene}-{label}.png"))).unwrap();
        }
    }
    println!("SC2K reference replay complete.");
}

}
fn main(){if std::env::args().nth(1).as_deref()==Some("--city"){city::main()}else{samples()}}
