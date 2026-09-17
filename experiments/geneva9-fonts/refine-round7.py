"""Compare small-text R/& fitting and an independently drawn i entry stroke.

The only artwork input is our existing OFL Inter-derived Coppet outline.
No Apple font file, bitmap, coordinate or contour is read by this build.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.pens.ttGlyphPen import TTGlyphPen

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
baseline = TTFont(OUT / 'Coppet-Round6-Right-unhinted.ttf')


def interpolate(value, knots):
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if value <= x1:
            return y0 + (value - x0) * (y1 - y0) / (x1 - x0)
    raise ValueError(value)


def refine_bar(font):
    g = font['glyf']['uni0052']
    # Center the 71-unit bar on logical y=3.5. Move its adjacent curves and
    # leg join smoothly, anchoring the baseline, bowl's side and cap height.
    for index, (x, y) in enumerate(g.coordinates):
        g.coordinates[index] = (x, round(interpolate(y,
            [(0, 0), (276, 314), (347, 385), (486, 486), (700, 700)])))


def refine_ampersand(font):
    g = font['glyf']['uni0026']
    # The upper bowl's side strokes straddle final pixel columns. Bring
    # their centers towards x=1.5 and 4.5; open the counter, retaining the
    # existing top/bottom alignment, outer ink bounds and balanced bearings.
    for index, (x, y) in enumerate(g.coordinates):
        if y > 300:
            amount = min(1.0, (y - 300) / 200)
            target = interpolate(x, [(100, 100), (151, 111), (228, 189),
                (382, 412), (458, 488), (600, 600)])
            x = round(x + (target - x) * amount)
        g.coordinates[index] = (x, y)


def entry_stroke(font):
    old = font['glyf']['uni0069']
    pen = TTGlyphPen(None)
    # Use Coppet's accepted ~72-unit stroke weight and aligned stem.
    # Only the upper-left extension is new; keep the shaft and dot exactly.
    pen.moveTo((114, 0))
    for p in [(114, 437), (25, 437), (25, 509), (185, 509), (185, 0)]:
        pen.lineTo(p)
    pen.closePath()
    # Replay the original quadratic dot contour without changing its points.
    pen.moveTo(tuple(old.coordinates[4]))
    for start, end in [(5, 7), (8, 10), (11, 13), (14, 4)]:
        pen.qCurveTo(tuple(old.coordinates[start]),
            tuple(old.coordinates[start + 1]), tuple(old.coordinates[end]))
    pen.closePath()
    font['glyf']['uni0069'] = pen.glyph()


reports = []
for variant, version, sharper, entry in [
        ('Sharp', '0.022', True, False),
        ('Entry', '0.023', False, True),
        ('Combined', '0.024', True, True)]:
    font = copy.deepcopy(baseline)
    if sharper:
        refine_bar(font)
        refine_ampersand(font)
    if entry:
        entry_stroke(font)
    for ch in '&Ri':
        name = font.getBestCmap()[ord(ch)]
        g = font['glyf'][name]
        g.recalcBounds(font['glyf'])
        font['hmtx'][name] = (baseline['hmtx'][name][0], g.xMin)
    for record in list(font['name'].names):
        if record.nameID in [3, 5]:
            text = f'Coppet-Regular-Study-{version}' if record.nameID == 3 else f'Version {version}; Inter-derived Geneva 9 optical refinement'
            font['name'].setName(text, record.nameID, record.platformID,
                record.platEncID, record.langID)
    font.recalcTimestamp = False
    unhinted = OUT / f'Coppet-Round7-{variant}-unhinted.ttf'
    hinted = OUT / f'Coppet-Round7-{variant}.ttf'
    font.save(unhinted)
    subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0',
        '-a', 'qsq', str(unhinted), str(hinted)], check=True)
    font = TTFont(hinted)
    # Preserve the accepted guest-size l foot, as in round six.
    g = font['glyf']['uni006C']
    points = len(g.coordinates)
    hint = Program()
    hint.fromAssembly(['SVTCA[1]', 'MPPEM[ ]', 'PUSHB[ ]', '9', 'EQ[ ]', 'IF[ ]',
        'PUSHB[ ]', '1', 'SZP2[ ]', 'PUSHB[ ]', str(points), 'SLOOP[ ]',
        'NPUSHB[ ]', *map(str, range(points)), '20', 'SHPIX[ ]', 'EIF[ ]'])
    g.program.fromBytecode(bytes(g.program.getBytecode()) + bytes(hint.getBytecode()))
    font['maxp'].maxStackElements = max(font['maxp'].maxStackElements, points + 1)
    font.recalcTimestamp = False
    font.save(hinted)
    result = TTFont(unhinted)
    changed = [chr(c) for c in range(32, 127) if
        baseline['glyf'][baseline.getBestCmap()[c]].compile(baseline['glyf']) !=
        result['glyf'][result.getBestCmap()[c]].compile(result['glyf'])]
    assert changed == (['&', 'R'] if sharper else []) + (['i'] if entry else [])
    assert all(baseline['hmtx'][n][0] == result['hmtx'][n][0]
        for n in baseline.getGlyphOrder())
    reports.append({'variant': variant, 'version': version,
        'changed_outlines': changed, 'all_advances_unchanged': True,
        'artwork_source': 'Coppet-Round6-Right-unhinted.ttf (OFL Inter derivative)',
        'R_bar_outline_shift_units': 38 if sharper else 0,
        'i_entry_extension_units': 89 if entry else 0,
        'sha256': hashlib.sha256(hinted.read_bytes()).hexdigest()})
(OUT / 'round7-build-validation.json').write_text(json.dumps(reports, indent=2) + '\n')
print(json.dumps(reports, indent=2))
