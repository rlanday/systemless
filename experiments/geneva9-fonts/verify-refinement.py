"""Validate native Windows glyph captures against the accepted t-only study.

Usage: python verify-refinement.py /path/to/font-candidates
Run audit-detail.rs and render-spacing.rs on Windows first; see the report.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
captures = Path(sys.argv[1]) / 'review'
before_dir, after_dir = captures / 'spacing-before', captures / 'spacing-refined'
before_font = here / 'generated/Coppet-Regular-unhinted.ttf'
after_font = here / 'generated/Coppet-Refined-unhinted.ttf'
hinted_font = here / 'generated/Coppet-Refined.ttf'
before, after = TTFont(before_font), TTFont(after_font)
allowed = set('&cijlmrt')
changed_outlines = [chr(code) for code in range(32, 127)
    if before['glyf'][before.getBestCmap()[code]].compile(before['glyf']) !=
       after['glyf'][after.getBestCmap()[code]].compile(after['glyf'])]
assert set(changed_outlines) == allowed, changed_outlines
assert all(before['hmtx'][n][0] == after['hmtx'][n][0] for n in before.getGlyphOrder())
assert (before_dir / 'guest-metrics.txt').read_bytes() == (after_dir / 'guest-metrics.txt').read_bytes()
rows_before = list(csv.DictReader((before_dir / 'glyphs.csv').open()))
rows_after = list(csv.DictReader((after_dir / 'glyphs.csv').open()))
assert len(rows_before) == len(rows_after) == 190
changed_rasters = {}
for target in ['guest', 'retained']:
    changed = []
    for a, b in zip(rows_before, rows_after):
        assert (a['target'], a['code']) == (b['target'], b['code'])
        if a['target'] == target and a != b:
            changed.append(chr(int(a['code'])))
    assert set(changed) <= allowed, changed
    changed_rasters[target] = changed
    for code in range(33, 127):
        magic, size, max_value, pixels = (after_dir / 'masks' / f'{target}-{code}.pgm').read_bytes().split(b'\n', 3)
        w, h = map(int, size.split())
        assert magic == b'P5' and max_value == b'255' and len(pixels) == w * h
        assert any(pixels), (target, chr(code), 'unexpected blank glyph')

# Non-empty alone is insufficient: i's dot can disappear while its stem
# survives. Require the full guest i/l images to match their earlier masks.
# Their translated origin is allowed to differ; their advances are not.
for code in map(ord, 'il'):
    name = f'guest-{code}.pgm'
    assert (before_dir / 'masks' / name).read_bytes() == (after_dir / 'masks' / name).read_bytes(), chr(code)

pixel_hashes = {}
for folder in [before_dir, after_dir, captures / 'spacing-after', captures / 'spacing-original', captures / 'coppet']:
    for path in sorted(folder.glob('*.png')):
        pixel_hashes[str(path.relative_to(captures))] = hashlib.sha256(path.read_bytes()).hexdigest()
report = {'version': '0.010', 'font_sha256': hashlib.sha256(hinted_font.read_bytes()).hexdigest(),
    'font_family': TTFont(hinted_font)['name'].getDebugName(1),
    'changed_outlines': changed_outlines, 'changed_rasters': changed_rasters,
    'other_87_outline_and_raster_images_identical': True,
    'all_95_advances_unchanged': True, 'baseline_font_metrics_unchanged': True,
    'all_94_nonspace_glyphs_have_ink_in_both_targets': True,
    'guest_i_dot_and_stem_and_l_mask_preserved': True,
    'native_tests': 'Windows, Skrifa 0.43.2 / zeno; same frozen Systemless library for both cases',
    'game_text': 'Citizens Demand Road&Rail',
    'visual_review': 'Earlier spacing/stem treatment preferred; final c/i/l refinement awaiting review',
    'production_validation': 'Interaction, clipping, guest-font precedence and native/scaled performance pending',
    'capture_sha256': pixel_hashes}
(here / 'validation-refinement.json').write_text(json.dumps(report, indent=2) + '\n')
t_report = json.loads((here / 'validation-t.json').read_text())
t_report['font_sha256'] = hashlib.sha256((here / 'generated/Coppet-Regular.ttf').read_bytes()).hexdigest()
t_report['visual_review'] = 't proportions accepted by user'
(here / 'validation-t.json').write_text(json.dumps(t_report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'capture_sha256'}, indent=2))
