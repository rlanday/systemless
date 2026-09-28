"""Build/freeze current-stack libraries and link the existing deterministic replay.

No measurements run here. Refuse to overwrite completed experiments. Source
hashes and Cargo's actual artifact records bind each executable to its inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

R = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--variant', choices=['worker', 'sync'], default='worker')
p.add_argument('--platform', choices=['windows', 'linux'], default='windows')
a = p.parse_args()
assert a.variant == 'worker'
stem = f'opus-follow-{a.platform}'
W = R / 'systemless-follow'
C = Path('/home/rlanday/src/systemless/target/windows-tools/cargo/registry/src/index.crates.io-1949cf8c6b5b557f/m68k-0.14.3')
target = 'x86_64-pc-windows-gnu' if a.platform == 'windows' else 'x86_64-unknown-linux-gnu'
cache = R / 'reuse-compact-frames/target'
manifest_path = R / (stem + '-manifest.json')
assert not manifest_path.exists()
h = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_new(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

def source(tree):
    names = sorted(p for p in (tree / 'src').rglob('*') if p.is_file())
    names += [tree / 'Cargo.toml', tree / 'Cargo.lock']
    if (tree / 'build.rs').exists(): names.append(tree / 'build.rs')
    return {str(p.relative_to(tree)): h(p) for p in names if p.exists()}

env = dict(os.environ, CARGO_BUILD_JOBS='1')
features = [] if a.platform == 'windows' else ['--no-default-features', '--features', 'jit']
with (R / (stem + '-metadata.json')).open('x') as out:
    subprocess.run(['cargo', 'metadata', '--offline', '--format-version=1', '--filter-platform', target, *features], cwd=W, env=env, stdout=out, check=True)
inputs = {'stack': json.loads((R/'default-on-stack.json').read_text()),
          'variant': 'batch_jit_access', 'core_commit': '0f5589062569410b7e52bac8bda6d0ac53436dda', 'candidate_patch_sha256': h(R/'batch-jit-access.patch'), 'platform': a.platform, 'systemless': source(W), 'm68k': source(C),
          'rustc': subprocess.check_output(['rustc', '-vV'], text=True),
          'cargo': subprocess.check_output(['cargo', '-V'], text=True),
          'driver_sha256': h(R/'reuse-compact-profile.rs'), 'before_build_ns': time.time_ns()}
write_new(R/(stem+'-inputs.json'), inputs)
artifacts = R/(stem+'-artifacts.jsonl')
# Shared target dir: make Cargo rebuild this tree's crate even when a sibling
# tree with the same package name/version built more recently (mtime check).
for _p in (W/'src').rglob('*'):
    if _p.is_file(): os.utime(_p)
with artifacts.open('x') as out, (R/(stem+'-cargo.log')).open('x') as log:
    subprocess.run(['cargo', 'build', '--offline', '--locked', '--release', '--lib', '--target', target,
                    '--target-dir', str(cache), '--message-format=json-render-diagnostics', *features], cwd=W, env=env, stdout=out, stderr=log, check=True)
assert source(W) == inputs['systemless'] and source(C) == inputs['m68k']
records = [json.loads(x) for x in artifacts.read_text().splitlines() if x.startswith('{')]
assert records[-1] == {'reason':'build-finished', 'success':True}
frozen = R/(stem+'-frozen'); frozen.mkdir()
files, copies, libraries = [], {}, {}
def copy(path, folder):
    path = Path(path).resolve()
    if path in copies: return copies[path]
    dest = frozen/folder/path.name; dest.parent.mkdir(exist_ok=True)
    if dest.exists(): assert h(dest) == h(path)
    else: shutil.copyfile(path, dest)
    copies[path] = dest
    files.append({'source':str(path), 'frozen':str(dest), 'sha256':h(dest)})
    return dest
for row in records:
    if row.get('reason') != 'compiler-artifact': continue
    for path in row.get('filenames', []):
        if Path(path).suffix in {'.rlib','.rmeta','.so','.dll','.a','.lib'}:
            copy(path, 'target-deps' if target in Path(path).parts else 'host-deps')
for name in ['systemless','m68k','image','serde_json']:
    row = next(r for r in reversed(records) if r.get('reason')=='compiler-artifact' and r['target']['name']==name and 'lib' in r['target']['kind'])
    path = Path(next(x for x in row['filenames'] if x.endswith('.rlib')))
    assert row['profile']['opt_level']=='3' and not row['profile']['debug_assertions']
    if name in {'systemless','m68k'}:
        assert Path(row['manifest_path']) == (W if name=='systemless' else C)/'Cargo.toml'
        assert 'jit' in row['features'] and not {'instruction-generation','trace-profile','native-code-map'}.intersection(row['features'])
    dest = copy(path,'target-deps')
    libraries[name] = {'frozen':str(dest), 'sha256':h(dest), 'features':row['features'], 'fresh':row['fresh']}
    assert name!='systemless' or not row['fresh'], 'stale systemless rlib reused'
native = set()
if a.platform=='windows':
    template=json.loads((R/'copy-snapshot-spans-master-after-link-command.json').read_text())
    native.update(x.split('=',1)[1] for x in template if x.startswith('native='))
for row in records:
    if row.get('reason')=='build-script-executed':
        for value in row.get('linked_paths',[]): native.add(value.split('=',1)[-1])
folders=[]
for n,path in enumerate(sorted(native)):
    folder=f'native-{n}'; (frozen/folder).mkdir()
    for f in Path(path).iterdir():
        if f.is_file() and (f.suffix in {'.a','.lib','.dll','.so'} or '.so.' in f.name): copy(f,folder)
    folders.append(str(frozen/folder))
driver = R/'reuse-compact-profile.rs'
if a.platform=='linux':
    driver=R/(stem+'-driver.rs')
    original=(R/'reuse-compact-profile.rs').read_text()
    start=original.index('#[link(name="kernel32")]')
    end=original.index('fn main(){',start)
    replacement='fn qpc() -> i64 { use std::sync::OnceLock; static EPOCH: OnceLock<std::time::Instant> = OnceLock::new(); EPOCH.get_or_init(std::time::Instant::now).elapsed().as_nanos() as i64 }\n'
    with driver.open('x') as out: out.write(original[:start]+replacement+original[end:])
exe=R/(stem+('-profile.exe' if a.platform=='windows' else '-profile'))
assert not exe.exists()
cmd=['rustc','--edition=2021','--crate-name=fire_batch_jit_profile','--target='+target,'-C','opt-level=3','-C','lto=fat','-C','codegen-units=1']
if a.platform=='windows': cmd+=['-C','linker=x86_64-w64-mingw32-gcc']
for folder in ['target-deps','host-deps']: cmd+=['-L','dependency='+str(frozen/folder)]
for folder in folders: cmd+=['-L','native='+folder]
for name,lib in libraries.items(): cmd+=['--extern',name+'='+lib['frozen']]
cmd+=['--cfg','skip_logical_export','--cfg','cache_compact_export',str(driver),'-o',str(exe)]
write_new(R/(stem+'-link-command.json'),cmd)
manifest={**inputs,'libraries':libraries,'frozen_files':files,'artifacts_sha256':h(artifacts),
          'actual_driver_sha256':h(driver),'link_command':cmd,'scope':'Hidden fixed-work replay; no GPU submission or input/display latency.'}
write_new(R/(stem+'-frozen-manifest.json'),manifest)
with (R/(stem+'-link.log')).open('x') as log: subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
assert source(W)==inputs['systemless'] and source(C)==inputs['m68k']
manifest['exe_sha256']=h(exe)
write_new(manifest_path,manifest)
print(json.dumps({'manifest':str(manifest_path),'exe_sha256':h(exe)},indent=2),flush=True)
