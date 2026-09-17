"""Verify scope, native glyphs and captures of the R/&/i optical trials."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
captures = Path(sys.argv[1]) / 'review'
baseline = TTFont(HERE / 'generated/Coppet-Round6-Right-unhinted.ttf')
before_dir = captures / 'round6-right'


def rows(folder):
    return {(r['target'], int(r['code'])): r
        for r in csv.DictReader((folder / 'glyphs.csv').open())}


def mask(folder, target, ch):
    _, dimensions, _, data = (folder / 'masks' / f'{target}-{ord(ch)}.pgm').read_bytes().split(b'\n', 3)
    width, height = map(int, dimensions.split())
    assert len(data) == width * height
    return width, height, data


def native_pixel(folder, ch, x, y):
    # Area-average the retained 4x glyph in logical coordinates. y is
    # screen-relative to baseline (negative above it), x relative to pen.
    r = rows(folder)['retained', ord(ch)]
    left, top = int(r['left']), int(r['top'])
    w, h, pixels = mask(folder, 'retained', ch)
    total = 0
    for sy in range(y * 4, (y + 1) * 4):
        for sx in range(x * 4, (x + 1) * 4):
            if 0 <= sx - left < w and 0 <= sy + top < h:
                total += pixels[(sy + top) * w + sx - left]
    return round(total / 16, 2)


a = rows(before_dir)
reports = []
for variant, chars in [('Sharp', '&R'), ('Entry', 'i'), ('Combined', '&Ri')]:
    folder = captures / f'round7-{variant.lower()}'
    font = TTFont(HERE / f'generated/Coppet-Round7-{variant}-unhinted.ttf')
    changed = [chr(c) for c in range(32, 127) if
        baseline['glyf'][baseline.getBestCmap()[c]].compile(baseline['glyf']) !=
        font['glyf'][font.getBestCmap()[c]].compile(font['glyf'])]
    assert changed == list(chars), changed
    assert all(baseline['hmtx'][n][0] == font['hmtx'][n][0] for n in baseline.getGlyphOrder())
    assert (before_dir / 'guest-metrics.txt').read_bytes() == (folder / 'guest-metrics.txt').read_bytes()
    b = rows(folder)
    assert len(a) == len(b) == 190 and a.keys() == b.keys()
    changed_guest = [chr(code) for target, code in a if target == 'guest' and a[target, code] != b[target, code]]
    changed_retained = [chr(code) for target, code in a if target == 'retained' and a[target, code] != b[target, code]]
    assert changed_guest == [ch for ch in chars if ch != 'R']
    assert changed_retained == list(chars)
    for target, code in a:
        if chr(code) not in chars or (target == 'guest' and chr(code) == 'R'):
            filename = f'{target}-{code}.pgm'
            assert (before_dir / 'masks' / filename).read_bytes() == (folder / 'masks' / filename).read_bytes()
        if code != 32:
            assert any(mask(folder, target, chr(code))[2]), (variant, target, code)
    assert (folder / 'audit-stderr.log').read_text().count('hinting_enabled=true') == 2
    if 'i' in chars:
        old, new = baseline['glyf']['uni0069'], font['glyf']['uni0069']
        assert list(old.coordinates[4:]) == list(new.coordinates[6:])
        assert list(old.flags[4:]) == list(new.flags[6:])
        w, h, pixels = mask(folder, 'guest', 'i')
        assert (w, h) == (2, 7)
        assert pixels == bytes([0, 255, 0, 0, 255, 255] + [0, 255] * 4)
    for ch in '&R':
        old, new = baseline['glyf'][baseline.getBestCmap()[ord(ch)]], font['glyf'][font.getBestCmap()[ord(ch)]]
        assert (old.xMin, old.xMax, old.yMin, old.yMax) == (new.xMin, new.xMax, new.yMin, new.yMax)
    reports.append({'variant': variant, 'changed_outlines': changed,
        'changed_guest_glyphs': changed_guest, 'changed_retained_glyphs': changed_retained,
        'all_95_advances_and_baseline_metrics_unchanged': True,
        'unrelated_glyphs_pixel_identical': True, 'R_guest_mask_identical': True,
        'all_nonspace_guest_glyphs_have_ink': True, 'strict_native_hint_checks_passed': True,
        'font_sha256': hashlib.sha256((HERE / f'generated/Coppet-Round7-{variant}.ttf').read_bytes()).hexdigest()})
    for name in ['samples-100', 'samples-138', 'samples-400', 'city-100', 'city-138', 'new-city-100', 'new-city-138']:
        assert (folder / (name + '.png')).is_file(), (variant, name)

sharp_dir = captures / 'round7-sharp'
coverage = {label: {'R_middle_bar_row': native_pixel(folder, 'R', 1, -4),
    'R_row_below_bar': native_pixel(folder, 'R', 1, -3),
    'ampersand_upper_left_side': native_pixel(folder, '&', 1, -6),
    'ampersand_upper_counter': [native_pixel(folder, '&', x, -6) for x in [2, 3]],
    'ampersand_upper_right_side': native_pixel(folder, '&', 4, -6)}
    for label, folder in [('before', before_dir), ('after', sharp_dir)]}
assert coverage['after']['R_middle_bar_row'] > coverage['before']['R_middle_bar_row']
assert coverage['after']['R_row_below_bar'] == 0
assert max(coverage['after']['ampersand_upper_counter']) < min(coverage['before']['ampersand_upper_counter'])
result = {'variants': reports, 'native_coverage_0_to_255': coverage,
    'scope': 'Optical study only, unchanged renderer; these changes selected, broader glyph review and production validation pending',
    'visual_review': 'User selected both changes; Combined 0.024 is the new comparison baseline',
    'capture_sha256': {str(p.relative_to(captures)): hashlib.sha256(p.read_bytes()).hexdigest()
        for variant in ['sharp', 'entry', 'combined']
        for p in sorted((captures / ('round7-' + variant)).glob('*.png'))}}
(HERE / 'validation-round7.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'capture_sha256'}, indent=2))
