"""User-requested whole-pixel move right for i, retaining aligned l and T."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.ttProgram import Program

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
font = TTFont(OUT / 'Coppet-Round5-IL-unhinted.ttf')
g = font['glyf']['uni0069']
for index, (x, y) in enumerate(g.coordinates):
    g.coordinates[index] = (x + 100, y)
g.recalcBounds(font['glyf'])
font['hmtx']['uni0069'] = (300, g.xMin)
for record in list(font['name'].names):
    if record.nameID in [3, 5]:
        text = 'Coppet-Regular-Study-0.021' if record.nameID == 3 else 'Version 0.021; Inter-derived Geneva 9 optical refinement'
        font['name'].setName(text, record.nameID, record.platformID, record.platEncID, record.langID)
font.recalcTimestamp = False
unhinted = OUT / 'Coppet-Round6-Right-unhinted.ttf'
hinted = OUT / 'Coppet-Round6-Right.ttf'
font.save(unhinted)
subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0', '-a', 'qsq', str(unhinted), str(hinted)], check=True)
font = TTFont(hinted)
# i's outline is now already in its accepted guest position; omit its old
# +1-pixel guest hint. Preserve l's existing size-specific foot protection.
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
report = {'version': '0.021', 'source': 'Coppet-Round5-IL-unhinted.ttf',
    'change': 'i outline +100 units / one logical pixel right; aligned l and T unchanged',
    'i_9ppem_extra_hint': 'Removed; outline now already matches accepted guest position',
    'l_9ppem_hint_64ths': 20, 'sha256': hashlib.sha256(hinted.read_bytes()).hexdigest()}
(OUT / 'round6-build-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
