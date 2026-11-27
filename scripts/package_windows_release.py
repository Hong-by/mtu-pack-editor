from pathlib import Path
import argparse
import zipfile
import hashlib
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tk_pack_builder import __version__
parser = argparse.ArgumentParser(description='Package and verify Windows release archives.')
parser.add_argument('--app-dir', type=Path, default=ROOT / 'dist/MTU Pack Editor')
parser.add_argument('--output-dir', type=Path, default=ROOT / 'release-assets')
args = parser.parse_args()
root=args.app_dir.resolve()
if not (root / 'MTU Pack Editor.exe').is_file():
    raise SystemExit('Build the Windows executable first.')
out=args.output_dir.resolve();out.mkdir(parents=True, exist_ok=True)
files=sorted(p for p in root.rglob('*') if p.is_file())
# Exclude only runtime traces produced by the smoke launch.
files=[p for p in files if p.suffix not in {'.log','.sqlite3'} and not p.name.endswith(('.sqlite3-shm','.sqlite3-wal'))]
main=[];parts=[];current=[];size=0
for p in files:
    rel=p.relative_to(root).as_posix()
    if rel.startswith('work/assets/profile_190/'):
        n=p.stat().st_size
        if current and size+n>1400*1024*1024:
            parts.append(current);current=[];size=0
        current.append(p);size+=n
    else: main.append(p)
if current: parts.append(current)
plan=[('windows',main)]+[(f'data-{i}',part) for i,part in enumerate(parts,1)]
checks=[];total=0
for label,group in plan:
    target=out/f'MTU-Pack-Editor-v{__version__}-{label}.zip'
    print('Creating',target,len(group),'files',flush=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in group:z.write(p, 'MTU Pack Editor/'+p.relative_to(root).as_posix())
    assert target.stat().st_size<2*1024**3, str(target)+' exceeds release asset limit'
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        total+=len(z.namelist())
    digest=hashlib.file_digest(target.open('rb'),'sha256').hexdigest()
    checks.append(f'{digest}  {target.name}')
    print('Verified',target.name,target.stat().st_size,flush=True)
assert total==len(files)
(out/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='utf-8')
print('COMPLETE',len(files),'files',len(plan),'archives',flush=True)
