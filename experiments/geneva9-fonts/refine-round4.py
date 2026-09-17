"""Lighter R/T, farther-left i, and a T with its shaft on the native grid."""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
baseline = TTFont(OUT / 'Coppet-Round3-T25-unhinted.ttf')
font = copy.deepcopy(baseline)
i_glyph = font['glyf']['uni0069']
for index, (x, y) in enumerate(i_glyph.coordinates):
    i_glyph.coordinates[index] = (x - 25, y)

source = instantiateVariableFont(TTFont(HERE / 'sources/inter/Inter[opsz,wght].ttf'),
    {'wght': 360, 'opsz': 14}, inplace=True)
name = source.getBestCmap()[ord('R')]
g = source['glyf'][name]
sx, sy = 500 / (g.xMax - g.xMin), 700 / (g.yMax - g.yMin)
recording = DecomposingRecordingPen(source.getGlyphSet())
source.getGlyphSet()[name].draw(recording)
pen = TTGlyphPen(None)
recording.replay(TransformPen(pen, (sx, 0, 0, sy, -sx * g.xMin, -sy * g.yMin)))
font['glyf']['uni0052'] = pen.glyph()

reports = []
for variant, version, center in [('Shifted', '0.017', 275), ('Aligned', '0.018', 250)]:
    candidate = copy.deepcopy(font)
    t = candidate['glyf']['uni0054']
    assert len(t.coordinates) == 8 and t.numberOfContours == 1
    # Crossbar stays a quarter pixel right, but is thinner. Compare moving
    # the shaft with it versus keeping that shaft centered on pixel column 2.
    for index, (x, y) in enumerate(t.coordinates):
        if y == 621:
            y = 628
        if index in [4, 5]:
            x = center + 40
        elif index in [6, 7]:
            x = center - 40
        t.coordinates[index] = (x, y)
    for ch in 'RTi':
        name = candidate.getBestCmap()[ord(ch)]
        g = candidate['glyf'][name]
        g.recalcBounds(candidate['glyf'])
        candidate['hmtx'][name] = (baseline['hmtx'][name][0], g.xMin)
    for record in list(candidate['name'].names):
        if record.nameID in [3, 5]:
            text = f'Coppet-Regular-Study-{version}' if record.nameID == 3 else f'Version {version}; Inter-derived Geneva 9 optical refinement'
            candidate['name'].setName(text, record.nameID, record.platformID, record.platEncID, record.langID)
    candidate.recalcTimestamp = False
    unhinted = OUT / f'Coppet-Round4-{variant}-unhinted.ttf'
    hinted = OUT / f'Coppet-Round4-{variant}.ttf'
    candidate.save(unhinted)
    subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0', '-a', 'qsq', str(unhinted), str(hinted)], check=True)
    hinted_font = TTFont(hinted)
    i_glyph = hinted_font['glyf']['uni0069']
    points = len(i_glyph.coordinates)
    hint = Program()
    hint.fromAssembly(['SVTCA[1]', 'MPPEM[ ]', 'PUSHB[ ]', '9', 'EQ[ ]', 'IF[ ]',
        'PUSHB[ ]', '1', 'SZP2[ ]', 'PUSHB[ ]', str(points), 'SLOOP[ ]',
        'NPUSHB[ ]', *map(str, range(points)), '32', 'SHPIX[ ]', 'EIF[ ]'])
    i_glyph.program.fromBytecode(bytes(i_glyph.program.getBytecode()) + bytes(hint.getBytecode()))
    hinted_font['maxp'].maxStackElements = max(hinted_font['maxp'].maxStackElements, points + 1)
    hinted_font.recalcTimestamp = False
    hinted_font.save(hinted)
    result = TTFont(unhinted)
    changed = [chr(c) for c in range(32, 127) if
        baseline['glyf'][baseline.getBestCmap()[c]].compile(baseline['glyf']) !=
        result['glyf'][result.getBestCmap()[c]].compile(result['glyf'])]
    assert changed == ['R', 'T', 'i'], changed
    assert all(baseline['hmtx'][n][0] == result['hmtx'][n][0] for n in baseline.getGlyphOrder())
    reports.append({'variant': variant, 'version': version, 'changed_outlines': changed,
        'advances_unchanged': True, 'R_Inter_weight': 360, 'T_stem_width': 80,
        'T_crossbar_thickness': 72, 'T_stem_center': center, 'T_crossbar_center': 275,
        'i_shift_from_round2': -50, 'i_9ppem_hint': '+32/64 pixel; real points only',
        'sha256': hashlib.sha256(hinted.read_bytes()).hexdigest()})
(OUT / 'round4-build-validation.json').write_text(json.dumps(reports, indent=2) + '\n')
print(json.dumps(reports, indent=2))
