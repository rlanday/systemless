"""Isolate a lowercase-t correction against the accepted first Inter study."""
from pathlib import Path
import hashlib,json,os,subprocess
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

here=Path(__file__).resolve().parent
out=here/'generated';out.mkdir(exist_ok=True)
base=TTFont(here/'generated/inter-fitted-unhinted.ttf')
source=instantiateVariableFont(TTFont(here/'sources/inter/Inter[opsz,wght].ttf'),{'wght':400,'opsz':14},inplace=True)
name=source.getBestCmap()[ord('t')]
original=source['glyf'][name]
pen=TTGlyphPen(None)
recording=DecomposingRecordingPen(source.getGlyphSet());source.getGlyphSet()[name].draw(recording)
sx=300/(original.xMax-original.xMin)
# The crossbar reaches Inter's x-height (1118 source units). Give it the same
# five-logical-pixel x-height as the other fitted lowercase glyphs, rather than
# stretching the whole t to the seven-pixel cap-height bounding box.
sy=500/source['OS/2'].sxHeight
recording.replay(TransformPen(pen,(sx,0,0,sy,-sx*original.xMin,0)))
base['glyf']['uni0074']=pen.glyph()
base['glyf']['uni0074'].flags[0] |= 0x40  # retain Inter's overlapping-contour flag
names={1:'Coppet',2:'Regular',3:'Coppet-Regular-Study-0.002',
       4:'Coppet Regular',5:'Version 0.002; Inter-derived Geneva 9 optical study',
       6:'Coppet-Regular',16:'Coppet',17:'Regular'}
for record in list(base['name'].names):
    if record.nameID in names:
        base['name'].setName(names[record.nameID],record.nameID,record.platformID,record.platEncID,record.langID)
for name_id,text in names.items():base['name'].setName(text,name_id,3,1,0x409)
base.recalcTimestamp=False
unhinted=out/'Coppet-Regular-unhinted.ttf';hinted=out/'Coppet-Regular.ttf'
base.save(unhinted)
subprocess.run([os.environ.get('TTFAUTOHINT','ttfautohint'),'-n','-x','0','-a','qsq',str(unhinted),str(hinted)],check=True)
before=TTFont(here/'generated/inter-fitted-unhinted.ttf');after=TTFont(unhinted)
changed=[n for n in before.getGlyphOrder() if before['glyf'][n].compile(before['glyf']) != after['glyf'][n].compile(after['glyf'])]
assert changed==['uni0074'],changed
assert before['hmtx'].metrics==after['hmtx'].metrics
g=after['glyf']['uni0074']
report={'changed_unhinted_glyphs':changed,'all_advances_and_bearings_unchanged':True,
        't_advance_at_9':after['hmtx']['uni0074'][0]/100,'t_before_bounds':[0,0,300,700],
        't_after_bounds':[g.xMin,g.yMin,g.xMax,g.yMax],
        'source_x_height':source['OS/2'].sxHeight,'scale_y':sy,
        'font_sha256':hashlib.sha256(hinted.read_bytes()).hexdigest(),
        'note':'Raster checks are required because rehinting regenerates shared font tables.'}
(out/'t-correction-build-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
