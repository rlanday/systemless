"""Check round-four outlines, strict native rasters and the size-specific i hint."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
captures = Path(sys.argv[1]) / 'review'
base_dir = captures / 'round4-before'
base = TTFont(here / 'generated/Coppet-Round3-T25-unhinted.ttf')

def rows(folder):
    return {(r['target'], int(r['code'])): r for r in csv.DictReader((folder / 'glyphs.csv').open())}

def glyph(font, code):
    return font['glyf'][font.getBestCmap()[code]].compile(font['glyf'])

base_rows = rows(base_dir)
reports = []
for variant in ['Shifted', 'Aligned']:
    folder = captures / ('round4-' + variant.lower())
    font = TTFont(here / f'generated/Coppet-Round4-{variant}-unhinted.ttf')
    changed = [chr(c) for c in range(32, 127) if glyph(base, c) != glyph(font, c)]
    assert changed == ['R', 'T', 'i'], changed
    assert all(base['hmtx'][n][0] == font['hmtx'][n][0] for n in base.getGlyphOrder())
    assert (base_dir / 'guest-metrics.txt').read_bytes() == (folder / 'guest-metrics.txt').read_bytes()
    output = rows(folder)
    assert len(output) == 190 and output.keys() == base_rows.keys()
    assert (folder / 'audit-stderr.log').read_text().count('hinting_enabled=true') == 2
    changed_rows = [key for key in output if output[key] != base_rows[key]]
    assert set(changed_rows) == {('retained', ord(c)) for c in 'RTi'}, changed_rows
    # Equality above includes guest i's dot/stem and T's shaft, all placements,
    # bitmap extents and hashes, not just non-empty output.
    for target in ['guest', 'retained']:
        for code in range(33, 127):
            data = (folder / 'masks' / f'{target}-{code}.pgm').read_bytes().split(b'\n', 3)
            assert any(data[3]), (variant, target, chr(code))
    reports.append({'variant': variant, 'changed_outlines': changed,
        'all_95_advances_and_baseline_metrics_unchanged': True,
        'all_95_guest_glyphs_identical_including_masks_and_placement': True,
        'only_R_T_i_retained_rasters_change': True,
        'other_92_outlines_and_rasters_identical': True,
        'strict_interpreter_checks_passed': True,
        'font_sha256': hashlib.sha256((here / f'generated/Coppet-Round4-{variant}.ttf').read_bytes()).hexdigest()})

shifted = TTFont(here / 'generated/Coppet-Round4-Shifted-unhinted.ttf')
aligned = TTFont(here / 'generated/Coppet-Round4-Aligned-unhinted.ttf')
assert [chr(c) for c in range(32, 127) if glyph(shifted, c) != glyph(aligned, c)] == ['T']
a, b = rows(captures / 'round4-shifted'), rows(captures / 'round4-aligned')
assert [key for key in a if a[key] != b[key]] == [('retained', 84)]

with_dir, without_dir = [captures / 'round4-i-hint' / n for n in ['with-hint', 'without-hint']]
with_rows, without_rows = rows(with_dir), rows(without_dir)
assert len(with_rows) == len(without_rows) == 7
for folder in [with_dir, without_dir]:
    assert (folder / 'stderr.log').read_text().count('hinting_enabled=true') == 7
for key, row in with_rows.items():
    if int(row['ppem']) != 9:
        assert row == without_rows[key], ('hint escaped 9 ppem', key)
assert with_rows['mono9', 105] != without_rows['mono9', 105]
for field in ['width', 'height', 'left', 'top', 'hash']:
    assert with_rows['mono9', 105][field] == base_rows['guest', 105][field]
report = {'variants': reports, 'variants_differ_only_in_T': True,
    'hint_scope': 'Strict Windows audit: guest i unchanged; added hint has no effect at 8/10/36 ppem',
    'visual_review': 'User prefers aligned T stem; i and l still look soft and remain under refinement',
    'production_validation': 'GUI, clipping, guest-font precedence and native/scaled performance pending',
    'capture_sha256': {str(p.relative_to(captures)): hashlib.sha256(p.read_bytes()).hexdigest()
        for case in ['before','shifted','aligned','original']
        for p in sorted((captures / ('round4-' + case)).glob('*.png'))}}
(here / 'validation-round4.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'capture_sha256'}, indent=2))
