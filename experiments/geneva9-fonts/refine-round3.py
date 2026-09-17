"""Review P/y/j weight and i/l placement; isolate two T-bearing trials.

Continue from the selected curved-foot l. No advances or engine behavior change.
The half-pixel T trial is generated only to audit its fragile guest stem.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables.ttProgram import Program

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
baseline = TTFont(OUT / 'Coppet-Round2-Foot-unhinted.ttf')
font = copy.deepcopy(baseline)

def edit(char, transform):
    g = font['glyf'][font.getBestCmap()[ord(char)]]
    for i, (x, y) in enumerate(g.coordinates):
        g.coordinates[i] = tuple(round(v) for v in transform(i, x, y))
    g.recalcBounds(font['glyf'])

# Keep P's outer width and bowl extent while reducing its straight stem.
edit('P', lambda i, x, y: (x * 80 / 93 if x <= 93 else
     80 + (x - 93) * 420 / 407, y))
# Reduce j's shaft from 80 to 72; blend into the unchanged hook end.
j = font['glyf']['uni006A']
edit('j', lambda i, x, y: (
    (150 + (x - 150) * 72 / 80 if x >= 110 else x * 114 / 110), y)
    if i <= j.endPtsOfContours[0] else (x, y))
# A restrained shift balances m-i / i-n and gives i-l more breathing room.
# Larger fractional shifts can erase the one-bit stem: audit before review.
edit('i', lambda i, x, y: (x - 25, y))
edit('l', lambda i, x, y: (x + 20, y))

source = instantiateVariableFont(TTFont(HERE / 'sources/inter/Inter[opsz,wght].ttf'),
    {'wght': 360, 'opsz': 14}, inplace=True)
name = source.getBestCmap()[ord('y')]
g = source['glyf'][name]
sx, sy = 500 / (g.xMax - g.xMin), 700 / (g.yMax - g.yMin)
recording = DecomposingRecordingPen(source.getGlyphSet())
source.getGlyphSet()[name].draw(recording)
pen = TTGlyphPen(None)
recording.replay(TransformPen(pen, (sx, 0, 0, sy, -sx * g.xMin, -200 - sy * g.yMin)))
font['glyf']['uni0079'] = pen.glyph()

reports = []
for variant, version, shift in [('Weight', '0.013', 0), ('T25', '0.014', 25),
                                ('T100', '0.015', 100), ('T50-AuditOnly', '0.016', 50)]:
    candidate = copy.deepcopy(font)
    t = candidate['glyf']['uni0054']
    if shift:
        for i, (x, y) in enumerate(t.coordinates):
            t.coordinates[i] = (x + shift, y)
    changed_chars = 'Pijly' + ('T' if shift else '')
    for ch in changed_chars:
        n = candidate.getBestCmap()[ord(ch)]
        g = candidate['glyf'][n]
        g.recalcBounds(candidate['glyf'])
        candidate['hmtx'][n] = (baseline['hmtx'][n][0], g.xMin)
    for record in list(candidate['name'].names):
        if record.nameID in [3, 5]:
            text = f'Coppet-Regular-Study-{version}' if record.nameID == 3 else f'Version {version}; Inter-derived Geneva 9 optical refinement'
            candidate['name'].setName(text, record.nameID, record.platformID, record.platEncID, record.langID)
    candidate.recalcTimestamp = False
    unhinted = OUT / f'Coppet-Round3-{variant}-unhinted.ttf'
    hinted = OUT / f'Coppet-Round3-{variant}.ttf'
    candidate.save(unhinted)
    subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0', '-a', 'qsq',
                    str(unhinted), str(hinted)], check=True)
    # Native audit found that the shifted circular i dot falls below the
    # one-bit coverage threshold at 9 ppem. Add a size-specific x hint after
    # autohinting: restore the accepted position at the guest bitmap size,
    # while keeping the new outline placement in the 36-ppem retained mask.
    # Move real points only; phantom points/advances remain untouched.
    hinted_font = TTFont(hinted)
    i_glyph = hinted_font['glyf']['uni0069']
    points = len(i_glyph.coordinates)
    hint = Program()
    hint.fromAssembly(['SVTCA[1]', 'MPPEM[ ]', 'PUSHB[ ]', '9', 'EQ[ ]', 'IF[ ]',
        'PUSHB[ ]', '1', 'SZP2[ ]', 'PUSHB[ ]', str(points), 'SLOOP[ ]',
        'NPUSHB[ ]', *map(str, range(points)), '16', 'SHPIX[ ]', 'EIF[ ]'])
    i_glyph.program.fromBytecode(bytes(i_glyph.program.getBytecode()) + bytes(hint.getBytecode()))
    hinted_font['maxp'].maxStackElements = max(hinted_font['maxp'].maxStackElements, points + 1)
    hinted_font.recalcTimestamp = False
    hinted_font.save(hinted)
    result = TTFont(unhinted)
    changed = [chr(c) for c in range(32, 127) if
        baseline['glyf'][baseline.getBestCmap()[c]].compile(baseline['glyf']) !=
        result['glyf'][result.getBestCmap()[c]].compile(result['glyf'])]
    assert set(changed) == set(changed_chars), changed
    assert all(baseline['hmtx'][n][0] == result['hmtx'][n][0] for n in baseline.getGlyphOrder())
    reports.append({'variant': variant, 'version': version, 'changed_outlines': changed,
        'T_shift': shift, 'advances_unchanged': True,
        'i_guest_hint': '9 ppem only: shift real contour points +16/64 pixel in x; no phantom point movement',
        'parameters': {'P_stem': 80, 'j_stem': 72, 'y_Inter_weight': 360, 'i_shift': -25, 'l_shift': 20},
        'sha256': hashlib.sha256(hinted.read_bytes()).hexdigest()})
(OUT / 'round3-build-validation.json').write_text(json.dumps(reports, indent=2) + '\n')
print(json.dumps(reports, indent=2))
