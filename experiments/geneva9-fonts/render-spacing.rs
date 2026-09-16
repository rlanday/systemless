use systemless::{cpu::{M68kCpu,Register},memory::{MacMemoryBus,MemoryBus},trap::TrapDispatcher,display,quickdraw::fonts};

fn main() {
    let out=std::path::PathBuf::from(std::env::args().nth(1).unwrap());
    std::fs::create_dir_all(&out).unwrap();
    let mut audit=String::new();
    for id in [1,3,21] { for size in [9,12] {
        let f=fonts::get_font_face(id,size).unwrap();
        audit+=&format!("family={id} size={size} metrics={},{},{},{} advances={:?}\n",f.metrics.ascent,f.metrics.descent,f.metrics.wid_max,f.metrics.leading,f.glyphs.iter().map(|g|g.advance).collect::<Vec<_>>());
    }}
    std::fs::write(out.join("guest-metrics.txt"),audit).unwrap();
    let mut d=TrapDispatcher::new();let mut c=M68kCpu::new();let mut b=MacMemoryBus::new(8*1024*1024);
    let (w,h)=(440u16,180u16);let base=0x400000;d.set_screen_mode_for_test(base,u32::from(w),w,h,8);
    let palette=display::rgba_palette_from_clut_with_gamma(&d.device_clut,&d.device_gamma()).map(|v| {let [r,g,b,_]=v.to_le_bytes();[r,g,b]});
    b.enable_outline_presentation(d.screen_mode,palette,4);
    c.write_reg(Register::A5,0x20000);c.write_reg(Register::A7,0x10000);b.write_long(0x10000,0x21000);d.dispatch(0xa86e,&mut c,&mut b).unwrap();
    for (op,value) in [(0xa887,3),(0xa88a,9),(0xa889,1)] {
        c.write_reg(Register::A7,0x10000);b.write_word(0x10000,value);d.dispatch(op,&mut c,&mut b).unwrap();
    }
    for (y,text) in [
        (20,"Citizens Demand Road&Rail"),
        (42,"Citizens  Citi  tizens  izens  it iz ii ti zi"),
        (64,"Demand  Demands  ma me mm mi im am"),
        (86,"Road&Rail  Road & Rail  d&R A&B P&T"),
        (108,"Power Plant Needed  little city minimum"),
        (130,"The quick brown fox jumps over the lazy dog."),
        (152,"abcdefghijklmnopqrstuvwxyz & 0123456789")
    ] {
        c.write_reg(Register::A7,0x10000);b.write_word(0x10000,y);b.write_word(0x10002,10);d.dispatch(0xa893,&mut c,&mut b).unwrap();
        b.write_pstring(0x11000,text.as_bytes());c.write_reg(Register::A7,0x10000);b.write_long(0x10000,0x11000);d.dispatch(0xa884,&mut c,&mut b).unwrap();
    }
    let mut pen_trace=String::new();
    let f=fonts::get_font_face(3,9).unwrap();
    for text in ["Citizens Demand Road&Rail","Power Plant Needed"] {
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
    for (dw,dh,name) in [(440,180,"100"),(607,248,"138"),(1760,720,"400")] {
        let mut rendered=Vec::new();b.presented_argb_resized(&raw,&raw,(dw,dh),&mut rendered).unwrap();
        image::RgbaImage::from_raw(dw,dh,rendered.iter().flat_map(|p|[(p>>16)as u8,(p>>8)as u8,*p as u8,255]).collect()).unwrap().save(out.join(format!("samples-{name}.png"))).unwrap();
    }
}
