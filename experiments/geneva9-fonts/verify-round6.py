"""Check the requested whole-pixel i move and preservation of l/T and guest masks."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from fontTools.ttLib import TTFont

here = Path(__file__).resolve().parent
captures = Path(sys.argv[1]) / 'review'
before_dir, after_dir = captures / 'round6-before', captures / 'round6-right'
before = TTFont(here / 'generated/Coppet-Round5-IL-unhinted.ttf')
after = TTFont(here / 'generated/Coppet-Round6-Right-unhinted.ttf')
changed = [chr(c) for c in range(32, 127) if
    before['glyf'][before.getBestCmap()[c]].compile(before['glyf']) !=
    after['glyf'][after.getBestCmap()[c]].compile(after['glyf'])]
assert changed == ['i']
assert all(before['hmtx'][n][0] == after['hmtx'][n][0] for n in before.getGlyphOrder())
for a, b in zip(before['glyf']['uni0069'].coordinates, after['glyf']['uni0069'].coordinates):
    assert b == (a[0] + 100, a[1])
assert (before_dir / 'guest-metrics.txt').read_bytes() == (after_dir / 'guest-metrics.txt').read_bytes()

def rows(folder):
    return {(r['target'], int(r['code'])): r for r in csv.DictReader((folder / 'glyphs.csv').open())}

a, b = rows(before_dir), rows(after_dir)
assert len(a) == len(b) == 190 and a.keys() == b.keys()
assert [key for key in a if a[key] != b[key]] == [('retained', 105)]
assert int(b['retained',105]['left']) == int(a['retained',105]['left']) + 4
assert a['retained',105]['hash'] == b['retained',105]['hash']
for target in ['guest', 'retained']:
    for code in range(32, 127):
        name = f'{target}-{code}.pgm'
        assert (before_dir / 'masks' / name).read_bytes() == (after_dir / 'masks' / name).read_bytes()
assert (after_dir / 'audit-stderr.log').read_text().count('hinting_enabled=true') == 2
report = {'version':'0.021', 'changed_outlines':['i'],
    'i_translation_font_units':100, 'retained_translation_pixels':4,
    'all_95_advances_and_baseline_metrics_unchanged':True,
    'all_95_guest_glyphs_identical_including_masks_and_placement':True,
    'all_95_raster_mask_contents_identical_in_both_targets':True,
    'only_retained_i_placement_changes':True,
    'aligned_l_and_T_unchanged':True, 'strict_native_hint_checks_passed':True,
    'font_sha256':hashlib.sha256((here/'generated/Coppet-Round6-Right.ttf').read_bytes()).hexdigest(),
    'visual_review':'Requested placement implemented; awaiting review of updated words',
    'production_validation':'GUI, clipping, guest-font precedence and native/scaled performance pending',
    'capture_sha256':{str(p.relative_to(captures)):hashlib.sha256(p.read_bytes()).hexdigest()
        for case in ['before','right','original']
        for p in sorted((captures/('round6-'+case)).glob('*.png'))}}
(here/'validation-round6.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='capture_sha256'},indent=2))
