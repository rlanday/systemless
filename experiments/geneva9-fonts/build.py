"""Build three ASCII Geneva-9 optical studies from licensed source designs.

Apple reference data is deliberately not an input. This is a comparison, not a
production typeface: 9-point ASCII only; Systemless preserves other glyphs.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.svgLib.path import parse_path

HERE = Path(__file__).resolve().parent
SOURCES = HERE / 'sources'
OUT = HERE / 'generated'
OUT.mkdir(exist_ok=True)
POTRACE = os.environ.get('POTRACE', 'potrace')
TTFAUTOHINT = os.environ.get('TTFAUTOHINT', 'ttfautohint')
ENV = dict(os.environ)
UPEM = 900  # 100 units per pixel at the intended 9-point optical size.


def historical(size):
    text = (SOURCES / f'kurrajong/geneva{size}.rs').read_text()
    text = re.sub(r'//[^\n]*', '', text)
    records = re.findall(r'g!\(\s*(\d+)\s*,\s*\((-?\d+)\s*,\s*(-?\d+)\)\s*,(.*?)\)', text, re.S)
    result = []
    for advance, left, top, body in records:
        rows = re.findall(r'"([.#]+)"', body)
        assert not rows or len(set(map(len, rows))) == 1
        points = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '#']
        left, top = int(left), int(top)
        bounds = None if not points else (
            left + min(x for x, y in points),
            -(top + max(y for x, y in points) + 1),
            left + max(x for x, y in points) + 1,
            -(top + min(y for x, y in points)),
        )
        result.append(dict(advance=int(advance), left=left, top=top, rows=rows, bounds=bounds))
    assert len(result) == 95
    return result


SMALL, LARGE = historical(9), historical(24)
assert bytes(g['advance'] for g in SMALL) == (SOURCES / 'geneva9-advances.bin').read_bytes()


def bounds(recording):
    pen = BoundsPen(None)
    recording.replay(pen)
    return pen.bounds


def trace(rows, code):
    bitmap = OUT / f'trace-{code}.pbm'
    svg = bitmap.with_suffix('.svg')
    w, h = len(rows[0]), len(rows)
    bitmap.write_text(f'P1\n{w} {h}\n' + '\n'.join(' '.join('1' if c == '#' else '0' for c in row) for row in rows))
    subprocess.run([POTRACE, '-s', '-t', '0', '-a', '1.0', '-O', '0.15', '-o', str(svg), str(bitmap)], env=ENV, check=True)
    recording = RecordingPen()
    # Potrace path coordinates have y increasing upwards; the enclosing SVG
    # transform flips them for display. The font also needs y upwards.
    for path in ET.parse(svg).getroot().iter('{http://www.w3.org/2000/svg}path'):
        parse_path(path.attrib['d'], recording)
    return recording


def fitted(recording, target, vertical):
    if target is None or bounds(recording) is None:
        return TTGlyphPen(None).glyph()
    x0, y0, x1, y1 = bounds(recording)
    tx0, ty0, tx1, ty1 = [v * 100 for v in target]
    sx = (tx1 - tx0) / (x1 - x0)
    if vertical == 'fit':
        sy = (ty1 - ty0) / (y1 - y0)
        dy = ty0 - sy * y0
    else:
        sy, dy = vertical, 0
    pen = TTGlyphPen(None)
    cubic = Cu2QuPen(pen, max_err=0.5, reverse_direction=False)
    recording.replay(TransformPen(cubic, (sx, 0, 0, sy, tx0 - sx * x0, dy)))
    return pen.glyph()


def make(key, family, source=None):
    if source:
        font = TTFont(source)
        if 'fvar' in font:
            font = instantiateVariableFont(font, {'wght': 400, 'opsz': 14}, inplace=False)
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap()
        scale = UPEM / font['head'].unitsPerEm
    order = ['.notdef'] + [f'uni{code:04X}' for code in range(32, 127)]
    glyphs = {'.notdef': TTGlyphPen(None).glyph()}
    metrics = {'.notdef': (500, 0)}
    checks = []
    for code in range(32, 127):
        i, name = code - 32, f'uni{code:04X}'
        target = SMALL[i]
        if source:
            recording = DecomposingRecordingPen(glyph_set)
            glyph_set[cmap[code]].draw(recording)
            # Preserve Nimbus vertical proportions; fit Inter to the same
            # historical small-size ink boxes as Kurrajong for this study.
            vertical = scale if key == 'nimbus-fitted' else 'fit'
        elif LARGE[i]['rows']:
            recording = trace(LARGE[i]['rows'], code)
            vertical = 'fit'
        else:
            recording, vertical = RecordingPen(), 'fit'
        glyph = fitted(recording, target['bounds'], vertical)
        glyphs[name] = glyph
        glyph.recalcBounds(glyphs)
        metrics[name] = (target['advance'] * 100, getattr(glyph, 'xMin', 0))
        checks.append({'code': code, 'advance_at_9': metrics[name][0] / 100,
                       'ink_box': [getattr(glyph, k, 0) / 100 for k in ['xMin', 'yMin', 'xMax', 'yMax']]})
    builder = FontBuilder(UPEM, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({code: f'uni{code:04X}' for code in range(32, 127)})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=1000, descent=-200, lineGap=0)
    builder.setupNameTable({
        'familyName': family, 'styleName': 'Regular',
        'uniqueFontIdentifier': family.replace(' ', '') + '-Study-1',
        'fullName': family + ' Regular', 'psName': family.replace(' ', '') + '-Regular',
        'version': 'Version 0.001; comparison only; 9-point ASCII optical study',
        'copyright': 'Derived from ' + ('Ben Letchford 2026 Kurrajong (OFL-1.1)' if source is None else ('Rasmus Andersson Inter (OFL-1.1)' if key == 'inter-fitted' else 'URW++ 2014,2015 Nimbus Sans (OFL-1.1)')),
        'licenseDescription': 'SIL Open Font License 1.1; see adjacent source license.',
        'licenseInfoURL': 'https://openfontlicense.org/',
    })
    builder.setupOS2(sTypoAscender=1000, sTypoDescender=-200, sTypoLineGap=0,
                     usWinAscent=1000, usWinDescent=200, sxHeight=500, sCapHeight=700,
                     usWeightClass=400, usWidthClass=5, fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    unhinted, hinted = OUT / f'{key}-unhinted.ttf', OUT / f'{key}.ttf'
    builder.save(unhinted)
    # New contours need new instructions. Disable automatic x-height enlargement
    # so this comparison doesn't silently add a second size-dependent treatment.
    subprocess.run([TTFAUTOHINT, '-n', '-x', '0', '-a', 'qsq',
                    str(unhinted), str(hinted)], env=ENV, check=True)
    for path in [unhinted, hinted]:
        parsed = TTFont(path)
        assert set(parsed.getBestCmap()) == set(range(32, 127))
        assert [parsed['hmtx'][parsed.getBestCmap()[c]][0] for c in range(32, 127)] == [g['advance'] * 100 for g in SMALL]
    license_path = SOURCES / 'kurrajong/OFL.txt' if source is None else (SOURCES / 'inter/OFL.txt' if key == 'inter-fitted' else SOURCES / 'nimbus/OFL.txt')
    shutil.copyfile(license_path, OUT / f'{key}-OFL.txt')
    return {'key': key, 'family': family, 'file': hinted.name, 'sha256': hashlib.sha256(hinted.read_bytes()).hexdigest(),
            'source': str(source) if source else 'historical/geneva24.rs outlines; historical/geneva9.rs ink boxes and advances',
            'glyphs': checks}


manifest = [
    make('kurrajong-curves', 'Kurrajong Curve Study'),
    make('inter-fitted', 'Cedar Nine Study', SOURCES / 'inter/Inter[opsz,wght].ttf'),
    make('nimbus-fitted', 'Harbor Nine Study', SOURCES / 'nimbus/NimbusSans-Regular.ttf'),
]
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Created and validated three 95-glyph optical studies; original Apple artwork was not used.')
