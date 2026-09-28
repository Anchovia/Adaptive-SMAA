"""Actual unjittered SMAA 1X versus independently bridged original T2X-R."""
import argparse,hashlib,json,math,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Baseline-Restart';BENCH=ROOT/'Projects/CMAA2/AutoBench'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stream(folder,start,end):
    h=hashlib.sha256()
    for i in range(start,end):
        with Image.open(folder/f'frame_{i:05d}.png') as im:
            assert im.mode=='RGB' and im.size==(1920,1061)
            h.update(i.to_bytes(8,'little'));h.update(np.asarray(im).tobytes())
    return h.hexdigest()
def validate(d,start,end):
    assert d['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
    assert d['configuration']==dict(fps=60,patch_scale=4,patch_pool='mean',models=['2'],reference_index_offset=0)
    assert d['runtime']['device']=='cuda'
    for name in ['test','reference']:
        s=d[name+'_sequence'];r=d[name+'_round_trip']
        assert (s['first_index'],s['last_index'],s['frame_count'],s['width'],s['height'])==(start,end-1,end-start,1920,1061)
        assert r['decoded_frames']==end-start and r['mismatched_values']==r['max_absolute_difference']==0
    assert math.isfinite(d['results']['CGVQM-2']['score_higher_is_better'])
def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);scene=p.parse_args().scene
    qp=DOC/f'{scene}-capture.json';q=json.loads(qp.read_text());assert q['validation']=='PASS' and q['reference_reuse_allowed']
    cap=Path(q['capture']);ref=Path(q['reference']);results={}
    for window,(start,end) in dict(moving=(60,180),transition=(160,220)).items():
        nr=BENCH/'ContrastReferenceAnalysis'/scene/'CGVQM2'/window/'O-T2X-R/CGVQM-Results.json';native=json.loads(nr.read_text());validate(native,start,end)
        assert native['provenance']['scene']==scene and native['provenance']['test_mode']=='O-T2X-R'
        assert stream(cap/'O-T2X-R',start,end)==native['test_sequence']['pixel_sha256']
        reference_hash=stream(ref,start,end);assert reference_hash==native['reference_sequence']['pixel_sha256']
        out=BENCH/'BaselineRestart'/scene/'CGVQM2'/window/'O-1X';out.mkdir(parents=True,exist_ok=True);rp=out/'CGVQM-Results.json'
        if not rp.exists():
            print(f'START {scene}/{window} actual O-1X',flush=True)
            args=[sys.executable,str(ROOT/'Tools/SMAA/run_cgvqm_png_sequences.py'),'--test-dir',str(cap/'O-1X'),'--reference-dir',str(ref),'--output-dir',str(out),'--start-index',str(start),'--frames',str(end-start),'--cgvqm-root',str(ROOT.parents[2]/'.research-tools/CGVQM'),'--model','2','--classification','engineering','--scene',scene,'--camera-profile','original-flythrough-t2-still60-move120-still60','--test-mode','O-1X','--reference-id','SS-Reference','--device','cuda','--patch-scale','4','--patch-pool','mean','--skip-error-map-video']
            with (out/'runner.log').open('w',encoding='utf-8') as log:subprocess.run(args,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        new=json.loads(rp.read_text());validate(new,start,end)
        assert new['test_sequence']['pixel_sha256']==stream(cap/'O-1X',start,end) and new['reference_sequence']['pixel_sha256']==reference_hash
        assert new['provenance']['test_mode']=='O-1X' and new['provenance']['scene']==scene
        for k in ['torch','cuda_runtime','device']:assert new['runtime'][k]==native['runtime'][k]
        n=native['results']['CGVQM-2']['score_higher_is_better'];x=new['results']['CGVQM-2']['score_higher_is_better']
        results[window]=dict(smaa_1x_score=x,t2x_r_score=n,t2x_r_minus_1x=n-x,one_x_record=new,native_record=native,one_x_result_sha256=sha(rp),native_result_sha256=sha(nr))
        print(f'PASS {scene}/{window}: SMAA 1X={x:.6f}, T2X-R={n:.6f}',flush=True)
    (DOC/f'{scene}-cgvqm.json').write_text(json.dumps(dict(scene=scene,validation='PASS',capture_report_sha256=sha(qp),results=results),indent=2)+'\n')
if __name__=='__main__':main()
