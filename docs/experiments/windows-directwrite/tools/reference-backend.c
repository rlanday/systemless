#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <initguid.h>
#include <dwrite_3.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* Experimental renderer, loaded only by the opt-in prototype. No fonts are
   installed and no file paths are passed to the Windows font service. */
typedef struct { int32_t left,top,width,height; uint32_t *pixels; } GlyphImage;
static IDWriteFactory *factory;
static IDWriteFactory5 *factory5;
static IDWriteFactory2 *factory2;
static IDWriteInMemoryFontFileLoader *loader;
static IDWriteGdiInterop *interop;
static IDWriteRenderingParams *params_gray;
static IDWriteRenderingParams *params_subpixel;
typedef struct { const void *bytes; uint32_t length; IDWriteFontFace *face; } Face;
static Face faces[32];
static uint32_t face_count;
#define CHECK(call) do { HRESULT result=(call); if(FAILED(result)){hr=result;goto cleanup;} } while(0)

static HRESULT init(void){
 static HRESULT initialized=E_PENDING;
 HRESULT hr=S_OK;
 if(initialized!=E_PENDING)return initialized;
 CHECK(DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED,&IID_IDWriteFactory,(IUnknown**)&factory));
 CHECK(IDWriteFactory_QueryInterface(factory,&IID_IDWriteFactory5,(void**)&factory5));
 CHECK(IDWriteFactory_QueryInterface(factory,&IID_IDWriteFactory2,(void**)&factory2));
 CHECK(IDWriteFactory5_CreateInMemoryFontFileLoader(factory5,&loader));
 CHECK(IDWriteFactory_RegisterFontFileLoader(factory,(IDWriteFontFileLoader*)loader));
 CHECK(IDWriteFactory_GetGdiInterop(factory,&interop));
 IDWriteRenderingParams *system_params=NULL;
 IDWriteRenderingParams2 *gray=NULL,*subpixel=NULL;
 CHECK(IDWriteFactory_CreateRenderingParams(factory,&system_params));
 /* Selected after physical-display review: smooth curves, standard contrast,
    grayscale below 12 physical pixels/em and full subpixel at 12 and above.
    No size-dependent gamma or contrast changes. */
 CHECK(IDWriteFactory2_CreateCustomRenderingParams(factory2,IDWriteRenderingParams_GetGamma(system_params),IDWriteRenderingParams_GetEnhancedContrast(system_params),1,0,IDWriteRenderingParams_GetPixelGeometry(system_params),DWRITE_RENDERING_MODE_NATURAL_SYMMETRIC,DWRITE_GRID_FIT_MODE_DISABLED,&gray));
 CHECK(IDWriteFactory2_CreateCustomRenderingParams(factory2,IDWriteRenderingParams_GetGamma(system_params),IDWriteRenderingParams_GetEnhancedContrast(system_params),1,1,IDWriteRenderingParams_GetPixelGeometry(system_params),DWRITE_RENDERING_MODE_NATURAL_SYMMETRIC,DWRITE_GRID_FIT_MODE_DISABLED,&subpixel));
 params_gray=(IDWriteRenderingParams*)gray;params_subpixel=(IDWriteRenderingParams*)subpixel;
 IDWriteRenderingParams_Release(system_params);
cleanup:initialized=hr;return hr;
}
static HRESULT font_face(const void *bytes,uint32_t length,IDWriteFontFace **face){
 for(uint32_t i=0;i<face_count;i++)if(faces[i].bytes==bytes&&faces[i].length==length){*face=faces[i].face;return S_OK;}
 if(face_count==32)return E_OUTOFMEMORY;
 HRESULT hr=S_OK;IDWriteFontFile *file=NULL;
 CHECK(IDWriteInMemoryFontFileLoader_CreateInMemoryFontFileReference(loader,factory,bytes,length,NULL,&file));
 BOOL supported=FALSE;DWRITE_FONT_FILE_TYPE file_type;DWRITE_FONT_FACE_TYPE face_type;UINT32 count=0;
 CHECK(IDWriteFontFile_Analyze(file,&supported,&file_type,&face_type,&count));
 if(!supported||count!=1){hr=E_FAIL;goto cleanup;}
 CHECK(IDWriteFactory_CreateFontFace(factory,face_type,1,&file,0,DWRITE_FONT_SIMULATIONS_NONE,face));
 faces[face_count++]=(Face){bytes,length,*face};
cleanup:if(file)IDWriteFontFile_Release(file);return hr;
}
__declspec(dllexport) void free_glyph(GlyphImage *image){free(image->pixels);memset(image,0,sizeof(*image));}

