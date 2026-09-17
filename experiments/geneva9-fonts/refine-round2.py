"""Second optical review: shared narrow stems/dots, shorter r, lighter s.

Keep version 0.010 as the comparison baseline. Generate a plain-l candidate
and a separate candidate using Inter's existing l.ss02 alternate. Guest
advance widths remain fixed; neither candidate enables kerning.
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

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
PARAMETERS = {
    'narrow_stem': 72,  # close to accepted m (73–74) and i (71)
    'plain_l_left': 25,
    'r_left': 20,
    'r_width': 340,
    'c_right': 450,
    's_weight': 360,
}
baseline = TTFont(OUT / 'Coppet-Refined-unhinted.ttf')
font = copy.deepcopy(baseline)

def glyph(f, char):
    return f['glyf'][f.getBestCmap()[ord(char)]]

def edit(char, transform):
    g = glyph(font, char)
    for index, (x, y) in enumerate(g.coordinates):
        g.coordinates[index] = tuple(round(v) for v in transform(index, x, y))
    g.recalcBounds(font['glyf'])

# Extend c's open side without widening its left stroke. This reduces the
# c-i gap while retaining the accepted i's clear native-size pixel phase.
edit('c', lambda i, x, y: (x if x <= 80 else 80 + (x - 80) * (PARAMETERS['c_right'] - 80) / 320, y))
edit('l', lambda i, x, y: (PARAMETERS['plain_l_left'] + (x - 100) * PARAMETERS['narrow_stem'] / 80, y))
edit('r', lambda i, x, y: (
    PARAMETERS['r_left'] + (x * PARAMETERS['narrow_stem'] / 80 if x <= 80 else
    PARAMETERS['narrow_stem'] + (x - 80) * (PARAMETERS['r_width'] - PARAMETERS['narrow_stem']) / 320), y))

t = glyph(font, 't')
center = (87 + 167) / 2
edit('t', lambda i, x, y: (
    center - PARAMETERS['narrow_stem'] / 2 if i > t.endPtsOfContours[0] and x == 87 else
    center + PARAMETERS['narrow_stem'] / 2 if i > t.endPtsOfContours[0] and x == 167 else x, y))

# Share the exact i dot, including its position/height. Move j's shaft center
# from 137 to i's 150 without changing the existing 80-unit shaft width.
j = glyph(font, 'j')
edit('j', lambda i, x, y: (x + 13 if x >= 97 else x * 110 / 97, y)
     if i <= j.endPtsOfContours[0] else (x, y))
i_glyph = glyph(font, 'i')
i_start, j_start = i_glyph.endPtsOfContours[0] + 1, j.endPtsOfContours[0] + 1
assert len(i_glyph.coordinates) - i_start == len(j.coordinates) - j_start
for offset in range(len(i_glyph.coordinates) - i_start):
    j.coordinates[j_start + offset] = i_glyph.coordinates[i_start + offset]
    j.flags[j_start + offset] = i_glyph.flags[i_start + offset]
j.recalcBounds(font['glyf'])

def instance(weight):
    return instantiateVariableFont(TTFont(HERE / 'sources/inter/Inter[opsz,wght].ttf'),
                                   {'wght': weight, 'opsz': 14}, inplace=True)

def transformed(source, name, transform):
    recording = DecomposingRecordingPen(source.getGlyphSet())
    source.getGlyphSet()[name].draw(recording)
    pen = TTGlyphPen(None)
    recording.replay(TransformPen(pen, transform))
    return pen.glyph()

lighter = instance(PARAMETERS['s_weight'])
s_name = lighter.getBestCmap()[ord('s')]
s = lighter['glyf'][s_name]
sx, sy = 400 / (s.xMax - s.xMin), 500 / (s.yMax - s.yMin)
font['glyf']['uni0073'] = transformed(lighter, s_name, (sx, 0, 0, sy, -sx * s.xMin, -sy * s.yMin))

reports = []
for variant, version in [('Plain', '0.011'), ('Foot', '0.012')]:
    candidate = copy.deepcopy(font)
    if variant == 'Foot':
        source = instance(400)
        # Inter's existing curved-foot alternate, not traced Apple artwork.
        # Its vertical stem is 180 units. Keep the shared 72-unit width,
        # seven-pixel ascender and the same leading space as the plain trial.
        sx, sy = PARAMETERS['narrow_stem'] / 180, 700 / 1490
        candidate['glyf']['uni006C'] = transformed(source, 'l.ss02',
            (sx, 0, 0, sy, PARAMETERS['plain_l_left'] - sx * 158, 0))
    for char in 'cjlrst':
        name = candidate.getBestCmap()[ord(char)]
        g = candidate['glyf'][name]
        g.recalcBounds(candidate['glyf'])
        candidate['hmtx'][name] = (baseline['hmtx'][name][0], g.xMin)
    for record in list(candidate['name'].names):
        if record.nameID in [3, 5]:
            text = f'Coppet-Regular-Study-{version}' if record.nameID == 3 else f'Version {version}; Inter-derived Geneva 9 optical refinement'
            candidate['name'].setName(text, record.nameID, record.platformID, record.platEncID, record.langID)
    candidate.recalcTimestamp = False
    unhinted = OUT / f'Coppet-Round2-{variant}-unhinted.ttf'
    hinted = OUT / f'Coppet-Round2-{variant}.ttf'
    candidate.save(unhinted)
    subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0', '-a', 'qsq',
                    str(unhinted), str(hinted)], check=True)
    result = TTFont(unhinted)
    changed = [n for n in baseline.getGlyphOrder()
               if baseline['glyf'][n].compile(baseline['glyf']) != result['glyf'][n].compile(result['glyf'])]
    assert changed == ['uni0063', 'uni006A', 'uni006C', 'uni0072', 'uni0073', 'uni0074'], changed
    assert all(baseline['hmtx'][n][0] == result['hmtx'][n][0] for n in baseline.getGlyphOrder())
    # Explicitly protect the accepted Demand and ampersand treatment.
    for ch in 'Demand&':
        assert glyph(baseline, ch).compile(baseline['glyf']) == glyph(result, ch).compile(result['glyf'])
    reports.append({'variant': variant, 'version': version, 'changed_outlines': changed,
        'advances_unchanged': True, 'Demand_and_ampersand_unchanged': True,
        'parameters': PARAMETERS, 'sha256': hashlib.sha256(hinted.read_bytes()).hexdigest()})
(OUT / 'round2-build-validation.json').write_text(json.dumps(reports, indent=2) + '\n')
print(json.dumps(reports, indent=2))
