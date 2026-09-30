"""Per-branch provenance, full-frame RGB regression and paired timing gate."""
import argparse,csv,hashlib,json,statistics,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Stencil-Lifecycle-Refresh'
CFG=json.loads((DOC/'case.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,data):
 (DOC/name).write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def audit():
 assert git('branch','--show-current').decode().strip()==CFG['branch']
 shader=[]
 for name in git('ls-tree','-r','--name-only',CFG['base'],'Projects/CMAA2/SMAA').decode().splitlines():
  if not name.endswith(('.hlsl','.fx','.h')) or name.endswith(('SMAA.h','vaSMAAWrapper.h')):continue
  original=git('show',CFG['base']+':'+name).replace(b'\r\n',b'\n');local=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
  assert local==original,name
  shader.append(dict(path=name,normalized_sha256=hashlib.sha256(local).hexdigest()))
 core=(ROOT/'Projects/CMAA2/SMAA/SMAA.cpp').read_text()
 go=core.split('void SMAA::go(',1)[1].split('\nvoid SMAA::',1)[0]
 assert go.count('ClearDepthStencilView')==1
 assert 'if(dsv) context->ClearDepthStencilView(dsv, D3D11_CLEAR_STENCIL, 1.0f, 0);' in go
 if CFG['case']==5:assert core.count('ClearDepthStencilView')==2 and 'if(exactStencil) context->ClearDepthStencilView' in core
 else:assert core.count('ClearDepthStencilView')==1
 wrapper=(ROOT/'Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp').read_text()
 assert wrapper.count('"SR_CameraVelocity"')==1 and wrapper.count('"SR_Resolve"')==1
 changed=git('diff','--name-only',CFG['base'],'--','Projects','Tools/SMAA').decode().splitlines()
 expected={'Projects/CMAA2/CMAA2Sample.cpp','Projects/CMAA2/SMAA/SMAA.cpp','Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp','Projects/CMAA2/StencilLifecycleVerification.inl','Tools/SMAA/run_stencil_lifecycle.ps1','Tools/SMAA/analyze_stencil_lifecycle.py'}
 assert set(changed).issubset(expected),changed
 write('source-audit.json',dict(validation='PASS',config=CFG,unchanged_shaders=shader,executable_sha256=sha(ROOT/'Projects/CMAA2/CMAA2.exe'),sources={p:sha(ROOT/p) for p in sorted(expected)},spatial_go_clear_calls=1,raw_exact_edge_clear_preserved=CFG['case']==5))
 print('PASS source audit',CFG['case'],len(shader),'unchanged shader/support files',flush=True)
def read(scene,phase):
 receipts=json.loads((ROOT/f'tmp/stencil-lifecycle-case{CFG["case"]}-runs.json').read_text(encoding='utf-8-sig'))
 rec=[r for r in receipts if r['scene']==scene and r['phase']==phase];assert len(rec)==1
 r=rec[0];p=Path(r['report']);assert sha(p)==r['report_sha256'].lower()
 text=p.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'Aggregate: FAIL' not in text
 a=json.loads((DOC/'source-audit.json').read_text());assert a['executable_sha256']==r['executable_sha256'].lower()
 return r,[[c.strip() for c in row] for row in csv.reader(text.splitlines())]
def rgb(p):
 with Image.open(p) as im:
  assert im.size==(1920,1061) and im.mode=='RGB',(p,im.size,im.mode)
  return np.array(im)
def capture(scene):
 r,rows=read(scene,'Capture');captureRoot=Path(next(row[1] for row in rows if row and row[0]=='capture_root'))
 target=CFG['target'];modes=[target]+(['O-T2X-R'] if CFG['case']!=4 else [])+[target+'-Repeat']
 checks=[row for row in rows if row and row[0]=='mode_check'];assert len(checks)==240*len(modes)
 prior=json.loads((DOC/f'{scene}-prior.json').read_text())
 hashes={m:[] for m in modes};bad={m:[] for m in modes};maximum={m:0 for m in modes}
 for m in modes:
  seq=[row for row in checks if row[1]==m];assert [int(row[2]) for row in seq]==list(range(240)) and all(row[4]=='PASS' for row in seq)
  files=sorted((captureRoot/m).glob('frame_*.png'));assert [p.name for p in files]==[f'frame_{i:05d}.png' for i in range(240)]
  if m.endswith('-Repeat'):other=captureRoot/target
  elif m==target:other=Path(prior['target_capture'])
  else:other=Path(prior['control_capture'])
  for i,p in enumerate(files):
   arr=rgb(p);old=rgb(other/p.name);diff=np.abs(arr.astype(np.int16)-old.astype(np.int16))
   err=int(diff.max());maximum[m]=max(maximum[m],err)
   if err:bad[m].append(i)
   hashes[m].append(hashlib.sha256(arr.tobytes()).hexdigest())
  print(scene,m,'mismatch',len(bad[m]),flush=True)
 static={m:len(set(hashes[m][200:240])) for m in modes}
 result=dict(validation='PASS' if not any(bad.values()) and all(x==1 for x in static.values()) else 'FAIL',executable_sha256=r['executable_sha256'].lower(),scene=scene,case=CFG['case'],receipt=r,capture=str(captureRoot),frames_per_mode=240,mismatched_frames=bad,max_rgb_error=maximum,late_still_unique_rgb=static,quality_reuse_allowed=not any(bad.values()),quality_interpretation='Full 240-frame RGB bridge to preserved quality inputs; old scores reused only when PASS, no model rerun or new quality improvement claim',prior_metadata_sha256=sha(DOC/f'{scene}-prior.json'))
 write(f'{scene}-capture.json',result);write(f'{scene}-rgb-hashes.json',hashes)
 assert result['validation']=='PASS',result
def performance(scene,phase):
 r,rows=read(scene,phase);repeats=1 if phase=='Smoke' else 6;samples=240 if phase=='Smoke' else 4800
 target=CFG['target'];names=[target]+(['O-T2X-R'] if CFG['case']!=4 else [])
 data={};timing=[row for row in rows if row and row[0]=='timing'];expected=0
 for m in names:
  metrics=['SMAA','WholeFrame','WallFrame']+(['SR_CameraVelocity','SR_Resolve'] if m=='O-T2X-R' or CFG['temporal'] else [])
  data[m]={};expected+=len(metrics)*repeats
  for metric in metrics:
   group=sorted([row for row in timing if row[1]==m and row[3]==metric],key=lambda row:int(row[2]))
   assert [int(row[2]) for row in group]==list(range(repeats)) and all(int(row[4])==samples for row in group)
   means=[float(row[5]) for row in group];assert all(x>=0 for x in means)
   data[m][metric]=dict(mean_ms=statistics.mean(means),run_mean_std_ms=statistics.stdev(means) if repeats>1 else None,run_means_ms=means,mean_run_median_ms=statistics.mean(float(row[6]) for row in group),mean_run_p95_ms=statistics.mean(float(row[7]) for row in group),mean_run_p99_ms=statistics.mean(float(row[8]) for row in group),mean_frame_stddev_ms=statistics.mean(float(row[9]) for row in group),mean_slowest_one_percent_equivalent_fps=statistics.mean(float(row[10]) for row in group))
 assert len(timing)==expected
 contrasts={}
 for metric in data[target]:
  a=data['O-T2X-R'][metric];b=data[target][metric]
  assert a['mean_ms']>0
  contrasts[metric]=dict(change_percent=(b['mean_ms']/a['mean_ms']-1)*100,difference_ms=b['mean_ms']-a['mean_ms'],paired_run_change_percent=[(y/x-1)*100 for x,y in zip(a['run_means_ms'],b['run_means_ms'])])
 result=dict(validation='PASS',executable_sha256=r['executable_sha256'].lower(),receipt=r,scene=scene,case=CFG['case'],config=CFG,frames_per_mode_run=samples,repeats=repeats,modes=data,relative_to_corrected_t2x_r=contrasts,classification='Within-executable paired GPU comparison; native On vs selective Off where applicable, not isolated selection effect. AA-Off AA=0 by definition. WholeFrame GPU and CPU wall distinct.')
 write(f'{scene}-{phase.lower()}.json',result)
 print(json.dumps(dict(case=CFG['case'],scene=scene,phase=phase,contrasts=contrasts)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['audit','Capture','Smoke','Benchmark']);p.add_argument('--scene',choices=['bistro','minecraft']);a=p.parse_args()
 if a.phase=='audit':audit()
 elif a.phase=='Capture':capture(a.scene)
 else:performance(a.scene,a.phase)
