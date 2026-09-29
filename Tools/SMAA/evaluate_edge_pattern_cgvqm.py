"""Evaluate Off full/selective against aligned supersample spatial reference; reuse verified native control."""
import argparse,json,subprocess,sys
from pathlib import Path
from analyze_edge_pattern import R,D,B,ITEM,FULL,SEL,sha
from evaluate_baseline_cgvqm import stream,validate
from cgvqm_bounded_window import evaluate
def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);scene=p.parse_args().scene
    q=json.loads((D/f'{scene}-capture.json').read_text());assert q['validation']=='PASS';cap=Path(q['capture'])
    ref=Path(json.loads((R/'Docs/Baseline-Restart/reused-reference-provenance.json').read_text())[scene]['reference'])
    results={}
    for window,(start,end) in dict(moving=(60,180),transition=(160,220)).items():
        nr=B/'ContrastReferenceAnalysis'/scene/'CGVQM2'/window/'O-T2X-R/CGVQM-Results.json';native=json.loads(nr.read_text());validate(native,start,end)
        refhash=stream(ref,start,end);assert refhash==native['reference_sequence']['pixel_sha256']
        # The current run's original control is byte-hash bridged to the independent native capture.
        prior=Path(q.get('native_baseline',q['prior']));assert stream(prior/'O-T2X-R',start,end)==native['test_sequence']['pixel_sha256']
        if end-start>60:
            native_sequence=R/'tmp'/f'edge-pattern-native-{scene}'/'O-T2X-R';native_sequence.mkdir(parents=True,exist_ok=True)
            for i in range(240):
                source=prior/'O-T2X-R'/f'frame_{i:05d}.png';target=native_sequence/source.name
                if not target.exists():target.hardlink_to(source)
                assert sha(target)==sha(source)
            bridge=evaluate(native_sequence,ref,cap/'CGVQM2'/window/'Native-Bridge',scene,'O-T2X-R',start,end)
            difference=bridge['results']['CGVQM-2']['score_higher_is_better']-native['results']['CGVQM-2']['score_higher_is_better']
            assert abs(difference)<=0.00002,(scene,'native chunk bridge',difference)
        else:bridge=None;difference=0
        entry={'O-T2X-R':native}
        for mode in [FULL,SEL]:
            # Official input collector requires only numbered final PNGs, without diagnostic snapshots.
            sequence=cap/'CGVQM-inputs'/mode;sequence.mkdir(parents=True,exist_ok=True)
            for i in range(240):
                source=cap/mode/f'frame_{i:05d}.png';target=sequence/source.name
                if not target.exists():target.hardlink_to(source)
                assert target.samefile(source)  # Same NTFS file, with identical bytes by construction.
            out=cap/'CGVQM2'/window/mode;out.mkdir(parents=True,exist_ok=True);rp=out/'CGVQM-Results.json'
            record=evaluate(sequence,ref,out,scene,mode,start,end);validate(record,start,end)
            assert record['test_sequence']['pixel_sha256']==stream(cap/mode,start,end) and record['reference_sequence']['pixel_sha256']==refhash
            assert record['provenance']['test_mode']==mode and record['provenance']['scene']==scene
            for k in ['torch','cuda_runtime','device']:assert record['runtime'][k]==native['runtime'][k]
            entry[mode]=record
        scores={m:v['results']['CGVQM-2']['score_higher_is_better'] for m,v in entry.items()}
        results[window]=dict(scores=scores,selective_minus_native=scores[SEL]-scores['O-T2X-R'],selective_minus_off_full=scores[SEL]-scores[FULL],records=entry,native_chunk_bridge=bridge,native_bridge_score_difference=difference)
        print(json.dumps(dict(scene=scene,window=window,scores=scores)),flush=True)
    (D/f'{scene}-cgvqm.json').write_text(json.dumps(dict(validation='PASS',item=ITEM,scene=scene,capture_report_sha256=sha(D/f'{scene}-capture.json'),reference=str(ref),results=results,scope='Official CGVQM-2 full-reference score, higher better. Spatial supersample reference; not absolute ghosting ground truth. 60 FPS.'),indent=2)+'\n')
if __name__=='__main__':main()
