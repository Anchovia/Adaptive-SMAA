"""Measure fresh Standard T2X-R CGVQM-2 and bridge pixel-identical source results.

The source score is explicitly reused only after all 480 current output frames
match the prior source capture and each selected-window input hash is rechecked.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from analyze_recovered_source_comparison import frames
from run_cgvqm_png_sequences import inspect_sequence

def main():
    p=argparse.ArgumentParser();p.add_argument('--comparison',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-source',type=Path,default=Path('tmp/source-comparison-cgvqm'));a=p.parse_args()
    data=json.loads(a.comparison.read_text());assert set(data['quality'])=={'bistro','minecraft'}
    root=Path(__file__).resolve().parents[2];a.output.mkdir(parents=True,exist_ok=True);jobs=[]
    for scene,q in data['quality'].items():
        assert not any(q['pixel_hash_mismatch'].values())
        reference=Path(q['reference'])/'SS_Reference'
        for window,start,count in [('central',150,180),('transition',410,30)]:
            indices=list(range(start,start+count))
            for mode,suffix in [('standard','O-T2X-R'),('integrated','source-1')]:
                run=q['runs'][f'{scene}-Quality-{suffix}'];paths=frames(run['report']);directory=paths[0].parent
                current=inspect_sequence(directory,paths[start:start+count],indices)
                refPaths=frames(reference);refInfo=inspect_sequence(reference,refPaths[start:start+count],indices)
                if mode=='integrated':
                    output=a.prior_source/scene/'profile-3'/window/'CGVQM-Results.json'
                    result=json.loads(output.read_text())
                    assert current.pixel_sha256==result['test_sequence']['pixel_sha256']
                    assert refInfo.pixel_sha256==result['reference_sequence']['pixel_sha256']
                    reuse=True
                else:
                    dest=a.output/scene/mode/window;dest.mkdir(parents=True,exist_ok=True)
                    args=[sys.executable,str(root/'Tools/SMAA/run_cgvqm_png_sequences.py'),'--test-dir',str(directory),
                          '--reference-dir',str(reference),'--output-dir',str(dest),'--start-index',str(start),'--frames',str(count),
                          '--model','2','--device','cuda','--classification','formal','--scene',scene,'--camera-profile','flythrough-wide-yaw-360',
                          '--test-mode','O-T2X-R','--patch-scale','4','--patch-pool','mean']
                    processes=subprocess.run(['tasklist','/FI','IMAGENAME eq CMAA2.exe','/FO','CSV','/NH'],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
                    assert b'cmaa2.exe' not in processes.stdout.lower()
                    print(f'CGVQM-2 fresh Standard: {scene} {window}',flush=True)
                    with (dest/'execution.log').open('w',encoding='utf-8') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800,cwd=root)
                    output=dest/'CGVQM-Results.json';result=json.loads(output.read_text());reuse=False
                assert result['classification']=='formal' and result['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
                expectedMode='O-T2X-R' if mode=='standard' else 'O-ET2X-R-SourceCandidate-SourceKernel'
                assert result['provenance']==dict(scene=scene,camera_profile='flythrough-wide-yaw-360',test_mode=expectedMode,reference_id='SS-Reference')
                assert result['runtime']['device']=='cuda' and result['runtime']['cuda_available']
                assert result['configuration']==dict(fps=60,patch_scale=4,patch_pool='mean',models=['2'],reference_index_offset=0)
                assert result['test_sequence']['pixel_sha256']==current.pixel_sha256
                assert result['reference_sequence']['pixel_sha256']==refInfo.pixel_sha256
                for side in ('test','reference'):
                    info=result[f'{side}_sequence'];trip=result[f'{side}_round_trip']
                    assert (info['frame_count'],info['first_index'],info['last_index'],info['width'],info['height'])==(count,start,start+count-1,1920,1017)
                    assert trip['decoded_frames']==count and trip['mismatched_values']==trip['max_absolute_difference']==0
                    assert trip['codec']=='ffv1' and trip['pixel_format']=='bgr0'
                jobs.append(dict(scene=scene,mode=mode,window=window,result=str(output),result_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                    reused_pixel_identical_source=reuse,current_capture=run,verified_current_pixel_sha256=current.pixel_sha256,reference_pixel_sha256=refInfo.pixel_sha256,
                    score=result['results']['CGVQM-2']['score_higher_is_better']))
                (a.output/'jobs.json').write_text(json.dumps(jobs,indent=2));print(f'PASS: {scene} {mode} {window}; reused={reuse}',flush=True)
if __name__=='__main__':main()
