"""Require a completed isolated capture, repeat/seed/control checks, static gate."""
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[2]
records=json.loads((root/'tmp/temporal-paired-dejitter-runs.json').read_text(encoding='utf-8-sig'))
r=next(r for r in records if r['scene']==a.scene and r['phase']=='StaticCapture')
report=Path(r['report']);text=report.read_text(encoding='utf-8-sig');capture=report.parent
assert hashlib.sha256(report.read_bytes()).hexdigest()==r['report_sha256'].lower()
assert 'Aggregate: PASS' in text and 'Aggregate: FAIL' not in text
assert 'Frames: 40' in text and 'Warmup: 60' in text and '1920 x 1061' in text
N='O-T2X-R';H='ABL-HistoryLinear-R';C='ABL-CurrentDeJitter-R';P='ABL-PairedDeJitter-R';D='DBG-DeJitterSpatial-R'
names=(N,H,C,P,P+'-Repeat',D)
checks=[[s.strip() for s in r] for r in csv.reader(text.splitlines()) if r and r[0].strip()=='pattern_check']
assert len(checks)==240 and all(r[3:5]==['On','PASS'] for r in checks)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rgb=lambda p:np.asarray(Image.open(p).convert('RGB'))
prior=root/'Projects/CMAA2/AutoBench'/('20260921_155746' if a.scene=='bistro' else '20260921_155323')
hp=root/'Projects/CMAA2/AutoBench'/('20260921_152300' if a.scene=='bistro' else '20260921_151748')
out={};bridges=0
for m in names:
 files=sorted((capture/m).glob('*.png'));assert [f.name for f in files]==[f'frame_{i:05d}.png' for i in range(40)]
 if m in (N,C,D,H):
  for f in files:assert sha(f)==sha((hp if m==H else prior)/m/f.name);bridges+=1
 ims=[rgb(f) for f in files[20:40]]
 steps=[np.abs(x.astype(np.int16)-y.astype(np.int16)) for x,y in zip(ims,ims[1:])]
 out[m]=dict(mean_rgb_step=float(np.mean([d.mean() for d in steps])),max_rgb_step=max(int(d.max()) for d in steps),
  unique_rgb_frames=len({hashlib.sha256(im.tobytes()).hexdigest() for im in ims}),
  lag2_mismatches=sum(not np.array_equal(x,y) for x,y in zip(ims,ims[2:])))
for i in range(40):
 f=f'frame_{i:05d}.png';assert sha(capture/P/f)==sha(capture/(P+'-Repeat')/f)
assert sha(capture/P/'frame_00000.png')==sha(capture/D/'frame_00000.png')
assert out[N]['unique_rgb_frames']==1
ok=out[P]['mean_rgb_step']<=.001 and out[P]['max_rgb_step']<=1 and out[P]['lag2_mismatches']==0
result=dict(scene=a.scene,receipt=r,static_gate='PASS' if ok else 'FAIL',control_hash_comparisons=bridges,
 repeat_hash_comparisons=40,first_seed_match=True,pattern_checks=240,late_still=out)
(root/f'Docs/Temporal-Paired-DeJitter/{a.scene}-static.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));assert ok,'Full-screen static gate failed; do not proceed to selection'
