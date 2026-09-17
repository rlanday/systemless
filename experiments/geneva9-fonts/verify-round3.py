"""Verify round-three native Windows captures; see round3-review.md."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
captures = Path(sys.argv[1]) / 'review'
base_dir = captures / 'round3-before'
base = TTFont(here / 'generated/Coppet-Round2-Foot-unhinted.ttf')

def rows(folder):
    return {(r['target'], int(r['code'])): r for r in csv.DictReader((folder / 'glyphs.csv').open())}

def pixels(folder, row):
    magic, size, maximum, data = (folder / 'masks' / f"{row['target']}-{row['code']}.pgm").read_bytes().split(b'\n', 3)
    w, h = map(int, size.split())
    assert magic == b'P5' and maximum == b'255' and len(data) == w * h
    return {(int(row['left']) + x, int(row['top']) - y - 1): data[y * w + x]
        for y in range(h) for x in range(w) if data[y * w + x]}

def normalized(points):
    x0 = min(x for x, y in points)
    y0 = min(y for x, y in points)
    return {(x-x0, y-y0): v for (x, y), v in points.items()}

def outlines(font, code):
    return font['glyf'][font.getBestCmap()[code]].compile(font['glyf'])

base_rows = rows(base_dir)
assert len(base_rows) == 190
reports = []
for variant in ['Weight', 'T25', 'T100']:
    folder = captures / ('round3-' + variant.lower())
    candidate = TTFont(here / f'generated/Coppet-Round3-{variant}-unhinted.ttf')
    allowed = set('Pijly' + ('T' if variant != 'Weight' else ''))
    changed = [chr(c) for c in range(32, 127) if outlines(base, c) != outlines(candidate, c)]
    assert set(changed) == allowed
    assert all(base['hmtx'][n][0] == candidate['hmtx'][n][0] for n in base.getGlyphOrder())
    assert (base_dir / 'guest-metrics.txt').read_bytes() == (folder / 'guest-metrics.txt').read_bytes()
    candidate_rows = rows(folder)
    assert candidate_rows.keys() == base_rows.keys()
    changed_rasters = {}
    for target in ['guest', 'retained']:
        changed_rasters[target] = [chr(c) for c in range(32, 127)
            if base_rows[target, c] != candidate_rows[target, c]]
        assert set(changed_rasters[target]) <= allowed
        for code in range(33, 127):
            assert pixels(folder, candidate_rows[target, code]), (variant, target, chr(code))
        for code in range(32, 127):
            if chr(code) not in allowed:
                assert base_rows[target, code] == candidate_rows[target, code]
    # The new hint must preserve the complete accepted one-bit i, including
    # its dot and its position relative to the pen, not merely some ink.
    assert pixels(base_dir, base_rows['guest', 105]) == pixels(folder, candidate_rows['guest', 105])
    for target, factor in [('guest', 1), ('retained', 4)]:
        dots = [{xy: v for xy, v in pixels(folder, candidate_rows[target, ord(ch)]).items()
                 if xy[1] >= 5 * factor} for ch in 'ij']
        assert dots[0] and dots[1] and normalized(dots[0]) == normalized(dots[1])
    t = pixels(folder, candidate_rows['guest', 84])
    assert all(any(y == row for x, y in t) for row in range(7)), 'T stem disappeared'
    changed_guest_ink = [chr(c) for c in range(33, 127)
        if pixels(base_dir, base_rows['guest', c]) != pixels(folder, candidate_rows['guest', c])]
    assert changed_guest_ink == (['T'] if variant == 'T100' else []), changed_guest_ink
    for ch in 'Demand&':
        assert outlines(base, ord(ch)) == outlines(candidate, ord(ch))
    reports.append({'variant': variant, 'changed_outlines': changed,
        'changed_raster_metadata_or_pixels': changed_rasters,
        'changed_guest_ink_positions': changed_guest_ink,
        'all_95_advances_and_baseline_metrics_unchanged': True,
        'all_other_outlines_and_rasters_identical': True,
        'i_guest_dot_stem_and_position_preserved': True,
        'i_j_dot_shapes_equal': True, 'T_guest_stem_intact': True,
        'Demand_and_ampersand_unchanged': True,
        'font_sha256': hashlib.sha256((here / f'generated/Coppet-Round3-{variant}.ttf').read_bytes()).hexdigest()})

rejected_dir = captures / 'round3-t50-auditonly'
rejected_t = pixels(rejected_dir, rows(rejected_dir)['guest', 84])
assert not any(y < 6 for x, y in rejected_t), 'Expected rejection reason changed; reassess trial'

with_dir, without_dir = [captures / 'round3-i-hint' / n for n in ['with-hint', 'without-hint']]
with_rows, without_rows = rows(with_dir), rows(without_dir)
assert len(with_rows) == len(without_rows) == 7
for key, r in with_rows.items():
    assert 'hinting_enabled=true' in (with_dir / 'stderr.log').read_text()
    if int(r['ppem']) != 9:
        assert r == without_rows[key], ('hint escaped 9 ppem', r)
assert with_rows['mono9', 105] != without_rows['mono9', 105]
assert any(y >= 5 for x, y in pixels(with_dir, with_rows['mono9', 105]))
assert not any(y >= 5 for x, y in pixels(without_dir, without_rows['mono9', 105]))

report = {'variants': reports,
    'strict_hint_check': 'Windows Skrifa pedantic mode: hint enabled; 8/10/36 ppem unchanged; 9 ppem mono dot restored',
    'rejected_trial': 'T50-AuditOnly: half-pixel translation removes all T guest stem pixels below crossbar',
    'visual_review': 'User selected small T shift and curved-foot l shape; other weight/spacing changes still need adjustment',
    'production_validation': 'GUI, clipping, guest-font precedence and native/scaled performance pending',
    'capture_sha256': {str(p.relative_to(captures)): hashlib.sha256(p.read_bytes()).hexdigest()
        for case in ['before','weight','t25','t100','original']
        for p in sorted((captures / ('round3-' + case)).glob('*.png'))}}
(here / 'validation-round3.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'capture_sha256'}, indent=2))
