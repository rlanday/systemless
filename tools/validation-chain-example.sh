cd /home/rlanday/src/systemless/target/windows-validation
source /home/rlanday/src/systemless/target/windows-tools/env.sh; export CARGO_BUILD_JOBS=1

suite() { t=$1
  find systemless-$t/src -type f -exec touch {} +
  (cd systemless-$t && timeout 7000 cargo test --profile ci-test --lib --no-default-features --features jit,test-support --target-dir ../mojo-test-target > ../opus-$t-suite.log 2>&1)
  grep -q "Compiling systemless v" opus-$t-suite.log || { echo "$t suite: DID NOT COMPILE THE TREE"; return 1; }
  echo "$t suite: $(grep -E 'test result' opus-$t-suite.log | tail -1)"
  grep -q "test result: ok" opus-$t-suite.log
}
desk() { t=$1
  find systemless-$t/src -type f -exec touch {} +
  (cd systemless-$t && timeout 5000 cargo build --release --target x86_64-pc-windows-gnu --bin systemless --target-dir ../desk-target-$t > ../opus-desk-$t.log 2>&1) || { echo "$t desktop build failed"; tail -3 opus-desk-$t.log; return 1; }
  cp -f desk-target-$t/x86_64-pc-windows-gnu/release/systemless.exe opus-desk-$t.exe; rm -f opus-desk-$t-manifest.json
}
ev() { rm -rf opus-desk-ev-$1-$2; powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(wslpath -w run-opus-ev.ps1)" -Run opus-desk-ev-$1-$2 -Binary "$(wslpath -w opus-desk-$1.exe)" -Mode public -Ticks $2 -ExactnessOnly -InputScript "$(wslpath -w default-on-ev-public-diagnostic/frozen-input.txt)" < /dev/null > opus-desk-ev-$1-$2.out 2>&1; python3 -c "import json;r=json.load(open('opus-desk-ev-$1-$2/ticks-$2/result.json'));print('EV $1 $2',r['state_sha256'][:12],r['image_sha256'][:12],'%.1f'%r['cpu_seconds'])"; }
sc2k() { n=$1; t=$2
  find systemless-$t/src -type f -exec touch {} +
  timeout 3500 python3 build-opus-$n.py --platform linux > opus-$n-build.out 2>&1 || { echo "STACK STOPPED: $n linux build"; tail -5 opus-$n-build.out; return 1; }
  timeout 900 python3 run-opus-$n-linux.py public a | tail -1
  python3 check-linux-exact.py opus-m4-linux-public-a opus-$n-linux-public-a
  S=$PWD/opus-$n-scratch; W=$PWD
  for i in 1 2 3 4 5 6; do if [ $((i%2)) -eq 1 ]; then o="opus-m4-linux-profile opus-$n-linux-profile"; else o="opus-$n-linux-profile opus-m4-linux-profile"; fi; for v in $o; do rm -rf $S && mkdir -p $S && cp sc2k-expanded-test.kpak $S/; (cd $S && env -u RUST_BACKTRACE M68K_NATIVE_REGIONS=public PROFILE_FIRE=1 timeout 300 python3 $W/opus-measure-retired.py --repeat 1 -- $W/$v $S/sc2k-expanded-test.kpak $S 2>&1 | grep "run 0:" | sed "s/^/$v /"); done; done > opus-$n-cycles.txt; rm -rf $S
  python3 - "$n" <<'PY'
import statistics as st, sys
n=sys.argv[1]; d={}
for l in open(f'opus-{n}-cycles.txt'):
    r=l.split(); vals=dict(x.split('=') for x in r if '=' in x)
    d.setdefault(r[0],[]).append({k:int(v.replace(',','')) for k,v in vals.items()})
b=d['opus-m4-linux-profile']; f=d[f'opus-{n}-linux-profile']
for k in ['instructions','cycles']:
    bm=st.median(x[k] for x in b); fm=st.median(x[k] for x in f)
    print(f"{n} {k:13} median {100*(fm-bm)/bm:+.2f}%  paired {[round((f[i][k]-b[i][k])/b[i][k]*100,2) for i in range(len(b))]}")
PY
}
suite follow || { echo "FOLLOW STOPPED"; exit 1; }
sc2k follow follow
desk follow || { echo "FOLLOW STOPPED"; exit 1; }
ev follow 9000
for i in 1 2; do for w in master4 follow; do for k in 2400 3000; do ev $w $k; done; done; done
rm -rf opus-ev-stacks-follow-2400 opus-ev-stacks-follow-3000
for k in 2400 3000; do powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(wslpath -w run-opus-ev-sampled-stacks.ps1)" -Run opus-ev-stacks-follow-$k -Binary opus-desk-follow.exe -Ticks $k < /dev/null; done
python3 - <<'PY2'
a=sum(1 for _ in open('opus-ev-stacks-follow-2400/samples.csv'))-1
rows=open('opus-ev-stacks-follow-3000/samples.csv').read().splitlines()
open('opus-ev-stacks-follow-3000/window.csv','w').write('\n'.join([rows[0]]+rows[1+a:])+'\n')
PY2
python3 opus-evstack.py opus-ev-stacks-follow-3000/window.csv opus-desk-follow.exe 50 > opus-ev-stacks-follow-window.txt
echo "FOLLOW EV DONE"
suite pr6 || echo "PR6 SUITE FAILED"
sc2k pr6 pr6
suite pr7 || echo "PR7 SUITE FAILED"
for t in benchm4 benchpr6; do
  find systemless-$t/src -type f -exec touch {} +
  (cd systemless-$t && timeout 7000 cargo test --profile fast --lib --no-default-features --features jit,test-support --target-dir ../bench-target-$t -- --ignored --nocapture --test-threads 1 text_operation_costs > ../opus-bench2-$t.log 2>&1); echo "$t: $(grep -E 'test result' opus-bench2-$t.log | tail -1)"
done
echo "FOLLOW ALL DONE"
