//! Windows owns gamma/contrast and glyph rasterization; QuickDraw owns layout.
use super::GlyphImage;
use std::{
    collections::HashMap,
    mem::{size_of, ManuallyDrop},
};
use windows::{
    core::{IUnknown, Interface, Result},
    Win32::{
        Foundation::{BOOL, COLORREF, E_FAIL, E_INVALIDARG},
        Graphics::{DirectWrite::*, Gdi::*},
    },
};

struct RegisteredLoader {
    factory: IDWriteFactory5,
    loader: IDWriteInMemoryFontFileLoader,
}
impl Drop for RegisteredLoader {
    fn drop(&mut self) {
        // All font faces are released before their loader is unregistered.
        unsafe {
            let _ = self.factory.UnregisterFontFileLoader(&self.loader);
        }
    }
}
struct GlyphRun(DWRITE_GLYPH_RUN);
impl Drop for GlyphRun {
    fn drop(&mut self) {
        // The generated ABI struct suppresses automatic COM-field destruction.
        unsafe {
            ManuallyDrop::drop(&mut self.0.fontFace);
        }
    }
}

pub(super) struct DirectWrite {
    faces: HashMap<(usize, usize), IDWriteFontFace2>,
    registered: RegisteredLoader,
    interop: IDWriteGdiInterop,
    gray: IDWriteRenderingParams2,
    subpixel: IDWriteRenderingParams2,
}
impl Drop for DirectWrite {
    fn drop(&mut self) {
        self.faces.clear();
    }
}
impl DirectWrite {
    pub(super) fn new() -> Result<Self> {
        // Factory5 is queried at runtime; unsupported Windows versions keep
        // the existing retained outline pixels instead of failing game load.
        unsafe {
            let factory: IDWriteFactory5 = DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED)?;
            let loader = factory.CreateInMemoryFontFileLoader()?;
            factory.RegisterFontFileLoader(&loader)?;
            let registered = RegisteredLoader { factory, loader };
            let factory = &registered.factory;
            let interop = factory.GetGdiInterop()?;
            let system = factory.CreateRenderingParams()?;
            // Temporary appearance-comparison control for this opt-in prototype.
            // Apply one constant correction at every size; no weight fade.
            let contrast_delta = std::env::var("SYSTEMLESS_NATIVE_TEXT_CONTRAST")
                .ok()
                .and_then(|value| value.parse::<f32>().ok())
                .filter(|value| value.is_finite() && (0.0..=1.0).contains(value))
                .unwrap_or(0.0);
            let parameters = |level| {
                factory.CreateCustomRenderingParams3(
                    system.GetGamma(),
                    system.GetEnhancedContrast() + contrast_delta,
                    1.0 + contrast_delta,
                    level,
                    system.GetPixelGeometry(),
                    DWRITE_RENDERING_MODE_NATURAL_SYMMETRIC,
                    DWRITE_GRID_FIT_MODE_DISABLED,
                )
            };
            let gray = parameters(0.0)?;
            let subpixel = parameters(1.0)?;
            Ok(Self {
                faces: HashMap::new(),
                registered,
                interop,
                gray,
                subpixel,
            })
        }
    }

    fn face(&mut self, bytes: &'static [u8]) -> Result<IDWriteFontFace2> {
        let key = (bytes.as_ptr() as usize, bytes.len());
        if let Some(face) = self.faces.get(&key) {
            return Ok(face.clone());
        }
        if bytes.is_empty() || self.faces.len() >= 32 {
            return Err(E_INVALIDARG.into());
        }
        let length = u32::try_from(bytes.len()).map_err(|_| E_INVALIDARG)?;
        unsafe {
            // A null owner asks DirectWrite to copy these bundled font bytes.
            // No fonts are installed, and no host font lookup determines layout.
            let file = self.registered.loader.CreateInMemoryFontFileReference(
                &self.registered.factory,
                bytes.as_ptr().cast(),
                length,
                None::<&IUnknown>,
            )?;
            let mut supported = BOOL(0);
            let mut file_type = DWRITE_FONT_FILE_TYPE::default();
            let mut face_type = DWRITE_FONT_FACE_TYPE::default();
            let mut count = 0;
            file.Analyze(
                &mut supported,
                &mut file_type,
                Some(&mut face_type),
                &mut count,
            )?;
            if !supported.as_bool() || count != 1 {
                return Err(E_INVALIDARG.into());
            }
            let face: IDWriteFontFace2 = self
                .registered
                .factory
                .CreateFontFace(face_type, &[Some(file)], 0, DWRITE_FONT_SIMULATIONS_NONE)?
                .cast()?;
            self.faces.insert(key, face.clone());
            Ok(face)
        }
    }

    pub(super) fn render(
        &mut self,
        bytes: &'static [u8],
        glyph: u16,
        size: f32,
        phase_x: f32,
        phase_y: f32,
        foreground: u32,
        background: u32,
    ) -> Result<GlyphImage> {
        if !size.is_finite()
            || !(0.0..=768.0).contains(&size)
            || size == 0.0
            || !phase_x.is_finite()
            || !phase_y.is_finite()
        {
            return Err(E_INVALIDARG.into());
        }
        let face = self.face(bytes)?;
        // This threshold is physical pixels/em, so resize and DPI scaling use
        // the actual displayed size. Gamma and contrast do not change with size.
        let parameters = if size < 12.0 {
            &self.gray
        } else {
            &self.subpixel
        };
        let advance = 0.0;
        let offset = DWRITE_GLYPH_OFFSET::default();
        let run = GlyphRun(DWRITE_GLYPH_RUN {
            fontFace: ManuallyDrop::new(Some(face.cast()?)),
            fontEmSize: size,
            glyphCount: 1,
            glyphIndices: &glyph,
            glyphAdvances: &advance,
            glyphOffsets: &offset,
            isSideways: BOOL(0),
            bidiLevel: 0,
        });
        unsafe {
            let mut mode = DWRITE_RENDERING_MODE::default();
            let mut grid = DWRITE_GRID_FIT_MODE::default();
            face.GetRecommendedRenderingMode3(
                size,
                96.0,
                96.0,
                None,
                false,
                DWRITE_OUTLINE_THRESHOLD_ALIASED,
                DWRITE_MEASURING_MODE_NATURAL,
                parameters,
                &mut mode,
                &mut grid,
            )?;
            if mode == DWRITE_RENDERING_MODE_OUTLINE {
                mode = DWRITE_RENDERING_MODE_NATURAL_SYMMETRIC;
            }
            let analysis = self.registered.factory.CreateGlyphRunAnalysis2(
                &run.0,
                None,
                mode,
                DWRITE_MEASURING_MODE_NATURAL,
                grid,
                DWRITE_TEXT_ANTIALIAS_MODE_CLEARTYPE,
                phase_x,
                phase_y,
            )?;
            let mut bounds = analysis.GetAlphaTextureBounds(DWRITE_TEXTURE_CLEARTYPE_3x1)?;
            if bounds.left == bounds.right || bounds.top == bounds.bottom {
                bounds = analysis.GetAlphaTextureBounds(DWRITE_TEXTURE_ALIASED_1x1)?;
            }
            let width = bounds.right.checked_sub(bounds.left).ok_or(E_FAIL)?;
            let height = bounds.bottom.checked_sub(bounds.top).ok_or(E_FAIL)?;
            if !(0..=2048).contains(&width) || !(0..=2048).contains(&height) {
                return Err(E_FAIL.into());
            }
            let mut image = GlyphImage {
                left: bounds.left,
                top: bounds.top,
                width,
                height,
                pixels: Vec::new(),
            };
            if width == 0 || height == 0 {
                return Ok(image);
            }
            let target = self.interop.CreateBitmapRenderTarget(
                HDC::default(),
                width as u32,
                height as u32,
            )?;
            let target1: IDWriteBitmapRenderTarget1 = target.cast()?;
            target1.SetTextAntialiasMode(DWRITE_TEXT_ANTIALIAS_MODE_CLEARTYPE)?;
            target.SetPixelsPerDip(1.0)?;
            let dc = target.GetMemoryDC();
            // GetMemoryDC documents a target-owned, 32-bit top-down DIB.
            // Access it directly instead of making another DC/bitmap and blit.
            let bitmap = GetCurrentObject(dc, OBJ_BITMAP);
            let mut dib = DIBSECTION::default();
            if GetObjectW(
                bitmap,
                size_of::<DIBSECTION>() as i32,
                Some((&mut dib as *mut DIBSECTION).cast()),
            ) != size_of::<DIBSECTION>() as i32
                || dib.dsBm.bmBits.is_null()
                || dib.dsBm.bmBitsPixel != 32
                || dib.dsBm.bmWidth != width
                || dib.dsBm.bmHeight != height
                || dib.dsBm.bmWidthBytes < width * 4
                || dib.dsBm.bmWidthBytes % 4 != 0
            {
                return Err(E_FAIL.into());
            }
            let stride = dib.dsBm.bmWidthBytes as usize / 4;
            let count = stride.checked_mul(height as usize).ok_or(E_FAIL)?;
            if count > 8 * 1024 * 1024 {
                return Err(E_FAIL.into());
            }
            if !GdiFlush().as_bool() {
                return Err(E_FAIL.into());
            }
            // The target stays alive, calls are synchronous, and this thread
            // has exclusive access. Do not keep a Rust slice across GDI calls.
            std::slice::from_raw_parts_mut(dib.dsBm.bmBits.cast::<u32>(), count).fill(background);
            let color = COLORREF(
                ((foreground >> 16) & 255) | (foreground & 0xff00) | ((foreground & 255) << 16),
            );
            target.DrawGlyphRun(
                phase_x - bounds.left as f32,
                phase_y - bounds.top as f32,
                DWRITE_MEASURING_MODE_NATURAL,
                &run.0,
                parameters,
                color,
                None,
            )?;
            if !GdiFlush().as_bool() {
                return Err(E_FAIL.into());
            }
            let pixels = std::slice::from_raw_parts(dib.dsBm.bmBits.cast::<u32>(), count);
            image.pixels.reserve(width as usize * height as usize);
            for row in pixels.chunks_exact(stride) {
                image.pixels.extend(
                    row[..width as usize]
                        .iter()
                        .map(|&pixel| pixel | 0xff000000),
                );
            }
            Ok(image)
        }
    }
}
