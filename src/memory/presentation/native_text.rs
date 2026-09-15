//! Opt-in experiment: retain glyph sources for final-resolution Windows text.
//! Unsupported drawing combinations keep the existing retained pixel renderer.
use super::*;
use crate::quickdraw::fonts::outline::Source;

#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct Layer {
    pub source: Source,
    pub dx: i32,
    pub dy: i32,
    pub foreground: u8,
    pub run: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) struct NativeCell {
    pub background: u8,
    pub layers: Vec<Layer>,
}
impl NativeCell {
    pub fn map(&mut self, map: &mut impl FnMut(u8) -> u8) {
        self.background = map(self.background);
        for layer in &mut self.layers {
            layer.foreground = map(layer.foreground);
        }
    }
    fn paint(&mut self, layer: Layer) -> bool {
        // Repeated same-color srcOr ink is idempotent. Keep different-color
        // layers in drawing order; only coalesce within the final color group.
        for previous in self.layers.iter_mut().rev() {
            if previous.foreground != layer.foreground {
                break;
            }
            if previous.source == layer.source && previous.dx == layer.dx && previous.dy == layer.dy
            {
                previous.run = layer.run;
                return true;
            }
        }
        if self.layers.len() == 32 {
            return false;
        }
        self.layers.push(layer);
        true
    }
    fn erase(&mut self, value: u8, run: Option<u64>) {
        self.background = value;
        self.layers.retain(|layer| Some(layer.run) == run);
    }
}

impl Presentation {
    pub(super) fn record_native_glyph(
        &mut self,
        address: u32,
        x: i16,
        y: i16,
        foreground: u8,
        background: u8,
    ) {
        if !self.native_enabled {
            return;
        }
        let Some((source, h, v)) = self.native_source else {
            self.set_native_cell(address, None);
            return;
        };
        let native = self.native_cell(address).or_else(|| {
            // Existing native sources already describe the background. Avoid
            // constructing a retained pixel snapshot just to discard it.
            let previous = self.detail(address);
            let background = if let Some(cell) = previous.as_deref() {
                let first = *cell.indices.first()?;
                if !cell.ink.is_empty() || cell.indices.iter().any(|&value| value != first) {
                    return None;
                }
                first
            } else {
                background
            };
            Some(Arc::new(NativeCell {
                background,
                layers: Vec::new(),
            }))
        });
        let Some(mut native) = native else {
            self.set_native_cell(address, None);
            return;
        };
        if !Arc::make_mut(&mut native).paint(Layer {
            source,
            dx: i32::from(h) - i32::from(x),
            dy: i32::from(v) - i32::from(y),
            foreground,
            run: self.native_run,
        }) {
            self.set_native_cell(address, None);
            return;
        }
        // Offscreen glyph cells can exist before the guest writes their 1x ink.
        if self.position(address).is_none() {
            self.include_offscreen_address(address);
            self.offscreen.entry(address).or_insert_with(|| {
                Arc::new(DetailCell {
                    value: background,
                    indices: vec![background; (self.scale * self.scale) as usize],
                    ink: HashMap::new(),
                    native: None,
                })
            });
        }
        self.set_native_cell(address, Some(native));
    }
    fn native_cell(&self, address: u32) -> Option<Arc<NativeCell>> {
        if self.position(address).is_some() {
            self.native_cells.get(&address).cloned()
        } else {
            self.offscreen
                .get(&address)
                .and_then(|cell| cell.native.clone())
        }
    }
    fn set_native_cell(&mut self, address: u32, native: Option<Arc<NativeCell>>) {
        if let Some((x, y)) = self.position(address) {
            match native {
                Some(cell) => {
                    self.native_cells.insert(address, cell);
                }
                None => {
                    self.native_cells.remove(&address);
                }
            }
            self.detail_cache.get_mut()[(y * self.width + x) as usize] = None;
        } else if let Some(cell) = self.offscreen.get_mut(&address) {
            Arc::make_mut(cell).native = native;
        }
    }
    pub(super) fn native_write(&mut self, address: u32, value: u8) {
        if !self.native_enabled || self.glyph.is_some() {
            return;
        }
        let Some(mut native) = self.native_cell(address) else {
            return;
        };
        let run = (self.erasing_text && self.in_text_run).then_some(self.native_run);
        // Ordinary stores erase all sources. Drop the shared record directly
        // instead of cloning its layers through Arc::make_mut before erasing
        // them; composition makes this a frequent operation.
        if !native.layers.iter().any(|layer| Some(layer.run) == run) {
            self.set_native_cell(address, None);
            return;
        }
        if native.background == value && native.layers.iter().all(|layer| Some(layer.run) == run) {
            return;
        }
        Arc::make_mut(&mut native).erase(value, run);
        if native.layers.is_empty() {
            self.set_native_cell(address, None);
        } else {
            self.set_native_cell(address, Some(native));
        }
    }
}

