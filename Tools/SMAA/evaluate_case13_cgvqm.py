"""Official CGVQM-2 auxiliary evaluation; exact control/reference RGB bridges."""
import argparse,copy,json,subprocess,sys
from pathlib import Path
from evaluate_baseline_cgvqm import validate,stream
from analyze_case13_quality import ROOT,DOC,MODES,CONTROL_DOC,load
from edge_quality_inputs import sha

def evaluate(scene,window,start,end,capture,reference):
    mode=MODES[3]
    sequence=capture/'cgvqm-final-only'/mode
    sequence.mkdir(parents=True,exist_ok=True)
    for index in range(240):
        source=capture/mode/f'frame_{index:05d}.png';target=sequence/source.name
        if not target.exists():target.hardlink_to(source)
        assert target.samefile(source)
    output=ROOT/'tmp/edge-catmull-rom-rgb-feedback/cgvqm'/scene/window
    output.mkdir(parents=True,exist_ok=True);parts=[]
    for first in range(start,end,60):
        dest=output/f'part-{first:05d}-{first+59:05d}';dest.mkdir(exist_ok=True)
        result=dest/'CGVQM-Results.json'
        if not result.exists():
            args=[sys.executable,str(ROOT/'Tools/SMAA/run_cgvqm_png_sequences.py'),
                '--test-dir',str(sequence),'--reference-dir',str(reference),'--output-dir',str(dest),
                '--start-index',str(first),'--frames','60',
                '--cgvqm-root',str(ROOT.parents[2]/'.research-tools/CGVQM'),
                '--model','2','--classification','engineering','--scene',scene,
                '--camera-profile','original-flythrough-t2-still60-move120-still60',
                '--test-mode',mode,'--reference-id','SS-Reference-spatial-proxy',
                '--device','cuda','--patch-scale','4','--patch-pool','mean','--skip-error-map-video']
            print(scene,13,window,first,'CGVQM',flush=True)
            with (dest/'runner.log').open('w',encoding='utf-8') as log:
                subprocess.run(args,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        data=load(result);validate(data,first,first+60)
        assert data['provenance']['test_mode']==mode and data['provenance']['scene']==scene
        assert data['test_sequence']['pixel_sha256']==stream(capture/mode,first,first+60)
        assert data['reference_sequence']['pixel_sha256']==stream(reference,first,first+60)
        parts.append(data)
    record=copy.deepcopy(parts[0])
    score=sum(p['results']['CGVQM-2']['score_higher_is_better'] for p in parts)/len(parts)
    for kind,folder in [('test',capture/mode),('reference',reference)]:
        record[kind+'_sequence'].update(first_index=start,last_index=end-1,
            frame_count=end-start,pixel_sha256=stream(folder,start,end))
        trips=[p[kind+'_round_trip'] for p in parts]
        record[kind+'_round_trip']=dict(videos=[t['video'] for t in trips],decoded_frames=end-start,
            mismatched_values=sum(t['mismatched_values'] for t in trips),
            max_absolute_difference=max(t['max_absolute_difference'] for t in trips))
    record['results']={'CGVQM-2':dict(score_higher_is_better=score)}
    record['official_chunk_results']=parts
    record['evaluation_method']='Equal-patch pooled official 60-frame calls; unchanged 30-frame patches; case13 has no full-window model rerun.'
    validate(record,start,end)
    (output/'CGVQM-Results.json').write_text(json.dumps(record,indent=2)+'\n')
    return dict(case=13,mode=mode,score=score,record=record,reused=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True)
    scene=p.parse_args().scene
    quality=load(DOC/f'{scene}-capture.json')
    assert quality['validation']=='PASS' and quality['control_bridge']['rgb_mismatch']==0
    cap=Path(quality['capture_root']);reference=Path(quality['reference_root'])
    source_path=CONTROL_DOC/f'{scene}-cgvqm.json';source=load(source_path)
    assert source['validation']=='PASS';windows=[]
    for window,start,end in [('moving',60,180),('transition',160,220)]:
        old=next(w for w in source['windows'] if w['window']==window);records=[]
        for case,index in [(4,0),(10,1),(11,2)]:
            item=copy.deepcopy(next(r for r in old['records'] if r['case']==case))
            record=item['record'];validate(record,start,end)
            assert item['mode']==MODES[index]
            assert record['test_sequence']['pixel_sha256']==stream(cap/MODES[index],start,end)
            assert record['reference_sequence']['pixel_sha256']==stream(reference,start,end)
            assert len(record['official_chunk_results'])==(end-start)//60
            assert item['score']==record['results']['CGVQM-2']['score_higher_is_better']
            for first,chunk in zip(range(start,end,60),record['official_chunk_results']):
                validate(chunk,first,first+60)
                assert chunk['test_sequence']['pixel_sha256']==stream(cap/MODES[index],first,first+60)
                assert chunk['reference_sequence']['pixel_sha256']==stream(reference,first,first+60)
            item['reused']='Existing official score; current decoded RGB/reference bridge verified'
            records.append(item)
        new=evaluate(scene,window,start,end,cap,reference)
        for key in ('torch','cuda_runtime','device'):
            assert new['record']['runtime'][key]==records[0]['record']['runtime'][key]
        records.append(new);windows.append(dict(window=window,frames=[start,end-1],records=records))
        print(scene,window,{str(r['case']):r['score'] for r in records},flush=True)
    result=dict(validation='PASS',scene=scene,
        scope='Auxiliary official CGVQM-2 vs supersampled spatial proxy; not temporal/ghosting ground truth. Direct lossless frames decide visual quality.',
        capture_evidence_sha256=sha(DOC/f'{scene}-capture.json'),
        reused_source_path=str(source_path),reused_source_sha256=sha(source_path),windows=windows)
    (DOC/f'{scene}-cgvqm.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
