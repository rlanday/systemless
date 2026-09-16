"""Refine c, i, m and ampersand inside unchanged Geneva-9 advance cells.

Starts from the accepted Coppet t correction. No pair kerning or changes
to the application's logical measurements; this remains an optical study.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
out = here / 'generated'
source = out / 'Coppet-Regular-unhinted.ttf'
font = TTFont(source)
before = TTFont(source)

def widen_m(x):
    # Add half a logical pixel inside each counter. Preserve the three
    # straight stems' widths (73, 74, 73 units), unlike uniform stretching.
    if x <= 73:
        return x
    if x < 263:
        return x + (x - 73) * 50 / 190
    if x <= 337:
        return x + 50
    if x < 527:
        return x + 50 + (x - 337) * 50 / 190
    return x + 100

# Put the entire narrow i inside logical pixel column 1. This preserves
# both dot and stem in the one-bit guest mask and concentrates their native
# presentation coverage. The earlier half-pixel trial split both columns.
for char, transform in [('m', widen_m), ('i', lambda x: x + 100),
                        ('c', lambda x: x * 4 / 3), ('&', lambda x: x + 100)]:
    name = font.getBestCmap()[ord(char)]
    glyph = font['glyf'][name]
    for index, (x, y) in enumerate(glyph.coordinates):
        glyph.coordinates[index] = (round(transform(x)), y)
    glyph.recalcBounds(font['glyf'])
    advance, _ = font['hmtx'][name]
    font['hmtx'][name] = (advance, glyph.xMin)

names = {3: 'Coppet-Regular-Study-0.009',
         5: 'Version 0.009; Inter-derived Geneva 9 spacing study'}
for record in list(font['name'].names):
    if record.nameID in names:
        font['name'].setName(names[record.nameID], record.nameID, record.platformID,
                             record.platEncID, record.langID)
font.recalcTimestamp = False
unhinted = out / 'Coppet-Spacing-unhinted.ttf'
hinted = out / 'Coppet-Spacing.ttf'
font.save(unhinted)
subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0',
                '-a', 'qsq', str(unhinted), str(hinted)], check=True)
after = TTFont(unhinted)
changed = [n for n in before.getGlyphOrder()
           if before['glyf'][n].compile(before['glyf']) != after['glyf'][n].compile(after['glyf'])]
assert changed == ['uni0026', 'uni0063', 'uni0069', 'uni006D'], changed
assert all(before['hmtx'][n][0] == after['hmtx'][n][0] for n in before.getGlyphOrder())
assert before['glyf']['uni0074'].compile(before['glyf']) == after['glyf']['uni0074'].compile(after['glyf'])
report = {'changed_unhinted_glyphs': changed, 'all_advances_unchanged': True,
          'accepted_t_unchanged': True,
          'font_sha256': hashlib.sha256(hinted.read_bytes()).hexdigest(), 'glyphs': {}}
for char in 'cim&':
    n = after.getBestCmap()[ord(char)]
    report['glyphs'][char] = {}
    for label, f in [('before', before), ('after', after)]:
        g = f['glyf'][n]
        report['glyphs'][char][label] = {'advance': f['hmtx'][n][0] / 100,
            'ink_left': g.xMin / 100, 'ink_right': g.xMax / 100,
            'right_space': (f['hmtx'][n][0] - g.xMax) / 100}
(out / 'spacing-build-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
