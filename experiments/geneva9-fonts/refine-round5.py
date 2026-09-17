"""Compare native-column placement of l alone and i/l together.

Keep the selected aligned T. These trials expose the spacing/clarity tradeoff;
they do not change character advances or dynamically hint the host compositor.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.ttProgram import Program

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
baseline = TTFont(OUT / 'Coppet-Round4-Aligned-unhinted.ttf')
reports = []
for variant, version, i_shift, hint_shift in [('L', '0.019', 0, 32), ('IL', '0.020', -50, 64)]:
    candidate = copy.deepcopy(baseline)
    for ch, shift in [('i', i_shift), ('l', -31)]:
        name = candidate.getBestCmap()[ord(ch)]
        g = candidate['glyf'][name]
        for index, (x, y) in enumerate(g.coordinates):
            g.coordinates[index] = (x + shift, y)
        g.recalcBounds(candidate['glyf'])
        candidate['hmtx'][name] = (baseline['hmtx'][name][0], g.xMin)
    for record in list(candidate['name'].names):
        if record.nameID in [3, 5]:
            text = f'Coppet-Regular-Study-{version}' if record.nameID == 3 else f'Version {version}; Inter-derived Geneva 9 optical refinement'
            candidate['name'].setName(text, record.nameID, record.platformID, record.platEncID, record.langID)
    candidate.recalcTimestamp = False
    unhinted = OUT / f'Coppet-Round5-{variant}-unhinted.ttf'
    hinted = OUT / f'Coppet-Round5-{variant}.ttf'
    candidate.save(unhinted)
    subprocess.run([os.environ.get('TTFAUTOHINT', 'ttfautohint'), '-n', '-x', '0', '-a', 'qsq', str(unhinted), str(hinted)], check=True)
    hinted_font = TTFont(hinted)
    # Preserve each accepted guest bitmap. In particular, l's shifted foot
    # otherwise quantizes into its stem column and disappears at 9 ppem.
    for glyph_name, amount in [('uni0069', hint_shift), ('uni006C', 20)]:
        g = hinted_font['glyf'][glyph_name]
        points = len(g.coordinates)
        hint = Program()
        hint.fromAssembly(['SVTCA[1]', 'MPPEM[ ]', 'PUSHB[ ]', '9', 'EQ[ ]', 'IF[ ]',
            'PUSHB[ ]', '1', 'SZP2[ ]', 'PUSHB[ ]', str(points), 'SLOOP[ ]',
            'NPUSHB[ ]', *map(str, range(points)), str(amount), 'SHPIX[ ]', 'EIF[ ]'])
        g.program.fromBytecode(bytes(g.program.getBytecode()) + bytes(hint.getBytecode()))
        hinted_font['maxp'].maxStackElements = max(hinted_font['maxp'].maxStackElements, points + 1)
    hinted_font.recalcTimestamp = False
    hinted_font.save(hinted)
    result = TTFont(unhinted)
    changed = [chr(c) for c in range(32, 127) if
        baseline['glyf'][baseline.getBestCmap()[c]].compile(baseline['glyf']) !=
        result['glyf'][result.getBestCmap()[c]].compile(result['glyf'])]
    assert changed == (['l'] if variant == 'L' else ['i', 'l'])
    assert all(baseline['hmtx'][n][0] == result['hmtx'][n][0] for n in baseline.getGlyphOrder())
    reports.append({'variant': variant, 'version': version, 'changed_outlines': changed,
        'advances_unchanged': True, 'l_translation': -31, 'i_translation': i_shift,
        'i_9ppem_hint_64ths': hint_shift, 'l_9ppem_hint_64ths': 20,
        'sha256': hashlib.sha256(hinted.read_bytes()).hexdigest()})
(OUT / 'round5-build-validation.json').write_text(json.dumps(reports, indent=2) + '\n')
print(json.dumps(reports, indent=2))
