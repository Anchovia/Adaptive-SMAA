"""Evaluate masked clips with official CGVQM-2 after the reference/hash gate passes."""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from analyze_standard_edge_mask_quality import BASE, WINDOWS, CG_WINDOWS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',choices=('bistro','minecraft'),required=True)
    p.add_argument('--output',type=Path,default=BASE/'20260917_StandardEdgeMaskQuality')
    args=p.parse_args()
    summary=json.loads((args.output/f'{args.scene}_summary.json').read_text())
    assert summary['provenance']['mismatches']==0
    record=next(r for r in summary['provenance']['capture_records'] if r['mode']=='ABL-Standard-EdgeMask-R')
    source=Path(record['report']).parent/'ABL_Standard_EdgeMask_R'
    ref=Path(summary['provenance']['reference_root'])/'SS_Reference'
    runner=Path(__file__).with_name('run_cgvqm_png_sequences.py')
    results={}
    for window,folder in CG_WINDOWS.items():
        start,end=WINDOWS[window]
        out=args.output/'CGVQM2'/args.scene/folder
        result=out/'CGVQM-Results.json'
        if not result.exists():
            command=[sys.executable,str(runner),'--test-dir',str(source),'--reference-dir',str(ref),
                     '--output-dir',str(out),'--start-index',str(start),'--frames',str(end-start),
                     '--model','2','--classification','formal','--scene',args.scene.title(),
                     '--camera-profile','flythrough-wide-yaw-360','--test-mode','ABL-Standard-EdgeMask-R',
                     '--reference-id','SS-Reference','--device','cuda','--patch-scale','4','--patch-pool','mean',
                     '--skip-error-map-video']
            print(f'START {args.scene}/{window}',flush=True)
            subprocess.run(command,check=True,timeout=600)
        d=json.loads(result.read_text())
        assert d['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
        assert d['runtime']['device']=='cuda'
        assert d['configuration']['models']==['2']
        assert d['configuration']['patch_scale']==4 and d['configuration']['patch_pool']=='mean'
        assert d['configuration']['fps']==60 and d['configuration']['reference_index_offset']==0
        original=json.loads(Path(summary['standard_cgvqm_reused'][window]['source']).read_text())
        assert original['configuration']==d['configuration']
        assert original['runtime']['torch']==d['runtime']['torch']
        assert original['runtime']['cuda_runtime']==d['runtime']['cuda_runtime']
        assert original['runtime']['gpu']==d['runtime']['gpu']
        assert d['provenance']['test_mode']=='ABL-Standard-EdgeMask-R'
        assert d['provenance']['camera_profile']=='flythrough-wide-yaw-360'
        for key,hashkey in [('test','masked'),('reference','reference')]:
            s=d[key+'_sequence'];rt=d[key+'_round_trip']
            assert (s['width'],s['height'])==(1920,1017)
            assert s['pixel_sha256']==summary['pixel_hashes'][window][hashkey]
            assert s['first_index']==start and s['last_index']==end-1 and s['frame_count']==end-start
            assert rt['decoded_frames']==end-start and rt['mismatched_values']==rt['max_absolute_difference']==0
        score=d['results']['CGVQM-2']['score_higher_is_better']
        assert math.isfinite(score)
        control=summary['standard_cgvqm_reused'][window]['score']
        results[window]={'standard':control,'masked':score,'masked_minus_standard':score-control,
                         'masked_result':str(result),'standard_reuse':summary['standard_cgvqm_reused'][window]}
        print(f'PASS {args.scene}/{window}: Standard={control:.6f}, EdgeMask={score:.6f}, delta={score-control:+.6f}',flush=True)
    (args.output/f'{args.scene}_cgvqm_comparison.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':
    main()
