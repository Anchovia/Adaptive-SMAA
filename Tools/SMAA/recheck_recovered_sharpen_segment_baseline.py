"""Fresh CGVQM baseline replication after an unreproduced frame-hash check failure."""
import hashlib, json, subprocess, sys
from pathlib import Path
from analyze_recovered_sharpen_segment import ROOT, BENCH, HISTORIC, NAMES, manifest, sequence
from run_cgvqm_png_sequences import inspect_sequence
from summarize_recovered_clipping_cgvqm import load_result

def main():
    root=ROOT/'tmp/recovered-sharpen-segment/cgvqm'
    jobs=json.loads((root/'jobs.json').read_text());assert len(jobs)==16
    run=manifest(ROOT/'tmp/recovered-sharpen-segment/runs.json','Quality','minecraft')[NAMES[0]]
    paths=sequence(run['report'],480);directory=paths[0].parent
    reference=BENCH/HISTORIC['minecraft'][1]/'SS_Reference'
    refs=sequence(reference,480);indices=list(range(410,440))
    test=inspect_sequence(directory,paths[410:440],indices)
    ref=inspect_sequence(reference,refs[410:440],indices)
    old=next(r for r in jobs if (r['scene'],r['window'],r['variant'])==('minecraft','transition',NAMES[0]))
    assert old['test_pixel_sha256']==test.pixel_sha256 and old['reference_pixel_sha256']==ref.pixel_sha256
    dest=root/'minecraft'/NAMES[0]/'transition';dest.mkdir(parents=True,exist_ok=True)
    target=dest/'CGVQM-Results.json'
    fresh=not target.exists()
    if fresh:
        process=subprocess.run(['tasklist','/FI','IMAGENAME eq CMAA2.exe','/FO','CSV','/NH'],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        assert b'cmaa2.exe' not in process.stdout.lower()
        command=[sys.executable,str(ROOT/'Tools/SMAA/run_cgvqm_png_sequences.py'),'--test-dir',str(directory),
            '--reference-dir',str(reference),'--output-dir',str(dest),'--start-index','410','--frames','30',
            '--model','2','--device','cuda','--classification','formal','--scene','minecraft',
            '--camera-profile','flythrough-wide-yaw-360','--test-mode',run['semantic_id'],
            '--patch-scale','4','--patch-pool','mean','--skip-error-map-video']
        with (dest/'execution.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800,cwd=ROOT)
    result=load_result(target,ref.pixel_sha256)
    assert result['test_sequence']['pixel_sha256']==test.pixel_sha256
    assert result['provenance']==dict(scene='minecraft',camera_profile='flythrough-wide-yaw-360',test_mode=run['semantic_id'],reference_id='SS-Reference')
    assert result['runtime']['device']=='cuda' and result['runtime']['cuda_available']
    for side in ('test','reference'):
        v=result[side+'_sequence']
        assert (v['frame_count'],v['first_index'],v['last_index'],v['width'],v['height'])==(30,410,439,1920,1017)
    recheck=root/'baseline-recheck.json'
    prior=json.loads(recheck.read_text())['prior'] if recheck.exists() else dict(old)
    old.update(result=str(target),result_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
               score=result['score'],reused_historical_baseline=False,newly_computed_this_invocation=fresh)
    (root/'jobs.json').write_text(json.dumps(jobs,indent=2))
    recheck.write_text(json.dumps(dict(status='PASS',prior=prior,fresh=old,
        score_difference=result['score']-prior['score'],reason='Independent recomputation despite matching pixel hashes after an unreproduced analyzer assertion'),indent=2))
    print('PASS fresh Minecraft transition baseline:',result['score'],flush=True)
if __name__=='__main__':main()
