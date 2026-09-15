//! DirectWrite rasterization of bundled outlines at the final physical size.
use super::{Layer, NativeCell};
use std::{cell::RefCell, collections::HashMap, sync::Arc};
mod directwrite;
use directwrite::DirectWrite;

struct GlyphImage {
    left: i32,
    top: i32,
    width: i32,
    height: i32,
    pixels: Vec<u32>,
}
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct Key {
    font: usize,
    glyph: u16,
    size: u32,
    phase_x: u32,
    phase_y: u32,
    foreground: u32,
    background: u32,
}
pub(super) struct Renderer {
    backend: DirectWrite,
    cache: HashMap<Key, Option<Arc<GlyphImage>>>,
    cache_pixels: usize,
    glyph_renders: u64,
    cache_clears: u64,
    profile: bool,
}
thread_local! { static RENDERER: RefCell<Option<Renderer>> = RefCell::new(Renderer::load()); }
pub(super) fn with_renderer(mut run: impl FnMut(&mut Renderer)) {
    RENDERER.with(|slot| {
        if let Some(renderer) = slot.borrow_mut().as_mut() {
            let before = (renderer.glyph_renders, renderer.cache_clears);
            run(renderer);
            if renderer.profile {
                eprintln!("[NATIVE-TEXT] glyph_renders={} cache_clears={} cached_glyphs={} cached_pixels={}",
                    renderer.glyph_renders - before.0, renderer.cache_clears - before.1,
                    renderer.cache.len(), renderer.cache_pixels);
            }
        }
    });
}
fn argb(rgb: [u8; 3]) -> u32 {
    0xff000000 | (u32::from(rgb[0]) << 16) | (u32::from(rgb[1]) << 8) | u32::from(rgb[2])
}
impl Renderer {
    fn load() -> Option<Self> {
        let backend = match DirectWrite::new() {
            Ok(backend) => backend,
            Err(error) => {
                eprintln!("DirectWrite unavailable; retaining outline pixels: {error}");
                return None;
            }
        };
        Some(Self {
            backend,
            cache: HashMap::new(),
            cache_pixels: 0,
            glyph_renders: 0,
            cache_clears: 0,
            profile: std::env::var_os("SYSTEMLESS_PROFILE_RENDER_PHASES").is_some(),
        })
    }
    fn pixel(
        &mut self,
        layer: &Layer,
        foreground: u32,
        background: u32,
        cell: (u32, u32),
        pixel: (usize, usize),
        scale: (f64, f64),
    ) -> Option<u32> {
        let bx = (f64::from(cell.0) + f64::from(layer.dx)) * scale.0;
        let by = (f64::from(cell.1) + f64::from(layer.dy)) * scale.1;
        let size = (f64::from(layer.source.size) * scale.0.min(scale.1)) as f32;
        let phase_x = (bx - bx.floor()) as f32;
        let phase_y = (by - by.floor()) as f32;
        let key = Key {
            font: layer.source.bytes.as_ptr() as usize,
            glyph: u16::try_from(layer.source.id.to_u32()).ok()?,
            size: size.to_bits(),
            phase_x: phase_x.to_bits(),
            phase_y: phase_y.to_bits(),
            foreground,
            background,
        };
        if let Some(image) = self.cache.get(&key) {
            return image
                .as_ref()
                .map(|image| Self::sample(image, pixel, (bx, by), background));
        }
        {
            if self.cache.len() >= 2048 || self.cache_pixels > 8 * 1024 * 1024 {
                self.cache.clear();
                self.cache_pixels = 0;
                self.cache_clears += 1;
            }
            self.glyph_renders += 1;
            let cached = match self.backend.render(
                layer.source.bytes,
                key.glyph,
                size,
                phase_x,
                phase_y,
                foreground,
                background,
            ) {
                Ok(image) => {
                    self.cache_pixels += image.pixels.len();
                    Some(Arc::new(image))
                }
                Err(error) => {
                    eprintln!("DirectWrite glyph render failed: {error}");
                    None
                }
            };
            let color = cached
                .as_ref()
                .map(|image| Self::sample(image, pixel, (bx, by), background));
            self.cache.insert(key, cached);
            color
        }
    }
    fn sample(
        image: &GlyphImage,
        pixel: (usize, usize),
        baseline: (f64, f64),
        background: u32,
    ) -> u32 {
        let x = pixel.0 as i32 - baseline.0.floor() as i32 - image.left;
        let y = pixel.1 as i32 - baseline.1.floor() as i32 - image.top;
        if x < 0 || y < 0 || x >= image.width || y >= image.height {
            background
        } else {
            image.pixels[(y * image.width + x) as usize]
        }
    }
    pub(super) fn cell_pixel(
        &mut self,
        cell: &NativeCell,
        palette: &[[u8; 3]; 256],
        position: (u32, u32),
        pixel: (usize, usize),
        scale: (f64, f64),
    ) -> Option<u32> {
        let mut background = argb(palette[cell.background as usize]);
        let mut index = 0;
        while index < cell.layers.len() {
            let fg = cell.layers[index].foreground;
            let foreground = argb(palette[fg as usize]);
            let base = background;
            // Same indexed ink uses the strongest coverage, matching srcOr's
            // idempotence instead of darkening a repeated antialiased edge.
            while index < cell.layers.len() && cell.layers[index].foreground == fg {
                let color = self.pixel(
                    &cell.layers[index],
                    foreground,
                    base,
                    position,
                    pixel,
                    scale,
                )?;
                for shift in [0, 8, 16] {
                    let old = (background >> shift) & 255;
                    let next = (color >> shift) & 255;
                    let value = if ((foreground >> shift) & 255) < ((base >> shift) & 255) {
                        old.min(next)
                    } else {
                        old.max(next)
                    };
                    background = (background & !(255 << shift)) | (value << shift);
                }
                index += 1;
            }
        }
        Some(background)
    }
}
