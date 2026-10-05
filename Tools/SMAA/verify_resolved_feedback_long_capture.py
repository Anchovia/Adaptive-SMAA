"""Presentation capture: exact control bridges, complete mode checks and PNG hashes."""
import argparse,csv,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from analyze_edge_resolved_rgb_feedback import ROOT,DOC,MODES,load,capture_root
from edge_quality_inputs import ph,rgb

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scene',required=True,choices=['bistro','minecraft'])
    scene=parser.parse_args().scene
    receipt=next(x for x in reversed(load(ROOT/'tmp/edge-resolved-rgb-feedback-runs.json')) if x['scene']==scene and x['phase']=='Capture' and x['frames']==720 and x['start_time']==2)
    capture=capture_root(receipt)
    rows=[[c.strip() for c in row] for row in csv.reader(Path(receipt['report']).read_text(encoding='utf-8-sig').splitlines())]
    timeline=next(r for r in rows if r and r[0]=='presentation_timeline')
    assert timeline[1:6]==['720','60','600','60','60fps'] and float(timeline[6])==2
    assert not any(r and r[0]=='trace' for r in rows),'Long presentation diagnostics must be off'
    old=next(x for x in load(ROOT.parents[2]/'tmp/six-case-long/case10-validated.json') if x['scene']==scene and x['start_time']==2)
    assert old['validation']=='PASS'
    hashes={}
    for mode in MODES:
        checks=[r for r in rows if r and r[0]=='mode_check' and r[1]==mode]
        assert [int(r[2]) for r in checks]==list(range(720)) and all(r[4]=='PASS' for r in checks)
        paths=sorted((capture/mode).glob('frame_[0-9][0-9][0-9][0-9][0-9].png'));assert len(paths)==720
        with ThreadPoolExecutor(max_workers=4) as pool:hashes[mode]=list(pool.map(lambda p:ph(rgb(p)),paths))
        if mode in MODES[:2]:assert hashes[mode]==old['rgb_hashes'][mode],(scene,mode,'old control mismatch')
    result=dict(validation='PASS',classification='720-frame presentation only; no new quality reference or timing',scene=scene,
        receipt=receipt,capture_root=str(capture),frames=720,start_time=2,source_fps=60,modes=MODES,
        rgb_hashes=hashes,controls_compared_frames=1440,control_rgb_mismatch=0,
        original_control_receipt={k:old[k] for k in ['capture_root','report','report_sha256','commit','branch']},
        stable_still_unique_hashes={m:len(set(hashes[m][700:720])) for m in MODES})
    (DOC/f'{scene}-long-capture.json').write_text(json.dumps(result,indent=2)+'\n')
    print(scene,'PASS long 3x720; original4/10 controls equal')

if __name__=='__main__':main()
