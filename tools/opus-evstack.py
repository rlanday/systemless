"""Inclusive/self profile of sample-stacks.exe CSV for a Systemless EV frontend exe."""
import bisect,collections,re,subprocess,sys
csv,exe=sys.argv[1],sys.argv[2]; top=int(sys.argv[3]) if len(sys.argv)>3 else 40
syms=[]
for l in subprocess.run(['nm','-C','--defined-only',exe],capture_output=True,text=True).stdout.splitlines():
    a,t,n=l.split(' ',2)
    if t in 'tT':syms.append((int(a,16),re.sub(r'::h[0-9a-f]{16}$','',n)))
syms.sort();addrs=[a for a,_ in syms]
dump=subprocess.run(['objdump','-p',exe],capture_output=True,text=True).stdout
size=int(re.search(r'SizeOfImage\s+([0-9a-f]+)',dump).group(1),16)
rows=[l.rstrip('\n').split(',') for l in open(csv)][1:]
bases=collections.Counter(int(r[2],16) for r in rows)
def inside(b,v):return b<=v<b+size
allframes=[int(f,16) for r in rows for f in r[5].split(';') if f]
base=max(bases,key=lambda b:sum(inside(b,v) for v in allframes[:20000]))
def name(v):
    if not inside(base,v):return None
    i=bisect.bisect_right(addrs,v-base+0x140000000)-1
    return syms[i][1] if i>=0 else None
inc=collections.Counter();slf=collections.Counter();n=len(rows)
for r in rows:
    rip=int(r[1],16);frames=[rip]+[int(f,16) for f in r[5].split(';') if f]
    names=[name(v) for v in frames]
    slf[names[0] or f'<{hex(int(r[2],16))}>']+=1
    for s in set(x for x in names if x):inc[s]+=1
print(f'samples {n}')
print('-- inclusive');[print(f'{100*c/n:5.1f}% {s[:150]}') for s,c in inc.most_common(top)]
print('-- self');[print(f'{100*c/n:5.1f}% {s[:150]}') for s,c in slf.most_common(25)]
