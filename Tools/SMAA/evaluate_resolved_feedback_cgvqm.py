"""Auxiliary CGVQM-2; bounded official invocations and exact input bridges."""
import argparse,copy,json,subprocess,sys
from pathlib import Path
from evaluate_baseline_cgvqm import stream,validate
from analyze_edge_resolved_rgb_feedback import ROOT,DOC,MODES,load
from edge_quality_inputs import sha

def evaluate(sequence,reference,out,scene,start,end):
    # Same official 30-frame temporal patches; 60-frame parts bound host memory.
    assert (end-start)%60==0
    chunks=[]
    for first in range(start,end,60):
        dest=out/f'part-{first:05d}-{first+59:05d}';dest.mkdir(parents=True,exist_ok=True)
        rp=dest/'CGVQM-Results.json'
        if not rp.exists():
            print(f'CGVQM-2 case11 {scene} {first}..{first+59}',flush=True)
            cmd=[sys.executable,str(ROOT/'Tools/SMAA/run_cgvqm_png_sequences.py'),
                 '--test-dir',str(sequence),'--reference-dir',str(reference),'--output-dir',str(dest),
                 '--start-index',str(first),'--frames','60','--cgvqm-root',str(ROOT.parents[2]/'.research-tools/CGVQM'),
                 '--model','2','--classification','engineering','--scene',scene,
                 '--camera-profile','original-flythrough-t2-still60-move120-still60',
                 '--test-mode',MODES[2],'--reference-id','SS-Reference-spatial-proxy',
                 '--device','cuda','--patch-scale','4','--patch-pool','mean','--skip-error-map-video']
            with (dest/'runner.log').open('w',encoding='utf-8') as log:
                subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        record=load(rp);validate(record,first,first+60)
        assert record['test_sequence']['pixel_sha256']==stream(sequence,first,first+60)
        assert record['reference_sequence']['pixel_sha256']==stream(reference,first,first+60)
        assert record['provenance']['scene']==scene and record['provenance']['test_mode']==MODES[2]
        chunks.append(record)
    result=copy.deepcopy(chunks[0])
    for kind,folder in [('test',sequence),('reference',reference)]:
        result[kind+'_sequence'].update(first_index=start,last_index=end-1,frame_count=end-start,pixel_sha256=stream(folder,start,end))
        trips=[c[kind+'_round_trip'] for c in chunks]
        result[kind+'_round_trip']=dict(videos=[t['video'] for t in trips],decoded_frames=end-start,
            mismatched_values=sum(t['mismatched_values'] for t in trips),max_absolute_difference=max(t['max_absolute_difference'] for t in trips))
    result['results']={'CGVQM-2':{'score_higher_is_better':sum(c['results']['CGVQM-2']['score_higher_is_better'] for c in chunks)/len(chunks)}}
    result['official_chunk_results']=chunks
    result['evaluation_method']='Equal-patch mean of official 60-frame invocations; unchanged 30-frame patch boundaries; cached native chunk/full bridge in source evidence.'
    validate(result,start,end)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scene',choices=['bistro','minecraft'],required=True)
    scene=parser.parse_args().scene
    quality=load(DOC/f'{scene}-capture.json');assert quality['validation']=='PASS' and quality['control_bridge']['rgb_mismatch']==0
    capture=Path(quality['capture_root']);reference=Path(quality['reference_root'])
    sequence=ROOT/'tmp/edge-resolved-rgb-feedback/cgvqm-inputs'/scene/MODES[2];sequence.mkdir(parents=True,exist_ok=True)
    for i in range(240):
        source=capture/MODES[2]/f'frame_{i:05d}.png';target=sequence/source.name
        if not target.exists():target.hardlink_to(source)
        assert target.samefile(source)
    sources=load(DOC/'sources/case10-quality-cgvqm.json');windows=[]
    for window,start,end in [('moving',60,180),('transition',160,220)]:
        refhash=stream(reference,start,end);records={}
        for case,mode in [(4,MODES[0]),(10,MODES[1])]:
            source=next(x for x in sources if x['scene']==scene and x['case']==case and x['window']==window)
            record=source['record'];validate(record,start,end)
            bridge=record.get('native_full_window_bridge')
            if case==4:
                assert bridge and bridge['validation']=='PASS' and abs(bridge['score_difference'])<=bridge['tolerance']<=0.00002
            # Case10 has official bounded chunks, not a full-window model bridge.
            # Verify each chunk and its current pixels instead of inventing a bridge.
            chunks=record['official_chunk_results'];assert len(chunks)==(end-start)//60
            for first,chunk in zip(range(start,end,60),chunks):
                validate(chunk,first,first+60)
                assert chunk['test_sequence']['pixel_sha256']==stream(capture/mode,first,first+60)
                assert chunk['reference_sequence']['pixel_sha256']==stream(reference,first,first+60)
            pooled=sum(c['results']['CGVQM-2']['score_higher_is_better'] for c in chunks)/len(chunks)
            assert abs(pooled-record['results']['CGVQM-2']['score_higher_is_better'])<1e-7
            assert record['test_sequence']['pixel_sha256']==stream(capture/mode,start,end)
            assert record['reference_sequence']['pixel_sha256']==refhash
            records[str(case)]=dict(score=record['results']['CGVQM-2']['score_higher_is_better'],reuse='Existing official score; current decoded RGB/reference hash verified; model not rerun',record=record)
        out=ROOT/'tmp/edge-resolved-rgb-feedback/cgvqm'/scene/window
        record=evaluate(sequence,reference,out,scene,start,end)
        record['native_full_window_bridge']=None
        record['native_control_pooling_bridge']=records['4']['record']['native_full_window_bridge']
        record['bridge_scope']='Case4 validates bounded pooling against its native full-window invocation. Case11 itself has no full-window model rerun.'
        for key in ['torch','cuda_runtime','device']:assert record['runtime'][key]==records['4']['record']['runtime'][key]
        records['11']=dict(score=record['results']['CGVQM-2']['score_higher_is_better'],reuse=False,record=record)
        (out/'CGVQM-Results.json').write_text(json.dumps(record,indent=2)+'\n')
        windows.append(dict(window=window,frames=[start,end-1],records=records,
            case11_minus_4=records['11']['score']-records['4']['score'],case11_minus_10=records['11']['score']-records['10']['score']))
        print(json.dumps(dict(scene=scene,window=window,scores={k:v['score'] for k,v in records.items()})),flush=True)
    result=dict(validation='PASS',scene=scene,capture_evidence_sha256=sha(DOC/f'{scene}-capture.json'),
        scope='Auxiliary official CGVQM-2 against supersampled spatial proxy; not absolute ghosting ground truth; direct lossless frame inspection controls quality judgment.',windows=windows)
    (DOC/f'{scene}-cgvqm.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