impl DetailCell {
    pub(super) fn map_native(&mut self, map: &mut impl FnMut(u8) -> u8) {
        if let Some(native) = &mut self.native {
            Arc::make_mut(native).map(map);
        }
    }
}

#[cfg(target_os = "windows")]
mod windows;

#[cfg(target_os = "windows")]
impl MacMemoryBus {
    /// Experimental final-size presentation only. Guest bytes are never changed.
    #[doc(hidden)]
    pub fn overlay_native_text(
        &self,
        guest: &[u32],
        overlays: &[u32],
        viewport: (usize, usize, usize, usize),
        stride: usize,
        output: &mut [u32],
    ) {
        let Some(p) = self.presentation.as_ref() else {
            return;
        };
        if !p.native_enabled
            || guest.len() != (p.width * p.height) as usize
            || overlays.len() != guest.len()
        {
            return;
        }
        let (left, top, width, height) = viewport;
        if width == 0
            || height == 0
            || left + width > stride
            || (top + height) * stride > output.len()
        {
            return;
        }
        let sx = width as f64 / p.width as f64;
        let sy = height as f64 / p.height as f64;
        windows::with_renderer(|renderer| {
            for (&address, cell) in &p.native_cells {
                let Some((x, y)) = p.position(address) else {
                    continue;
                };
                let logical = (y * p.width + x) as usize;
                if guest[logical] != overlays[logical] {
                    continue;
                }
                let x0 = (f64::from(x) * sx - 0.5).ceil().max(0.0) as usize;
                let x1 = ((f64::from(x) + 1.0) * sx - 0.5)
                    .ceil()
                    .max(0.0)
                    .min(width as f64) as usize;
                let y0 = (f64::from(y) * sy - 0.5).ceil().max(0.0) as usize;
                let y1 = ((f64::from(y) + 1.0) * sy - 0.5)
                    .ceil()
                    .max(0.0)
                    .min(height as f64) as usize;
                for py in y0..y1 {
                    for px in x0..x1 {
                        if let Some(color) =
                            renderer.cell_pixel(cell, &p.palette, (x, y), (px, py), (sx, sy))
                        {
                            output[(top + py) * stride + left + px] = color;
                        }
                    }
                }
            }
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn offscreen_native_edge_is_visible_to_snapshots_and_cpu_invalidation() {
        let mut bus = super::super::tests::bus();
        bus.write_byte(0x1800, 255);
        let (glyph, _) = crate::quickdraw::text::get_glyph(3, 9, 'p').unwrap();
        let source = crate::quickdraw::fonts::outline::source(glyph).unwrap();
        {
            let mut p = bus.presentation.as_mut().unwrap();
            p.native_enabled = true;
            p.native_source = Some((source, 0, 7));
            // A native edge can exist before a write of the legacy glyph ink.
            p.record_native_glyph(0x1800, 0, 0, 0, 255);
        }
        let saved = bus.save_pixel_bytes(0x1800, 1);
        assert!(saved.detail.get(&0).unwrap().native.is_some());
        bus.write_byte(0x1800, 200);
        assert!(bus
            .presentation
            .as_ref()
            .unwrap()
            .native_cell(0x1800)
            .is_none());
    }
    #[test]
    fn guest_cpu_recolor_preserves_native_sources_but_ordinary_writes_invalidate_them() {
        let mut bus = super::super::tests::bus();
        bus.write_byte(0x1001, 0);
        let (glyph, _) = crate::quickdraw::text::get_glyph(3, 9, 'A').unwrap();
        let source = crate::quickdraw::fonts::outline::source(glyph).unwrap();
        {
            let mut p = bus.presentation.as_mut().unwrap();
            p.native_enabled = true;
            p.prepare_text_cell(0, 0);
            p.native_cells.insert(
                0x1000,
                Arc::new(NativeCell {
                    background: 255,
                    layers: vec![Layer {
                        source,
                        dx: 0,
                        dy: 7,
                        foreground: 0,
                        run: 1,
                    }],
                }),
            );
        }
        bus.begin_cpu_drawing();
        bus.write_byte(0x1000, 200);
        bus.write_byte(0x1001, 0);
        bus.end_cpu_drawing(true);
        {
            let p = bus.presentation.as_ref().unwrap();
            let cell = p.native_cells.get(&0x1000).unwrap();
            assert_eq!(cell.background, 200);
            assert_eq!(cell.layers[0].foreground, 0);
            assert!(cell.layers[0].source == source);
        }
        bus.write_byte(0x1000, 200);
        assert!(!bus
            .presentation
            .as_ref()
            .unwrap()
            .native_cells
            .contains_key(&0x1000));
    }
    #[test]
    fn snapshots_preserve_native_edges_outside_the_legacy_mask() {
        let mut bus = super::super::tests::bus();
        let (glyph, _) = crate::quickdraw::text::get_glyph(3, 9, 'W').unwrap();
        let source = crate::quickdraw::fonts::outline::source(glyph).unwrap();
        {
            let mut p = bus.presentation.as_mut().unwrap();
            p.native_enabled = true;
            p.in_text_run = true;
            p.erasing_text = true;
            p.native_run = 9;
            p.text_cells[0] = true;
            p.native_cells.insert(
                0x1000,
                Arc::new(NativeCell {
                    background: 255,
                    layers: vec![Layer {
                        source,
                        dx: 1,
                        dy: 7,
                        foreground: 0,
                        run: 9,
                    }],
                }),
            );
        }
        bus.write_byte(0x1000, 255);
        let saved = bus.save_pixel_bytes(0x1000, 1);
        assert!(saved.detail.get(&0).unwrap().native.is_some());
        // A saved offscreen cell must survive the same opaque-background case.
        bus.restore_saved_pixels(0x1800, &saved, 0, 1);
        bus.write_byte(0x1800, 200);
        let offscreen = bus.save_pixel_bytes(0x1800, 1);
        let cell = offscreen.detail.get(&0).unwrap().native.as_ref().unwrap();
        assert_eq!(cell.background, 200);
        assert_eq!(cell.layers.len(), 1);
    }
    #[test]
    fn same_ink_repaint_is_bounded_and_opaque_erase_keeps_only_current_run() {
        let (glyph, _) = crate::quickdraw::text::get_glyph(3, 9, 'A').unwrap();
        let source = crate::quickdraw::fonts::outline::source(glyph).unwrap();
        let mut cell = NativeCell {
            background: 255,
            layers: Vec::new(),
        };
        for run in 0..1000 {
            assert!(cell.paint(Layer {
                source,
                dx: 0,
                dy: 7,
                foreground: 0,
                run
            }));
        }
        assert_eq!(cell.layers.len(), 1);
        cell.erase(200, Some(999));
        assert_eq!(cell.layers.len(), 1);
        cell.map(&mut |value| !value);
        assert_eq!(cell.background, 55);
        assert_eq!(cell.layers[0].foreground, 255);
        cell.erase(100, Some(1000));
        assert!(cell.layers.is_empty());
    }
}
