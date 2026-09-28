"""CGVQM-2: exact unchanged native baseline reuse, new selective runs."""
import argparse,hashlib,json,math,subprocess,sys
from pathlib import Path
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Temporal-First-Edge-Quality';BENCH=ROOT/'Projects/CMAA2/AutoBench';NATIVE='O-T2X-R';SELECT='ABL-FirstEdge-Reuse-R'
WINDOWS={'moving':(60,180),'transition':(160,220)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sequence_hash(folder,start,end):
 h=hashlib.sha256()
 for i in range(start,end):
  with Image.open(folder/f'frame_{i:05d}.png') as im:
   assert im.size==(1920,1061) and im.mode=='RGB';a=np.asarray(im)
  h.update(i.to_bytes(8,'little'));h.update(a.tobytes())
 return h.hexdigest()
def validate(d,start,end):
 assert d['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
 assert d['configuration']==dict(fps=60,patch_scale=4,patch_pool='mean',models=['2'],reference_index_offset=0)
 assert d['runtime']['device']=='cuda'
 for pre in ['test','reference']:
  seq=d[pre+'_sequence'];rt=d[pre+'_round_trip']
  assert (seq['first_index'],seq['last_index'],seq['frame_count'],seq['width'],seq['height'])==(start,end-1,end-start,1920,1061)
  assert rt['decoded_frames']==end-start and rt['mismatched_values']==rt['max_absolute_difference']==0
 assert math.isfinite(d['results']['CGVQM-2']['score_higher_is_better'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--scene',required=True,choices=['bistro','minecraft']);a=p.parse_args()
 qp=DOC/f'{a.scene}-quality.json';q=json.loads(qp.read_text());assert q['validation']=='PASS' and q['selection_mismatches']==0
 cap=Path(q['capture']);ref=Path(q['reference']);results={}
 for window,(start,end) in WINDOWS.items():
  prior=BENCH/'ContrastReferenceAnalysis'/a.scene/'CGVQM2'/window/NATIVE/'CGVQM-Results.json';native=json.loads(prior.read_text());validate(native,start,end)
  assert native['provenance']['scene']==a.scene and native['provenance']['test_mode']==NATIVE
  assert sequence_hash(cap/NATIVE,start,end)==native['test_sequence']['pixel_sha256'],'native pixel hash changed'
  assert sequence_hash(ref,start,end)==native['reference_sequence']['pixel_sha256'],'reference hash changed'
  out=BENCH/'FirstEdgeQuality'/a.scene/'CGVQM2'/window/SELECT;out.mkdir(parents=True,exist_ok=True);rp=out/'CGVQM-Results.json'
  if not rp.exists():
   cmd=[sys.executable,str(ROOT/'Tools/SMAA/run_cgvqm_png_sequences.py'),'--test-dir',str(cap/SELECT),'--reference-dir',str(ref),'--output-dir',str(out),'--start-index',str(start),'--frames',str(end-start),'--cgvqm-root',str(ROOT.parents[2]/'.research-tools/CGVQM'),'--model','2','--classification','engineering','--scene',a.scene,'--camera-profile','original-flythrough-t2-still60-move120-still60','--test-mode',SELECT,'--reference-id','SS-Reference','--device','cuda','--patch-scale','4','--patch-pool','mean','--skip-error-map-video']
   print(f'START {a.scene}/{window}',flush=True)
   with (out/'runner.log').open('w',encoding='utf-8') as f:subprocess.run(cmd,check=True,timeout=600,stdout=f,stderr=subprocess.STDOUT)
  new=json.loads(rp.read_text());validate(new,start,end)
  assert Path(new['test_sequence']['directory']).resolve()==(cap/SELECT).resolve()
  assert new['provenance']['test_mode']==SELECT and new['reference_sequence']['pixel_sha256']==native['reference_sequence']['pixel_sha256']
  for key in ['torch','cuda_runtime','device']:assert new['runtime'][key]==native['runtime'][key],key
  assert sequence_hash(cap/SELECT,start,end)==new['test_sequence']['pixel_sha256']
  n=native['results']['CGVQM-2']['score_higher_is_better'];v=new['results']['CGVQM-2']['score_higher_is_better']
  results[window]=dict(native_score=n,selective_score=v,selective_minus_native=v-n,native_reused_after_exact_pixel_bridge=True,native_result=str(prior),native_result_sha256=sha(prior),selective_result=str(rp),selective_result_sha256=sha(rp),reference_pixel_sha256=new['reference_sequence']['pixel_sha256'],native_record=native,selective_record=new)
  print(f'PASS {a.scene}/{window}: native={n:.6f}, selective={v:.6f}, delta={v-n:+.6f}',flush=True)
 (DOC/f'{a.scene}-cgvqm.json').write_text(json.dumps(dict(scene=a.scene,quality_report_sha256=sha(qp),validation='PASS',results=results),indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
