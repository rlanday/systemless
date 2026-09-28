"""Exact guest/output comparison of two Linux replay directories (non-timing fields)."""
import csv,hashlib,json,sys
from pathlib import Path
TIMING={'cpu_ms','prepare_ms','compose_ms','argb_ms','export_ms','finish_ms'}
def sig(d):
    d=Path(d); out={}
    rows=list(csv.DictReader((d/'frames.csv').open(encoding='utf-8-sig')))
    out['frames']=len(rows)
    out['frame_records']=hashlib.sha256(json.dumps([{k:v for k,v in r.items() if k not in TIMING} for r in rows],sort_keys=True).encode()).hexdigest()
    out['ram']=[x['sha256'] for x in json.loads((d/'ram-sha256.json').read_text())]
    for f in sorted(d.glob('frame-*')):
        if f.suffix in {'.png','.compact','.json'}: out[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
    return out
a,b=sig(sys.argv[1]),sig(sys.argv[2])
diff=[k for k in set(a)|set(b) if a.get(k)!=b.get(k)]
print('frames',a['frames'],b['frames'],'| compared',len(a),'items |','IDENTICAL' if not diff else f'DIFFER: {sorted(diff)}')
