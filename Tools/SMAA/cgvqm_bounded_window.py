"""Retain official 30-frame inference boundaries while bounding CPU commit with <=60-frame invocations.

For fixed resolution, fps=60, patch_scale=4 and mean pooling, equal 60-frame
parts contain equal numbers of the exact same official 30-frame patches.
Their scores have the same mathematical mean as the full window. Floating-point
reduction order can differ; callers must bridge to a cached native full-window score.
The official model/source is not modified.
"""
import copy,json,subprocess,sys
from pathlib import Path
from evaluate_baseline_cgvqm import stream,validate
R=Path(__file__).resolve().parents[2]
def evaluate(sequence,reference,out,scene,mode,start,end):
    assert (end-start)%60==0
    out.mkdir(parents=True,exist_ok=True);records=[]
    for first in range(start,end,60):
        dest=out/f'part-{first:05d}-{first+59:05d}';dest.mkdir(exist_ok=True);rp=dest/'CGVQM-Results.json'
        if not rp.exists():
            print(f'CGVQM {scene} {mode} {first}..{first+59}',flush=True)
            cmd=[sys.executable,str(R/'Tools/SMAA/run_cgvqm_png_sequences.py'),'--test-dir',str(sequence),'--reference-dir',str(reference),'--output-dir',str(dest),'--start-index',str(first),'--frames','60','--cgvqm-root',str(R.parents[2]/'.research-tools/CGVQM'),'--model','2','--classification','engineering','--scene',scene,'--camera-profile','original-flythrough-t2-still60-move120-still60','--test-mode',mode,'--reference-id','SS-Reference','--device','cuda','--patch-scale','4','--patch-pool','mean','--skip-error-map-video']
            with (dest/'runner.log').open('w',encoding='utf-8') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        record=json.loads(rp.read_text());validate(record,first,first+60)
        assert record['test_sequence']['pixel_sha256']==stream(sequence,first,first+60)
        assert record['reference_sequence']['pixel_sha256']==stream(reference,first,first+60)
        assert record['provenance']['scene']==scene and record['provenance']['test_mode']==mode
        records.append(record)
    result=copy.deepcopy(records[0]);n=end-start
    for kind,folder in [('test',sequence),('reference',reference)]:
        result[kind+'_sequence'].update(first_index=start,last_index=end-1,frame_count=n,pixel_sha256=stream(folder,start,end))
        trips=[v[kind+'_round_trip'] for v in records]
        result[kind+'_round_trip']=dict(video=None,videos=[v['video'] for v in trips],codec='ffv1',pixel_format='bgr0',decoded_frames=n,
            mismatched_values=sum(v['mismatched_values'] for v in trips),max_absolute_difference=max(v['max_absolute_difference'] for v in trips),
            verification_attempts=sum(v['verification_attempts'] for v in trips),transient_mismatched_values=sum(v['transient_mismatched_values'] for v in trips),
            transient_max_absolute_difference=max(v['transient_max_absolute_difference'] for v in trips))
    result['results']={'CGVQM-2':{'score_higher_is_better':sum(v['results']['CGVQM-2']['score_higher_is_better'] for v in records)/len(records)}}
    result['evaluation_method']='Official <=60-frame invocations aligned to original 30-frame inference boundaries; equal-patch mean aggregation; no source or sampling change.'
    result['official_chunk_results']=records
    result['aggregate_requires_native_bridge_tolerance']=0.00002
    (out/'CGVQM-Results.json').write_text(json.dumps(result,indent=2)+'\n');validate(result,start,end);return result
