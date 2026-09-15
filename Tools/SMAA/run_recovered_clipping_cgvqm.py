"""CGVQM-2 clipping factorial; input hashes guard reuse and resumed jobs."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
from analyze_recovered_clipping import ROOT, BENCH, HISTORIC, NAMES, manifest, sequence
from run_cgvqm_png_sequences import inspect_sequence

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=ROOT/'tmp/recovered-clipping/runs.json')
    p.add_argument('--output',type=Path,default=ROOT/'tmp/recovered-clipping/cgvqm');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for scene in HISTORIC:
        runs=manifest(a.manifest,'Quality',scene)
        reference=BENCH/HISTORIC[scene][1]/'SS_Reference';refs=sequence(reference,480)
        for window,start,count in [('central',150,180),('transition',410,30)]:
            indices=list(range(start,start+count));refinfo=inspect_sequence(reference,refs[start:start+count],indices)
            for name in NAMES:
                run=runs[name];paths=sequence(run['report'],480);directory=paths[0].parent
                testinfo=inspect_sequence(directory,paths[start:start+count],indices)
                reused=name=='SourceClip';dest=a.output/scene/name/window
                output=(ROOT/'tmp/source-comparison-cgvqm'/scene/'profile-3'/window/'CGVQM-Results.json') if reused else dest/'CGVQM-Results.json'
                fresh=False
                if not output.exists():
                    assert not reused,'Missing historic baseline result'
                    processes=subprocess.run(['tasklist','/FI','IMAGENAME eq CMAA2.exe','/FO','CSV','/NH'],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
                    assert b'cmaa2.exe' not in processes.stdout.lower(),'Concurrent demo process'
                    dest.mkdir(parents=True,exist_ok=True)
                    args=[sys.executable,str(ROOT/'Tools/SMAA/run_cgvqm_png_sequences.py'),'--test-dir',str(directory),'--reference-dir',str(reference),
                        '--output-dir',str(dest),'--start-index',str(start),'--frames',str(count),'--model','2','--device','cuda',
                        '--classification','formal','--scene',scene,'--camera-profile','flythrough-wide-yaw-360','--test-mode',run['semantic_id'],
                        '--patch-scale','4','--patch-pool','mean']
                    print(f'Starting CGVQM-2 {scene} {window} {name}',flush=True)
                    with (dest/'execution.log').open('w',encoding='utf-8') as log:
                        subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800,cwd=ROOT)
                    fresh=True
                result=json.loads(output.read_text());expected='O-ET2X-R-SourceCandidate-SourceKernel' if reused else run['semantic_id']
                assert result['classification']=='formal'
                assert result['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
                assert result['provenance']==dict(scene=scene,camera_profile='flythrough-wide-yaw-360',test_mode=expected,reference_id='SS-Reference')
                assert result['runtime']['device']=='cuda' and result['runtime']['cuda_available']
                assert result['configuration']==dict(fps=60,patch_scale=4,patch_pool='mean',models=['2'],reference_index_offset=0)
                assert result['test_sequence']['pixel_sha256']==testinfo.pixel_sha256
                assert result['reference_sequence']['pixel_sha256']==refinfo.pixel_sha256
                for side in ('test','reference'):
                    info=result[side+'_sequence'];trip=result[side+'_round_trip']
                    assert (info['frame_count'],info['first_index'],info['last_index'],info['width'],info['height'])==(count,start,start+count-1,1920,1017)
                    assert trip['decoded_frames']==count and trip['mismatched_values']==trip['max_absolute_difference']==0
                    assert trip['codec']=='ffv1' and trip['pixel_format']=='bgr0'
                jobs.append(dict(scene=scene,window=window,variant=name,result=str(output),result_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                    reused_historical_baseline=reused,newly_computed_this_invocation=fresh,test_pixel_sha256=testinfo.pixel_sha256,
                    reference_pixel_sha256=refinfo.pixel_sha256,score=result['results']['CGVQM-2']['score_higher_is_better']))
                (a.output/'jobs.json').write_text(json.dumps(jobs,indent=2))
                print(f'PASS {scene} {window} {name}: {jobs[-1]["score"]:.6f}',flush=True)
    assert len(jobs)==16
if __name__=='__main__':main()
