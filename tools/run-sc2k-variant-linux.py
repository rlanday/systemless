"""Private fixed-work Linux replay; Linux counters are not Windows commit sizes."""
import argparse,hashlib,json,os,resource,shutil,subprocess,tempfile,time
from pathlib import Path
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('mode',choices=['off','public']);p.add_argument('label');p.add_argument('--diagnostics',action='store_true');a=p.parse_args()
assert a.label.isalnum()
out=R/f'opus-follow-linux-{a.mode}-{a.label}';out.mkdir()
manifest=R/'opus-follow-linux-manifest.json';m=json.loads(manifest.read_text());exe=R/'opus-follow-linux-profile'
h=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert h(exe)==m['exe_sha256']
shutil.copyfile(manifest,out/'build-manifest.json');shutil.copyfile(__file__,out/'runner.py')
env={k:v for k,v in os.environ.items() if not k.startswith(('SYSTEMLESS_','M68K_','TRACE_COPYBITS')) and k!='PROFILE_FIRE'}
env.update(M68K_NATIVE_REGIONS=a.mode,PROFILE_FIRE='1')
if a.diagnostics:env['M68K_NATIVE_REGION_DIAGNOSTICS']='1'
with tempfile.TemporaryDirectory(prefix='systemless-defaulton-') as directory:
    local=Path(directory);game=local/'sc2k-expanded-test.kpak';shutil.copyfile(R/game.name,game)
    before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
    samples=[]
    with (local/'stdout.log').open('wb') as stdout,(local/'stderr.log').open('wb') as stderr:
        child=subprocess.Popen([str(exe),str(game),str(local)],cwd=local,env=env,stdout=stdout,stderr=stderr)
        while child.poll() is None:
            if time.monotonic()-start>180:
                child.kill();child.wait();raise TimeoutError('Owned Linux replay exceeded 180 seconds')
            try:
                status=(Path('/proc')/str(child.pid)/'status').read_text().splitlines()
                values={line.split(':')[0]:int(line.split()[1])*1024 for line in status if line.startswith(('VmRSS:','VmHWM:','VmData:','VmSwap:','VmPeak:'))}
                samples.append({'elapsed':time.monotonic()-start,**values})
            except (FileNotFoundError,ProcessLookupError):pass
            time.sleep(.01)
    wall=time.monotonic()-start;after=resource.getrusage(resource.RUSAGE_CHILDREN)
    assert child.returncode==0
    ram=[]
    for frame in [999,1499,1999,2499]:
        f=local/f'frame-{frame}.ram';assert f.stat().st_size==134217728
        ram.append({'name':f.name,'bytes':f.stat().st_size,'sha256':h(f)})
    (out/'ram-sha256.json').write_text(json.dumps(ram,indent=2))
    for f in local.iterdir():
        if f.is_file() and f.suffix not in {'.kpak','.ram'}:shutil.copyfile(f,out/f.name)
    (out/'memory.json').write_text(json.dumps(samples))
    (out/'process-times.json').write_text(json.dumps({'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
        'wall_seconds':wall,'mode':a.mode,'diagnostics':a.diagnostics,'exit_code':child.returncode,
        'peak_rss_bytes':after.ru_maxrss*1024,'scope':'Linux WSL hidden fixed-work replay; all child threads CPU, no GUI/GPU, Linux RSS is not Windows commit'},indent=2))
print(out.name,'finished',flush=True)
