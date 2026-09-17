"""Run official CGVQM-2 on contrast ablations after the aligned-reference gate."""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from analyze_temporal_contrast_reference import MODES, WINDOWS

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--cgvqm-root',type=Path,required=True)
    a=p.parse_args();q=json.loads((a.analysis/'reference-quality.json').read_text())
    assert q['native_and_mask_bridge']==480 and q['selection_mismatches']==0
    assert q['selection_semantics_frames']==720
    assert q['reference_late_still_unique_png']==1 or (len(q.get('reference_late_still_steps',[]))==40 and
        all(x['max_rgb_step']<=1 and x['changed_channels']<=16 for x in q['reference_late_still_steps']))
    capture=Path(q['capture']);reference=Path(q['quality_capture'])/'SS-Reference'
    runner=Path(__file__).with_name('run_cgvqm_png_sequences.py')
    results={};ref_hashes={}
    for window in ('moving','transition'):
        start,end=WINDOWS[window];results[window]={}
        for mode in MODES:
            out=a.analysis/'CGVQM2'/window/mode;result=out/'CGVQM-Results.json'
            if not result.exists():
                cmd=[sys.executable,str(runner),'--test-dir',str(capture/mode),'--reference-dir',str(reference),
                     '--output-dir',str(out),'--start-index',str(start),'--frames',str(end-start),
                     '--cgvqm-root',str(a.cgvqm_root),'--model','2','--classification','engineering',
                     '--scene',q['scene'],'--camera-profile','original-flythrough-t2-still60-move120-still60',
                     '--test-mode',mode,'--reference-id','SS-Reference','--device','cuda',
                     '--patch-scale','4','--patch-pool','mean','--skip-error-map-video']
                print(f'START {q["scene"]}/{window}/{mode}',flush=True)
                out.mkdir(parents=True,exist_ok=True)
                with (out/'runner.log').open('w',encoding='utf-8') as log:
                    subprocess.run(cmd,check=True,timeout=600,stdout=log,stderr=subprocess.STDOUT)
            d=json.loads(result.read_text())
            assert d['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
            assert d['configuration']=={'fps':60,'patch_scale':4,'patch_pool':'mean','models':['2'],'reference_index_offset':0}
            assert d['runtime']['device']=='cuda' and d['provenance']['test_mode']==mode
            for prefix,path in (('test',capture/mode),('reference',reference)):
                s=d[prefix+'_sequence'];rt=d[prefix+'_round_trip']
                assert Path(s['directory']).resolve()==path.resolve()
                assert (s['width'],s['height'],s['first_index'],s['last_index'],s['frame_count'])==(1920,1061,start,end-1,end-start)
                assert rt['decoded_frames']==end-start and rt['mismatched_values']==rt['max_absolute_difference']==0
            ref_hash=d['reference_sequence']['pixel_sha256']
            assert ref_hashes.setdefault(window,ref_hash)==ref_hash
            score=d['results']['CGVQM-2']['score_higher_is_better'];assert math.isfinite(score)
            results[window][mode]={'score':score,'minus_native':score-results[window].get(MODES[0],{'score':score})['score'],
                                   'error_map':d['results']['CGVQM-2']['error_map'],
                                   'result':str(result.resolve()),'record':d}
            print(f'PASS {q["scene"]}/{window}/{mode}: {score:.6f}',flush=True)
    (a.analysis/'cgvqm-comparison.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f'PASS {q["scene"]}: 8 CGVQM-2 comparisons',flush=True)

if __name__=='__main__':main()
