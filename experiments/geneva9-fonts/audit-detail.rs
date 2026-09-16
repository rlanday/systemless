use skrifa::{FontRef,MetadataProvider,instance::{LocationRef,Size},outline::{OutlinePen,DrawSettings,HintingInstance,SmoothMode,Target}};
use std::hash::{Hash,Hasher};
#[derive(Default)]struct Path(Vec<zeno::Command>);
impl OutlinePen for Path{
 fn move_to(&mut self,x:f32,y:f32){self.0.push(zeno::Command::MoveTo((x,y).into()))}
 fn line_to(&mut self,x:f32,y:f32){self.0.push(zeno::Command::LineTo((x,y).into()))}
 fn quad_to(&mut self,a:f32,b:f32,x:f32,y:f32){self.0.push(zeno::Command::QuadTo((a,b).into(),(x,y).into()))}
 fn curve_to(&mut self,a:f32,b:f32,c:f32,d:f32,x:f32,y:f32){self.0.push(zeno::Command::CurveTo((a,b).into(),(c,d).into(),(x,y).into()))}
 fn close(&mut self){self.0.push(zeno::Command::Close)}
}
fn main(){
 let bytes=std::fs::read(std::env::args().nth(1).unwrap()).unwrap();let f=FontRef::new(&bytes).unwrap();
 let outlines=f.outline_glyphs();let cmap=f.charmap();println!("target,ppem,code,width,height,left,top,hash");
 for (target,ppem,name) in [(Target::Mono,9.,"guest"),(Target::from(SmoothMode::Normal),36.,"retained")]{
  let hint=HintingInstance::new(&outlines,Size::new(ppem),LocationRef::default(),target).unwrap();
  for code in 32u8..127 {
   let mut p=Path::default();outlines.get(cmap.map(code as char).unwrap()).unwrap().draw(DrawSettings::hinted(&hint,false),&mut p).unwrap();
   let mut mask=Vec::new();let placement=zeno::Mask::new(p.0.as_slice()).origin(zeno::Origin::BottomLeft).inspect(|fmt,w,h|mask.resize(fmt.buffer_size(w,h),0)).render_into(&mut mask,None);
   if name=="guest"{for m in &mut mask{*m=if *m>=128{255}else{0}}}
   if let Some(out)=std::env::args().nth(2){
    let out=std::path::PathBuf::from(out);std::fs::create_dir_all(&out).unwrap();
    let mut pgm=format!("P5\n{} {}\n255\n",placement.width,placement.height).into_bytes();
    pgm.extend_from_slice(&mask);std::fs::write(out.join(format!("{name}-{code}.pgm")),pgm).unwrap();
   }
   let mut hash=std::collections::hash_map::DefaultHasher::new();mask.hash(&mut hash);
   println!("{name},{ppem},{code},{},{},{},{},{:016x}",placement.width,placement.height,placement.left,placement.top,hash.finish());
  }
 }
}
