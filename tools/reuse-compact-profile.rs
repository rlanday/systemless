use systemless::game;
use std::path::PathBuf;
use systemless::runner::FixtureRunner;
const SOUND_CALLBACK_RESERVED_INSTRUCTIONS_PER_FRAME: usize = 25_000;
const SOUND_CALLBACK_SLICE_INSTRUCTIONS: usize = 10_000;
const AUDIO_CALLBACK_CHUNK_SAMPLES: usize = 32;
const FRAME_DURATION: std::time::Duration=std::time::Duration::from_micros(16_625);
fn service_pending_sound_work_budgeted(
    runner: &mut FixtureRunner,
    slice_budget: usize,
    total_steps: usize,
    reserved_sound_steps: &mut usize,
) -> Option<usize> {
    if !runner.has_pending_sound_work() || runner.is_halted() {
        return None;
    }

    // Double-buffer callbacks are Sound Manager interrupt work, not foreground
    // application execution. Give them reserved time even when the GUI frame
    // has spent its foreground budget, but cap that reserve per host frame so
    // audio refills cannot monopolize the single-threaded event loop.
    let remaining = slice_budget.saturating_sub(total_steps);
    let using_reserved_slice = remaining == 0;
    let callback_budget = if using_reserved_slice {
        let reserved_remaining =
            SOUND_CALLBACK_RESERVED_INSTRUCTIONS_PER_FRAME.saturating_sub(*reserved_sound_steps);
        if reserved_remaining == 0 {
            return None;
        }
        reserved_remaining.min(SOUND_CALLBACK_SLICE_INSTRUCTIONS)
    } else {
        remaining.min(SOUND_CALLBACK_SLICE_INSTRUCTIONS)
    };

    // This slice services audio interrupts, not a presentation frame. The
    // outer presentation pass restores native chrome once.
    let (steps, _running) = runner.run_gui_pending_sound_work(callback_budget);
    if using_reserved_slice {
        *reserved_sound_steps = reserved_sound_steps.saturating_add(steps);
    }
    Some(steps)
}

#[derive(Debug, Default)]
struct FrameWork {
    instructions: usize,
    foreground: usize,
    budget_exhausted: bool,
}

fn service_sound(runner: &mut FixtureRunner, total: &mut usize, reserve_used: &mut usize) {
    if let Some(steps) = service_pending_sound_work_budgeted(
        runner,
        game::MAX_INSTRUCTIONS_PER_FRAME,
        *total,
        reserve_used,
    ) {
        *total = total.saturating_add(steps);
    }
}

/// One virtual frontend tick. The frontend clock keeps moving while a menu
/// freezes guest TickCount, just as the real host clock and audio do. A short
/// retained-tracking slice is a yield boundary, not an invitation to re-fire
/// the same wait. Other short slices can be ordinary engine/task handoffs.
fn frame(runner: &mut FixtureRunner, audio_samples: usize) -> FrameWork {
    if runner.debug_is_paused() {
        return FrameWork::default();
    }
    runner.advance_menu_presentation_clock(FRAME_DURATION);
    let target = runner.guest_tick().saturating_add(1);
    let batch = 10_000;
    let mut work = FrameWork::default();
    let mut audio_mixed = 0;
    let mut reserve_used = 0;
    while work.instructions < game::MAX_INSTRUCTIONS_PER_FRAME && !runner.is_halted() {
        let remaining = game::MAX_INSTRUCTIONS_PER_FRAME - work.instructions;
        let requested = batch.min(remaining);
        let batches_left = remaining.div_ceil(batch).max(1);
        let batch_audio = (audio_samples - audio_mixed).div_ceil(batches_left);
        // Match the desktop's deferred presentation: CPU batches do not
        // repaint chrome. Audio still runs between batches, including its
        // guest callbacks; the frame's presentation pass follows below.
        let (steps, running) = runner.run_gui_cpu_slice(requested, target);
        work.foreground += steps;
        work.instructions += steps;
        audio_mixed += batch_audio;
        if batch_audio > 0 {
            runner.mix_gui_audio_slice(batch_audio);
            service_sound(runner, &mut work.instructions, &mut reserve_used);
        }
        if !running
            || runner.guest_tick() >= target
            || steps == 0
            || runner.is_ui_tracking_active()
        {
            break;
        }
    }
    work.budget_exhausted =
        work.instructions >= game::MAX_INSTRUCTIONS_PER_FRAME && runner.guest_tick() < target;

    // Audio is driven by frontend time even when guest ticks are frozen.
    // Mix in the same bounded chunks used by the GUI, giving double-buffer
    // callbacks an opportunity to refill between chunks. No host device is
    // attached, but guest-visible playback and callback work still executes.
    let mut remaining_audio = audio_samples - audio_mixed;
    if remaining_audio > 0 {
        service_sound(runner, &mut work.instructions, &mut reserve_used);
    }
    while remaining_audio > 0 && !runner.is_halted() {
        let chunk = remaining_audio.min(AUDIO_CALLBACK_CHUNK_SAMPLES);
        runner.mix_gui_audio_slice(chunk);
        remaining_audio -= chunk;
        service_sound(runner, &mut work.instructions, &mut reserve_used);
    }
    service_sound(runner, &mut work.instructions, &mut reserve_used);
    work
}


