"""Check round-two native captures. Usage: python verify-round2.py CAPTURE_ROOT.

CAPTURE_ROOT contains review/round2-{before,plain,foot}. Run audit-detail.rs
and render-round2.rs on Windows first. This verifies scope and raster survival,
not whether a human prefers the optical changes.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
captures = Path(sys.argv[1]) / 'review'
before_dir = captures / 'round2-before'
before = TTFont(here / 'generated/Coppet-Refined-unhinted.ttf')
allowed = set('cjlrst')

def glyph_bytes(font, code):
    return font['glyf'][font.getBestCmap()[code]].compile(font['glyf'])

def rows(folder):
    result = list(csv.DictReader((folder / 'glyphs.csv').open()))
    assert len(result) == 190
    return {(r['target'], int(r['code'])): r for r in result}

def pixels(folder, row):
    magic, size, maximum, data = (folder / 'masks' /
        f"{row['target']}-{row['code']}.pgm").read_bytes().split(b'\n', 3)
    w, h = map(int, size.split())
    assert magic == b'P5' and maximum == b'255' and len(data) == w * h
    assert (w, h) == (int(row['width']), int(row['height']))
    return {(int(row['left']) + x, int(row['top']) - y - 1): data[y * w + x]
            for y in range(h) for x in range(w) if data[y * w + x]}

control_rows = rows(before_dir)
reports = []
for variant in ['Plain', 'Foot']:
    folder = captures / ('round2-' + variant.lower())
    font = TTFont(here / f'generated/Coppet-Round2-{variant}-unhinted.ttf')
    hinted = here / f'generated/Coppet-Round2-{variant}.ttf'
    changed = [chr(c) for c in range(32, 127) if glyph_bytes(before, c) != glyph_bytes(font, c)]
    assert set(changed) == allowed, changed
    assert all(before['hmtx'][n][0] == font['hmtx'][n][0] for n in before.getGlyphOrder())
    assert (before_dir / 'guest-metrics.txt').read_bytes() == (folder / 'guest-metrics.txt').read_bytes()
    for field in ['ascent', 'descent', 'lineGap', 'advanceWidthMax']:
        assert getattr(before['hhea'], field) == getattr(font['hhea'], field)
    candidate_rows = rows(folder)
    changed_rasters = {}
    for target, factor in [('guest', 1), ('retained', 4)]:
        changed_rasters[target] = [chr(c) for c in range(32, 127)
            if control_rows[target, c] != candidate_rows[target, c]]
        assert set(changed_rasters[target]) <= allowed
        for code in range(33, 127):
            assert pixels(folder, candidate_rows[target, code]), (variant, target, chr(code))
        dots = [{xy: v for xy, v in pixels(folder, candidate_rows[target, ord(c)]).items()
                 if xy[1] >= 5 * factor} for c in 'ij']
        assert dots[0] and dots[0] == dots[1], (variant, target, 'unequal or missing dots')
    # Keep the complete accepted i bitmap, not merely some surviving ink.
    assert (before_dir / 'masks/guest-105.pgm').read_bytes() == (folder / 'masks/guest-105.pgm').read_bytes()
    for ch in 'Demand&':
        assert glyph_bytes(before, ord(ch)) == glyph_bytes(font, ord(ch))
    reports.append({'variant': variant, 'font_sha256': hashlib.sha256(hinted.read_bytes()).hexdigest(),
        'changed_outlines': changed, 'changed_rasters': changed_rasters,
        'other_89_outlines_and_rasters_identical': True,
        'all_95_advances_and_baseline_font_metrics_unchanged': True,
        'all_94_nonspace_glyphs_have_ink_in_both_targets': True,
        'i_and_j_dot_pixels_identical_in_both_targets': True,
        'accepted_i_guest_bitmap_unchanged': True, 'Demand_and_ampersand_unchanged': True})

plain = TTFont(here / 'generated/Coppet-Round2-Plain-unhinted.ttf')
foot = TTFont(here / 'generated/Coppet-Round2-Foot-unhinted.ttf')
assert [chr(c) for c in range(32, 127) if glyph_bytes(plain, c) != glyph_bytes(foot, c)] == ['l']
plain_rows, foot_rows = rows(captures / 'round2-plain'), rows(captures / 'round2-foot')
assert all(plain_rows[k] == foot_rows[k] for k in plain_rows if k[1] != ord('l'))
report = {'variants': reports, 'variants_differ_only_in_lowercase_l': True,
    'native_tests': 'Windows; Skrifa 0.43.2 / zeno; same frozen Systemless library for all cases',
    'visual_review': 'Pending; Tool T-o pair remains unchanged, compare in actual Geneva 9 bold style',
    'production_validation': 'Interaction, clipping, guest-font precedence and native/scaled performance pending',
    'capture_sha256': {str(p.relative_to(captures)): hashlib.sha256(p.read_bytes()).hexdigest()
        for name in ['before', 'plain', 'foot', 'original']
        for p in sorted((captures / ('round2-' + name)).glob('*.png'))}}
(here / 'validation-round2.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'capture_sha256'}, indent=2))
