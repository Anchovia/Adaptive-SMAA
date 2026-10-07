"""Validate completed receipts and preserve small derived evidence in Docs."""
import csv,hashlib,json,shutil
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
RECORD=ROOT/'tmp/all-case-remeasurement'
OUT=ROOT/'Deliverables/SMAA_All_17_Remeasurement_20261007'
DOC=ROOT/'Docs/All-Case-Remeasurement'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 plan=load(RECORD/'manifest.json');runs=load(RECORD/'runs.json')
 assert load(RECORD/'status.json')['status']=='PASS'
 expected={(c,s,p) for c in range(1,18) for s in ('bistro','minecraft') for p in ('Smoke','Benchmark','Capture')}
 assert len(runs)==102 and {(r['case'],r['scene'],r['phase']) for r in runs}==expected
 for item in plan['cases']:
  source=Path(item['source']);binary=digest(source/'Projects/CMAA2/CMAA2.exe')
  for name,value in item['production_sha256'].items():assert digest(source/name).lower()==value.lower(),name
  for r in runs:
   if r['case']!=item['case']:continue
   assert digest(r['report']).lower()==r['report_sha256'].lower()
   assert binary.lower()==r['executable_sha256'].lower()
   assert 'Aggregate: PASS' in Path(r['report']).read_text(encoding='utf-8-sig')
 hashes=load(OUT/'output-pixel-hashes.json');assert len(hashes)==17*2*240
 inspection=load(OUT/'visual-inspection.json');assert inspection['completed'] is True
 reviewed=[]
 for p in sorted((OUT/'inspection').glob('*.png')):
  reviewed.append(dict(path=str(p),sha256=digest(p)))
 assert len(reviewed)==34
 media=[]
 for s,rois in [('bistro',('thin-chair','windows')),('minecraft',('thin-seam','leaves','grass-seam'))]:
  for c in range(1,18):
   if c==4:continue
   for roi in rois:
    p=OUT/'frames'/f'{s}-{roi}-4-vs-{c}.gif'
    with Image.open(p) as im:
     assert im.n_frames==150,(p,im.n_frames)
     duration=0
     for f in range(im.n_frames):im.seek(f);duration+=im.info['duration']
     assert duration==5000,(p,duration)
    assert (p.with_suffix('.png')).is_file()
    media.append(dict(path=str(p),frames=150,duration_ms=duration,playback_speed=0.5))
   for f in (130,181,230):assert (OUT/'frames'/f'{s}-full-f{f}-4-vs-{c}.png').is_file()
 assert len(media)==80
 with (OUT/'quality-per-frame.csv').open(encoding='utf-8-sig',newline='') as f:
  frame_rows=list(csv.DictReader(f))
 assert len(frame_rows)==17*2*240
 assert {(r['scene'],int(r['case']),int(r['frame'])) for r in frame_rows}=={(s,c,f) for s in ('bistro','minecraft') for c in range(1,18) for f in range(240)}
 previous=ROOT/'Deliverables/SMAA_15_16_17_20261007/Evidence/case17'
 bridge=[]
 for s in ('bistro','minecraft'):
  old=load(previous/f'{s}-capture.json')['rgb_hashes']['O-T2X-R']
  assert len(old)==240
  mismatch=[f for f in range(240) if hashes[f'{s}/4/{f}']!=old[f]]
  assert not mismatch,(s,mismatch)
  bridge.append(dict(scene=s,old_control=str(previous/f'{s}-capture.json'),frames=240,mismatch_count=0))
 equivalence=[]
 for s in ('bistro','minecraft'):
  for a,b in ((7,8),(8,9),(14,15),(14,16),(14,17)):
   mismatch=[f for f in range(240) if hashes[f'{s}/{a}/{f}']!=hashes[f'{s}/{b}/{f}']]
   equivalence.append(dict(scene=s,case_a=a,case_b=b,frames=240,rgb_hash_mismatch_count=len(mismatch),mismatch_frames=mismatch))
 audit=dict(validation='PASS',completed_commands=102,performance_sequences=34,capture_sequences=34,
  frames_per_capture=240,production_and_binary_hashes_unchanged=True,
  previous_native_baseline_bridge=bridge,case_equivalence=equivalence,
  native_controls=load(OUT/'native-baseline-bridge.json'),visual_inspection=inspection)
 audit['reviewed_lossless_sheets']=reviewed;audit['gif_media_validation']=media
 audit['settling_exception']=load(OUT/'settling-exception.json')
 save(OUT/'completion-audit.json',audit)
 protocol=load(DOC/'protocol.json');protocol['state']='Complete: fresh paired speed, fresh RGB quality and direct original-frame inspection'
 protocol['completion_audit']='completion-audit.json';save(DOC/'protocol.json',protocol)
 for name in ('performance.json','quality.json','native-baseline-bridge.json','visual-inspection.json','settling-exception.json','completion-audit.json','capture-reports.json','comparison.md'):
  shutil.copy2(OUT/name,DOC/name)
 save(DOC/'run-provenance.json',runs)
 print('PASS: all 102 commands, production/binary/report hashes, baseline bridges and direct inspection')

if __name__=='__main__':main()
