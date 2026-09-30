"""Complete missing AA-Off/temporal-only scores and bridge unchanged stencil images."""
import argparse
import json
import subprocess
from pathlib import Path
from cgvqm_bounded_window import evaluate
from evaluate_baseline_cgvqm import stream,validate
from stencil_quality_common import DOC,OUT,SCENES,WINDOWS,manifest,cached_scores,write_sources


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scene',required=True,choices=SCENES)
    scene=parser.parse_args().scene
    # Quality inference and rendering never overlap.
    check=subprocess.run(['powershell','-NoProfile','-Command',"if (@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count) {exit 1}"],capture_output=True)
    assert check.returncode==0,'CMAA2 process is active'
    data=manifest(scene);results={};DOC.mkdir(parents=True,exist_ok=True)
    for window,(start,end) in WINDOWS.items():
        cached=cached_scores(scene,window)
        reference_hash=stream(data['reference'],start,end)
        records={};reused=[]
        for mode,record in cached.items():
            validate(record,start,end)
            assert reference_hash==record['reference_sequence']['pixel_sha256'],(scene,window,mode,'reference')
            assert stream(data['sequences'][mode],start,end)==record['test_sequence']['pixel_sha256'],(scene,window,mode,'output')
            records[mode]=record;reused.append(mode)
        print(f'PASS {scene}/{window}: six cached scores bridged to current images',flush=True)
        for mode in ['AA-Off','ABL-TemporalOnly-R']:
            folder=data['sequences'][mode]
            # These source folders contain only numbered final PNGs; probes are DDS.
            assert len(list(folder.glob('*.png')))==240,folder
            record=evaluate(folder,data['reference'],OUT/scene/'CGVQM2'/window/mode,scene,mode,start,end)
            validate(record,start,end)
            assert record['test_sequence']['pixel_sha256']==stream(folder,start,end)
            assert record['reference_sequence']['pixel_sha256']==reference_hash
            for key in ['torch','cuda_runtime','device']:
                assert record['runtime'][key]==cached['O-T2X-R']['runtime'][key]
            records[mode]=record
        scores={m:r['results']['CGVQM-2']['score_higher_is_better'] for m,r in records.items()}
        results[window]=dict(scores=scores,reused_via_pixel_hash=reused,newly_evaluated=['AA-Off','ABL-TemporalOnly-R'],records=records)
        print(json.dumps(dict(scene=scene,window=window,scores=scores)),flush=True)
    result=dict(validation='PASS',scene=scene,results=results,
                sequences={k:str(v) for k,v in data['sequences'].items()},reference=str(data['reference']),
                scope='CGVQM-2 with supersample spatial reference; not absolute ghosting ground truth. Stencil scores reused only after current pixel-hash equality.')
    (DOC/f'{scene}-cgvqm.json').write_text(json.dumps(result,indent=2)+'\n')
    write_sources(f'{scene}-cgvqm-sources.json')


if __name__=='__main__':main()
