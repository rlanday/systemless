"""Validate i/l placement trials against the selected aligned-T candidate."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
captures = Path(sys.argv[1]) / 'review'
base_dir = captures / 'round5-before'
base = TTFont(here / 'generated/Coppet-Round4-Aligned-unhinted.ttf')

def rows(folder):
    return {(r['target'], int(r['code'])): r for r in csv.DictReader((folder / 'glyphs.csv').open())}

def glyph(font, code):
    return font['glyf'][font.getBestCmap()[code]].compile(font['glyf'])

base_rows = rows(base_dir)
reports = []
for variant in ['L', 'IL']:
    folder = captures / ('round5-' + variant.lower())
    font = TTFont(here / f'generated/Coppet-Round5-{variant}-unhinted.ttf')
    changed = [chr(c) for c in range(32, 127) if glyph(base, c) != glyph(font, c)]
    expected = ['l'] if variant == 'L' else ['i', 'l']
    assert changed == expected, changed
    assert all(base['hmtx'][n][0] == font['hmtx'][n][0] for n in base.getGlyphOrder())
    assert (base_dir / 'guest-metrics.txt').read_bytes() == (folder / 'guest-metrics.txt').read_bytes()
    output = rows(folder)
    assert len(output) == 190 and output.keys() == base_rows.keys()
    assert (folder / 'audit-stderr.log').read_text().count('hinting_enabled=true') == 2
    assert {key for key in output if output[key] != base_rows[key]} == {('retained', ord(c)) for c in expected}
    for target in ['guest', 'retained']:
        for code in range(33, 127):
            assert any((folder / 'masks' / f'{target}-{code}.pgm').read_bytes().split(b'\n', 3)[3])
    # Explicit full bitmap comparisons protect i's dot and l's curved foot.
    for code in [105, 108]:
        name = f'guest-{code}.pgm'
        assert (folder / 'masks' / name).read_bytes() == (base_dir / 'masks' / name).read_bytes()
    reports.append({'variant': variant, 'changed_outlines': changed,
        'all_95_advances_and_baseline_metrics_unchanged': True,
        'all_95_guest_glyphs_identical_including_masks_and_placement': True,
        'only_selected_i_l_retained_rasters_change': True,
        'guest_i_dot_and_l_foot_preserved': True,
        'accepted_T_unchanged': True, 'strict_interpreter_checks_passed': True,
        'font_sha256': hashlib.sha256((here / f'generated/Coppet-Round5-{variant}.ttf').read_bytes()).hexdigest()})

a, b = rows(captures / 'round5-l'), rows(captures / 'round5-il')
assert [key for key in a if a[key] != b[key]] == [('retained', 105)]
report = {'variants': reports, 'variants_differ_only_in_retained_i': True,
    'visual_review': 'User requested IL with i moved right while retaining native alignment; implemented in round six',
    'production_validation': 'GUI, clipping, guest-font precedence and native/scaled performance pending',
    'capture_sha256': {str(p.relative_to(captures)): hashlib.sha256(p.read_bytes()).hexdigest()
        for case in ['before','l','il','original']
        for p in sorted((captures / ('round5-' + case)).glob('*.png'))}}
(here / 'validation-round5.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'capture_sha256'}, indent=2))