__declspec(dllexport) HRESULT render_glyph(const void *bytes,uint32_t length,uint16_t glyph,float size,float phase_x,float phase_y,uint32_t foreground,uint32_t background,GlyphImage *image){
 HRESULT hr=S_OK;IDWriteFontFace *face=NULL;IDWriteFontFace2 *face2=NULL;IDWriteGlyphRunAnalysis *analysis=NULL;IDWriteBitmapRenderTarget *target=NULL;
 IDWriteRenderingParams *draw_params=NULL;
 IDWriteBitmapRenderTarget1 *target1=NULL;HDC capture=NULL;HBITMAP bitmap=NULL;HGDIOBJ previous=NULL;void *pixels=NULL;
 memset(image,0,sizeof(*image));
 if(!bytes||!length||size<=0||size>768)return E_INVALIDARG;
 CHECK(init());CHECK(font_face(bytes,length,&face));
 draw_params=size<12.0f?params_gray:params_subpixel;
 /* Selected candidate: standard contrast at every size. */
 FLOAT advance=0;DWRITE_GLYPH_OFFSET offset={0};
 DWRITE_GLYPH_RUN run={face,size,1,&glyph,&advance,&offset,FALSE,0};
 DWRITE_RENDERING_MODE mode;DWRITE_GRID_FIT_MODE grid;
 CHECK(IDWriteFontFace_QueryInterface(face,&IID_IDWriteFontFace2,(void**)&face2));
 CHECK(IDWriteFontFace2_GetRecommendedRenderingMode(face2,size,96,96,NULL,FALSE,DWRITE_OUTLINE_THRESHOLD_ALIASED,DWRITE_MEASURING_MODE_NATURAL,draw_params,&mode,&grid));
 if(mode==DWRITE_RENDERING_MODE_OUTLINE)mode=DWRITE_RENDERING_MODE_NATURAL_SYMMETRIC;
 CHECK(IDWriteFactory2_CreateGlyphRunAnalysis(factory2,&run,NULL,mode,DWRITE_MEASURING_MODE_NATURAL,grid,DWRITE_TEXT_ANTIALIAS_MODE_CLEARTYPE,phase_x,phase_y,&analysis));
 RECT bounds;
 CHECK(IDWriteGlyphRunAnalysis_GetAlphaTextureBounds(analysis,DWRITE_TEXTURE_CLEARTYPE_3x1,&bounds));
 if(bounds.right==bounds.left||bounds.bottom==bounds.top)CHECK(IDWriteGlyphRunAnalysis_GetAlphaTextureBounds(analysis,DWRITE_TEXTURE_ALIASED_1x1,&bounds));
 image->left=bounds.left;image->top=bounds.top;image->width=bounds.right-bounds.left;image->height=bounds.bottom-bounds.top;
 if(!image->width||!image->height)goto cleanup;
 if(image->width<0||image->height<0||image->width>2048||image->height>2048){hr=E_FAIL;goto cleanup;}
 CHECK(IDWriteGdiInterop_CreateBitmapRenderTarget(interop,NULL,image->width,image->height,&target));
 CHECK(IDWriteBitmapRenderTarget_QueryInterface(target,&IID_IDWriteBitmapRenderTarget1,(void**)&target1));
 CHECK(IDWriteBitmapRenderTarget1_SetTextAntialiasMode(target1,DWRITE_TEXT_ANTIALIAS_MODE_CLEARTYPE));
 CHECK(IDWriteBitmapRenderTarget_SetPixelsPerDip(target,1));
 HDC dc=IDWriteBitmapRenderTarget_GetMemoryDC(target);RECT rect={0,0,image->width,image->height};
 HBRUSH brush=CreateSolidBrush(RGB((background>>16)&255,(background>>8)&255,background&255));
 FillRect(dc,&rect,brush);DeleteObject(brush);GdiFlush();
 CHECK(IDWriteBitmapRenderTarget_DrawGlyphRun(target,phase_x-bounds.left,phase_y-bounds.top,DWRITE_MEASURING_MODE_NATURAL,&run,draw_params,RGB((foreground>>16)&255,(foreground>>8)&255,foreground&255),NULL));
 BITMAPINFO info={0};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=image->width;info.bmiHeader.biHeight=-image->height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
 capture=CreateCompatibleDC(dc);bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,NULL,0);
 if(!capture||!bitmap||!pixels){hr=E_OUTOFMEMORY;goto cleanup;}
 previous=SelectObject(capture,bitmap);
 if(!BitBlt(capture,0,0,image->width,image->height,dc,0,0,SRCCOPY)){hr=E_FAIL;goto cleanup;}
 GdiFlush();size_t count=(size_t)image->width*image->height;
 image->pixels=malloc(count*sizeof(uint32_t));if(!image->pixels){hr=E_OUTOFMEMORY;goto cleanup;}
 for(size_t i=0;i<count;i++)image->pixels[i]=((uint32_t*)pixels)[i]|0xff000000u;
cleanup:
 if(previous)SelectObject(capture,previous);
 if(bitmap)DeleteObject(bitmap);
 if(capture)DeleteDC(capture);
 if(target1)IDWriteBitmapRenderTarget1_Release(target1);
 if(target)IDWriteBitmapRenderTarget_Release(target);
 if(analysis)IDWriteGlyphRunAnalysis_Release(analysis);
 if(face2)IDWriteFontFace2_Release(face2);
 if(FAILED(hr))free_glyph(image);
 return hr;
}