use systemless::cpu::Register;
use std::fmt::Write;

fn capture(r:&mut FixtureRunner,out:&std::path::Path,name:&str){
 let mut pixels=Vec::new();let d=r.dispatcher();let gamma=d.device_gamma();
 systemless::display::render_screen_argb_with_gamma(r.bus(),d.screen_mode,&d.device_clut,&gamma,&mut pixels);
 let mut presented=Vec::new();
 let(w,h)=r.bus().presented_argb_scaled(&pixels,&pixels,1,&mut presented).unwrap();
 image::RgbaImage::from_raw(w,h,presented.iter().flat_map(|p|[(p>>16)as u8,(p>>8)as u8,*p as u8,255]).collect()).unwrap().save(out.join(format!("{name}.png"))).unwrap();
}
#[link(name="kernel32")]
extern "system" { fn QueryPerformanceCounter(counter: *mut i64) -> i32; }
fn qpc() -> i64 { let mut value=0; unsafe { assert_ne!(QueryPerformanceCounter(&mut value),0); } value }
fn main(){
 let args:Vec<_>=std::env::args().collect();let out=PathBuf::from(&args[2]);std::fs::create_dir_all(&out).unwrap();
 let mut r=game::new_runner();r.set_app_start_time(3_871_497_600);
 let app=game::load_game_from_path(&mut r,std::path::Path::new(&args[1])).unwrap();game::init_game(&mut r,&app);
 r.prepare_text_presentation();r.set_instructions_per_tick(415_628);
 let mut rows=String::from("frame,cpu_ms,prepare_ms,compose_ms,argb_ms,export_ms,finish_ms,instructions,foreground,tick,pc,total_instructions,gne,tracking\n");
 let mut phases=String::from("frame,cpu_start,cpu_end,prepare_end,compose_end,argb_end,export_end,finish_end\n");
 let mut logical=Vec::new();
 #[cfg(not(cache_compact_export))]
 let mut compact=systemless::memory::CompactPresentation::default();
 #[cfg(cache_compact_export)]
 let mut cache=systemless::memory::CompactPresentationCache::default();
 let mut audio_remainder=0.;let mut audio_discard=Vec::new();let mut fire_pending=false;
 let fire=std::env::var_os("PROFILE_FIRE").is_some();
 let mut metadata=serde_json::json!({"fire":fire,"ram_bytes":r.bus().ram_size()});
 for elapsed in 0..2500 {
  match elapsed {
   60|150|240|320|700|780=>{r.push_key_down(0x24,13);r.push_key_up(0x24,13);},
   120=>{for ch in b"Systemless Test" {r.push_key_down(0,*ch);r.push_key_up(0,*ch);}},
   1000 if fire=>{r.push_mouse_down(9,208);fire_pending=true;},
   1150|1250 if fire=>{r.push_key_down(0x24,13);r.push_key_up(0x24,13);},_=>{}
  }
  let samples=FRAME_DURATION.as_secs_f64().mul_add(systemless::sound::OUTPUT_RATE as f64,audio_remainder);
  let n=samples.floor()as usize;audio_remainder=samples-n as f64;
  let p0=qpc();let start=std::time::Instant::now();let work=frame(&mut r,n);let cpu=start.elapsed().as_secs_f64()*1000.;let p1=qpc();
  r.drain_audio_into(&mut audio_discard);
  let start=std::time::Instant::now();r.prepare_text_presentation();let prepare=start.elapsed().as_secs_f64()*1000.;let p2=qpc();
  let start=std::time::Instant::now();r.composite_frame();let compose=start.elapsed().as_secs_f64()*1000.;let p3=qpc();
  let start=std::time::Instant::now();let has_detail=r.bus().has_visible_outline_detail();let no_overlays=cfg!(skip_logical_export)&&has_detail;
  let overlay=if no_overlays {Vec::new()}else{systemless::display::render_screen_argb_with_gamma(r.bus(),r.dispatcher().screen_mode,&r.dispatcher().device_clut,&r.dispatcher().device_gamma(),&mut logical);logical.clone()};let argb=start.elapsed().as_secs_f64()*1000.;let pa=qpc();
  let start=std::time::Instant::now();
  #[cfg(all(skip_logical_export, not(cache_compact_export)))]
  let exported=if no_overlays {let (_,_,w,h,_)=r.dispatcher().screen_mode;r.bus().compact_presentation_without_overlays((u32::from(w),u32::from(h)),&mut compact)}else{r.bus().compact_presentation(&logical,&overlay,&mut compact)};
  #[cfg(not(skip_logical_export))]
  let exported=r.bus().compact_presentation(&logical,&overlay,&mut compact);
  #[cfg(cache_compact_export)]
  let exported=if no_overlays {let (_,_,w,h,_)=r.dispatcher().screen_mode;cache.prepare(r.bus(),(u32::from(w),u32::from(h)))}else{r.bus().compact_presentation(&logical,&overlay,cache.frame_mut())};
  #[cfg(cache_compact_export)]
  let compact=cache.frame();
  #[cfg(verify_compact_cache)]
  {
   let mut fresh=systemless::memory::CompactPresentation::default();
   let (_,_,w,h,_)=r.dispatcher().screen_mode;
   let expected=if no_overlays {r.bus().compact_presentation_without_overlays((u32::from(w),u32::from(h)),&mut fresh)}else{r.bus().compact_presentation(&logical,&overlay,&mut fresh)};
   assert!(expected);
   assert_eq!((compact.width,compact.height,compact.scale),(fresh.width,fresh.height,fresh.scale),"frame {elapsed}");
   assert_eq!(compact.cells,fresh.cells,"cells frame {elapsed}");
   assert_eq!(compact.detail,fresh.detail,"detail frame {elapsed}");
  }
  assert!(exported);let export=start.elapsed().as_secs_f64()*1000.;let pe=qpc();
  let start=std::time::Instant::now();r.finish_gui_frame();let finish=start.elapsed().as_secs_f64()*1000.;let p4=qpc();
  writeln!(phases,"{elapsed},{p0},{p1},{p2},{p3},{pa},{pe},{p4}").unwrap();
  writeln!(rows,"{elapsed},{cpu:.6},{prepare:.6},{compose:.6},{argb:.6},{export:.6},{finish:.6},{},{},{},{:08x},{},{},{}",work.instructions,work.foreground,r.guest_tick(),r.cpu().read_reg(Register::PC),r.total_instructions(),r.dispatcher().debug_get_next_event_count,r.is_ui_tracking_active()).unwrap();
  if fire_pending && r.is_ui_tracking_active(){r.set_mouse_position(27,200);r.push_mouse_up(27,200);fire_pending=false;}
  if [999,1499,1999,2499].contains(&elapsed){
   std::fs::write(out.join(format!("frame-{elapsed}.ram")),r.bus().ram_slice(0,r.bus().ram_size())).unwrap();
   let registers=[Register::D0,Register::D1,Register::D2,Register::D3,Register::D4,Register::D5,Register::D6,Register::D7,Register::A0,Register::A1,Register::A2,Register::A3,Register::A4,Register::A5,Register::A6,Register::A7,Register::PC].map(|reg|r.cpu().read_reg(reg));
   std::fs::write(out.join(format!("frame-{elapsed}.registers.json")),serde_json::to_string(&serde_json::json!({"integer":registers,"extended":format!("{:?}",systemless::cpu::CpuOps::capture_extended_context(r.cpu()))})).unwrap()).unwrap();
   capture(&mut r,&out,&format!("frame-{elapsed}"));
   let mut transport=Vec::new();
   for word in [compact.width,compact.height,compact.scale,compact.cells.len()as u32,compact.detail.len()as u32].into_iter().chain(compact.cells.iter().copied()).chain(compact.detail.iter().copied()){transport.extend_from_slice(&word.to_le_bytes());}
   std::fs::write(out.join(format!("frame-{elapsed}.compact")),transport).unwrap();
   if elapsed==999{metadata["addressing_32_bit"]=r.bus().addressing_32_bit().into();metadata["tracked_window"]=m68k::AddressBus::tracked_mem(r.bus_mut()).is_some().into();}
  }
  if r.is_halted(){metadata["halted_frame"]=elapsed.into();break;}
 }
 std::fs::write(out.join("phases.csv"),phases).unwrap();
 std::fs::write(out.join("frames.csv"),rows).unwrap();
 std::fs::write(out.join("metadata.json"),serde_json::to_string_pretty(&metadata).unwrap()).unwrap();
}
