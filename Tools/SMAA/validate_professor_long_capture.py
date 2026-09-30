import sys,json,csv,hashlib,subprocess
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
case,scene=sys.argv[1:]
receipt=json.loads((ROOT/f'tmp/professor-case{case}-{scene}-receipt.json').read_text(encoding='utf-8-sig'))
report=Path(receipt['report']);assert hashlib.sha256(report.read_bytes()).hexdigest()==receipt['report_sha256'].lower()
rows=[[x.strip() for x in r] for r in csv.reader(report.read_text(encoding='utf-8-sig').splitlines())]
for row in rows:
 while row and row[-1]=='':row.pop()
cap=Path(next(r[1] for r in rows if r and r[0]=='capture_root'))
assert next(r[1:] for r in rows if r and r[0]=='presentation_timeline')==['480','60','360','60','60fps']
checks=[r for r in rows if r and r[0]=='mode_check']
modes=list(dict.fromkeys(r[1] for r in checks))
if case=='audit':
 old=json.loads((ROOT/f'Docs/Edge-Persistence-Cost-Audit/{scene}-capture.json').read_text())['output_hashes']
 assert set(modes)=={'A-CurrentEdge-Stencil','B-PreviousRawEdge-Depth','E-PreviousRawEdge-FirstStencil','O-T2X-R'}
else:
 old=json.loads((ROOT/f'Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json').read_text())
 assert len(modes)==2
hashes={}
for mode in modes:
 group=[r for r in checks if r[1]==mode]
 assert [int(r[2]) for r in group]==list(range(480)) and all(r[-1]=='PASS' for r in group)
 files=sorted((cap/mode).glob('frame_[0-9][0-9][0-9][0-9][0-9].png'))
 assert len(files)==480
 hashes[mode]=[]
 for i,p in enumerate(files):
  assert p.name==f'frame_{i:05d}.png'
  with Image.open(p) as im:
   assert im.size==(1920,1061)
   hashes[mode].append(hashlib.sha256(im.convert('RGB').tobytes()).hexdigest())
 assert hashes[mode][:180]==old[mode][:180],(case,scene,mode,'prefix mismatch')
if case=='audit':
 assert hashes['B-PreviousRawEdge-Depth']==hashes['E-PreviousRawEdge-FirstStencil']
else:
 control=json.loads((ROOT/f'tmp/professor-caseaudit-{scene}-validated.json').read_text())
 assert hashes['O-T2X-R']==control['rgb_hashes']['O-T2X-R'],(case,scene,'native control mismatch')
result=dict(validation='PASS',case=case,scene=scene,receipt=receipt,capture_root=str(cap),modes=modes,
 frames=480,prefix_matching_frames_per_mode=180,native_control_all_frames_equal=True,
 late_still_unique_rgb={m:len(set(h[440:480])) for m,h in hashes.items()},rgb_hashes=hashes,
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip())
(ROOT/f'tmp/professor-case{case}-{scene}-validated.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS verified 480-frame capture, original prefix and native control:',case,scene,flush=True)
