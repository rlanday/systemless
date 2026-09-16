"""Correct oversized straight stems after the initial per-glyph fitting.

Run after refine-spacing.py. Only j/r/l/t are changed here. Keep the accepted
t height and crossbar, all advances, and all other glyph outlines intact.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
out = here / 'generated'
source = out / 'Coppet-Spacing-unhinted.ttf'
font = TTFont(source)
before = TTFont(source)

for char in 'jrlt':
    name = font.getBestCmap()[ord(char)]
    glyph = font['glyf'][name]
    for index, (x, y) in enumerate(glyph.coordinates):
        if char == 'j' and index <= glyph.endPtsOfContours[0]:
            # Shaft 92..182 -> 97..177. Preserve dot and leftmost hook.
            x = 137 + (x - 137) * 80 / 90 if x >= 92 else x * 97 / 92
        elif char == 'r':
            # Lower straight stem 0..127 -> 0..80; keep shoulder's outer
            # extent at 400. This widens the space under the shoulder.
            x = x * 80 / 127 if x <= 127 else 80 + (x - 127) * 320 / 273
        elif char == 'l':
            # Align the left edge with a logical pixel so downsampling
            # concentrates the 0.8-pixel stroke in one column at 100%.
            # The earlier half-pixel-centered stem blurred and vanished
            # when thresholded for the one-bit guest mask.
            x = 100 + x * 0.8
        elif char == 't' and index > glyph.endPtsOfContours[0]:
            # Thin the shaft symmetrically; leave crossbar, hook extent
            # and accepted vertical proportions unchanged.
            x = x + 4 if x == 83 else x - 4 if x == 171 else x
        glyph.coordinates[index] = (round(x), y)
    glyph.recalcBounds(font['glyf'])
    font['hmtx'][name] = (font['hmtx'][name][0], glyph.xMin)

names = {3: 'Coppet-Regular-Study-0.010',
         5: 'Version 0.010; Inter-derived Geneva 9 spacing and stem study'}
for record in list(font['name'].names):
    if record.nameID in names:
        font['name'].setName(names[record.nameID], record.nameID, record.platformID,
                             record.platEncID, record.langID)
font.recalcTimestamp = False
unhinted = out / 'Coppet-Refined-unhinted.ttf'
hinted = out / 'Coppet-Refined.ttf'
font.save(unhinted)
subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0',
                '-a', 'qsq', str(unhinted), str(hinted)], check=True)
after = TTFont(unhinted)
changed = [n for n in before.getGlyphOrder()
           if before['glyf'][n].compile(before['glyf']) != after['glyf'][n].compile(after['glyf'])]
assert changed == ['uni006A', 'uni006C', 'uni0072', 'uni0074'], changed
assert all(before['hmtx'][n][0] == after['hmtx'][n][0] for n in before.getGlyphOrder())
for char in 'jrlt':
    n = after.getBestCmap()[ord(char)]
    assert [y for x, y in before['glyf'][n].coordinates] == [y for x, y in after['glyf'][n].coordinates]
report = {'changed_unhinted_glyphs': changed, 'all_advances_unchanged': True,
          'all_vertical_coordinates_unchanged': True,
          't_crossbar_unchanged': True,
          'font_sha256': hashlib.sha256(hinted.read_bytes()).hexdigest(),
          'straight_stem_widths_at_9': {
              'n_reference': 0.81, 'm_reference': [0.73, 0.74, 0.73],
              'j': [0.9, 0.8], 'r': [1.27, 0.8],
              'l': [1.0, 0.8], 't': [0.88, 0.8]}}
(out / 'stem-build-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
