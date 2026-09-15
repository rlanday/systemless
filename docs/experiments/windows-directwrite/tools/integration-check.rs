use systemless::{cpu::{M68kCpu,Register},memory::{MacMemoryBus,MemoryBus},trap::TrapDispatcher,display};
use std::path::Path;
fn render(b:&MacMemoryBus,d:&TrapDispatcher,pct:u32)->(Vec<u32>,Vec<u32>) {
 let (w,h)=(200u32,48u32);let size=(w*pct/100,h*pct/100);
 let mut raw=Vec::new();display::render_screen_argb_with_gamma(b,d.screen_mode,&d.device_clut,&d.device_gamma(),&mut raw);
 let mut full=Vec::new();let scale=display::outline_output_scale((w,h),size);
 let source_size=b.presented_argb_scaled(&raw,&raw,scale,&mut full).unwrap();
 let mut current=Vec::new();display::resize_argb_coverage(&full,source_size,size,&mut current);
 let mut native=current.clone();b.overlay_native_text(&raw,&raw,(0,0,size.0 as usize,size.1 as usize),size.0 as usize,&mut native);
 (current,native)
}
fn save(path:&Path,pct:u32,pixels:&[u32]) {
 let mut im=image::RgbaImage::new(200*pct/100,48*pct/100);
 for (dst,p) in im.pixels_mut().zip(pixels){*dst=image::Rgba([(p>>16)as u8,(p>>8)as u8,*p as u8,255]);}
 im.save(path).unwrap();
}
fn main(){
 let out=std::path::PathBuf::from(std::env::args().nth(1).unwrap());std::fs::create_dir_all(&out).unwrap();
 for (font,size) in [(3,9),(3,11),(3,12),(0,12)] { for mode in [0,1] {
  let out=out.join(format!("font{font}-size{size}")); std::fs::create_dir_all(&out).unwrap();
  let widths:Vec<u8>=(32u8..127).map(|ch|systemless::quickdraw::text::get_glyph(font,size,ch as char).unwrap().0.advance as u8).collect(); std::fs::write(out.join("advances.bin"),widths).unwrap();
  let mut d=TrapDispatcher::new();let mut c=M68kCpu::new();let mut b=MacMemoryBus::new(8*1024*1024);
  let base=0x400000;let len=200*48;d.set_screen_mode_for_test(base,200,200,48,8);
  let palette=display::rgba_palette_from_clut_with_gamma(&d.device_clut,&d.device_gamma()).map(|v|{let [r,g,b,_]=v.to_le_bytes();[r,g,b]});
  b.enable_outline_presentation(d.screen_mode,palette,4);
  c.write_reg(Register::A5,0x20000);c.write_reg(Register::A7,0x10000);b.write_long(0x10000,0x21000);d.dispatch(0xa86e,&mut c,&mut b).unwrap();
  for (op,value) in [(0xa887,font as u16),(0xa88a,size as u16),(0xa889,mode)]{c.write_reg(Register::A7,0x10000);b.write_word(0x10000,value);d.dispatch(op,&mut c,&mut b).unwrap();}
  for (y,text) in [(18,"Speed Options Disasters"),(36,"Newspaper ppp aaa sss")] {
   c.write_reg(Register::A7,0x10000);b.write_word(0x10000,y);b.write_word(0x10002,10);d.dispatch(0xa893,&mut c,&mut b).unwrap();
   b.write_pstring(0x11000,text.as_bytes());c.write_reg(Register::A7,0x10000);b.write_long(0x10000,0x11000);d.dispatch(0xa884,&mut c,&mut b).unwrap();
  }
  let guest=b.read_bytes(base,len as usize);let (legacy,baseline)=render(&b,&d,100);
  assert!(legacy.iter().zip(&baseline).filter(|(a,b)|a!=b).count()>50,"Native renderer did not replace legacy text");
  let colored=baseline.iter().filter(|&&p| ((p>>16)&255)!=((p>>8)&255)||((p>>8)&255)!=(p&255)).count();
  let selected=std::env::var_os("SYSTEMLESS_CHECK_SELECTED").is_some();
  let grayscale=if selected {size<12} else {std::env::var("SYSTEMLESS_CLEARTYPE_LEVEL").ok().and_then(|v|v.parse::<f32>().ok())==Some(0.0)};
  if grayscale {assert_eq!(colored,0,"Grayscale rendered colored fringes");}
  else {assert!(colored>50,"ClearType did not produce RGB coverage: {colored}");}
  for pct in [99,100,125,133,134,150,175,200,250,300,400] {
   let (current,native)=render(&b,&d,pct);
   let physical=size as f64*((200*pct/100)as f64/200.0).min((48*pct/100)as f64/48.0);
   let expect_gray=if selected {physical<12.0} else {grayscale};
   let rgb_pixels=native.iter().filter(|&&p| ((p>>16)&255)!=((p>>8)&255)||((p>>8)&255)!=(p&255)).count();
   if expect_gray {assert_eq!(rgb_pixels,0,"Colored pixels below selected threshold: font={font} size={size} pct={pct} physical={physical}");}
   else {assert!(rgb_pixels>50,"Missing subpixel rendering: font={font} size={size} pct={pct} physical={physical}");}
   save(&out.join(format!("mode{mode}-current-{pct}.png")),pct,&current);
   save(&out.join(format!("mode{mode}-cleartype-{pct}.png")),pct,&native);
  }
  assert!(render(&b,&d,100).1==baseline,"Resize round-trip changed unchanged text");
  assert_eq!(b.read_bytes(base,len as usize),guest,"Presentation changed guest bytes");
  assert!(b.copy_ram_bytes(base,0x500000,len));b.fill_bytes(base,len,0);
  assert!(b.copy_ram_bytes(0x500000,base,len));
  let restored=render(&b,&d,100).1;save(&out.join(format!("mode{mode}-restored-100.png")),100,&restored);
  assert!(restored==baseline,"Saved/offscreen copy lost native glyph sources: {} pixels",restored.iter().zip(&baseline).filter(|(a,b)|a!=b).count());
  let inverted=std::array::from_fn(|i|!(i as u8));
  assert!(b.copy_mapped_ram_bytes(base,base,len,&inverted));
  let (_,inverse)=render(&b,&d,125);save(&out.join(format!("mode{mode}-inverted-125.png")),125,&inverse);
  assert!(b.copy_mapped_ram_bytes(base,base,len,&inverted));
  assert!(render(&b,&d,100).1==baseline,"Indexed recolor round-trip changed text");
  assert_eq!(b.read_bytes(base,len as usize),guest);
  println!("font={font} size={size} mode={mode}: {colored} RGB-separated pixels; resize, saved/offscreen copy, indexed recolor, and guest-byte checks passed");
 }
 }
}
