"""Bridge existing 4/10/13 captures to the unchanged case14 long capture."""
import argparse,csv,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from edge_quality_inputs import sha,ph,rgb

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-History-Four-Case-Playback'
MODES=['O-T2X-R','ABL-ET2X-R-PreviousRawEdge-BilinearRGB',
       'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB',
       'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def verify(scene):
    DOC.mkdir(parents=True,exist_ok=True)
    older=load(ROOT/f'Docs/Edge-History-Catmull-Rom-Reconstruction/{scene}-long-capture.json')
    short=load(ROOT/f'Docs/Edge-History-Fixed-Weight-080/{scene}-capture.json')
    assert older['validation']==short['validation']=='PASS'
    receipt=next(r for r in reversed(load(ROOT/'tmp/edge-fixed-weight-rgb-feedback-runs.json'))
                 if r['scene']==scene and r['phase']=='Capture' and r['frames']==720 and r['start_time']==2)
    report=Path(receipt['report']);assert sha(report).upper()==receipt['report_sha256']
    text=report.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[[s.strip() for s in r] for r in csv.reader(text.splitlines())]
    timeline=next(r for r in rows if r and r[0]=='presentation_timeline')
    assert timeline[1:6]==['720','60','600','60','60fps'] and float(timeline[6])==2
    assert not any(r and r[0]=='trace' for r in rows)
    capture=Path(next(r[1] for r in rows if r and r[0]=='capture_root'))
    oldroot=Path(older['capture_root'])
    sources={m:oldroot/m for m in MODES[:3]};sources[MODES[3]]=capture/MODES[3]
    if scene=='minecraft':
        sources[MODES[2]]=capture/MODES[2]
        audit=load(DOC/'minecraft-control-differences.json')
        assert audit['case13_different_frames']==0 and not audit['case14_short_prefix_mismatches']
    hashes={};last={};previous={}
    for m in [MODES[0],MODES[2],MODES[3]]:
        checks=[r for r in rows if r and r[0]=='mode_check' and r[1]==m]
        assert [int(r[2]) for r in checks]==list(range(720)) and all(r[4]=='PASS' for r in checks)
    for m in MODES:
        paths=sorted(sources[m].glob('frame_[0-9][0-9][0-9][0-9][0-9].png'))
        assert len(paths)==720,(m,len(paths));hashes[m]=[];last[m]=0
        def verify_frame(item):
            f,p=item
            assert p.name==f'frame_{f:05d}.png'
            h=ph(rgb(p))
            if m!=MODES[-1]:assert h==older['output_hashes'][m][f],(scene,m,f,'old capture hash changed')
            if m==MODES[0] or (m==MODES[2] and scene=='bistro'):
                assert ph(rgb(capture/m/p.name))==h,(scene,m,f,'long control bridge failed')
            if f<180 and m in short['output_hashes']:
                assert h==short['output_hashes'][m][f],(scene,m,f,'short common pose bridge failed')
            return f,h
        with ThreadPoolExecutor(max_workers=4) as pool:
            for f,h in pool.map(verify_frame,enumerate(paths)):
                hashes[m].append(h)
                if f and h!=previous[m]:last[m]=f
                previous[m]=h
        print(scene,m,'720 RGB frames PASS',flush=True)
    result=dict(validation='PASS',classification='four-case 720-frame playback; no new timing or reference',
                frames=720,source_fps=60,start_time=2,timeline=dict(initial_still=60,moving=600,final_still=60),
                receipt=receipt,new_capture_root=str(capture),sources={m:str(p) for m,p in sources.items()},
                mode_order=MODES,rgb_hashes=hashes,control_rgb_mismatch=0,
                old_controls_verified_frames=2160 if scene=='bistro' else 1440,
                new_control_bridge_frames=1440 if scene=='bistro' else 720,
                case13_current_capture_vs_stored_hash_frames=720,
                case14_short_prefix_verified_frames=180,whole_rgb_last_change=last,
                source_evidence=[dict(path=str(p),sha256=sha(p)) for p in [ROOT/f'Docs/Edge-History-Catmull-Rom-Reconstruction/{scene}-long-capture.json',ROOT/f'Docs/Edge-History-Fixed-Weight-080/{scene}-capture.json']],
                verified_redundant_directories=[str(capture/MODES[0])]+([str(capture/MODES[2])] if scene=='bistro' else []))
    if scene=='minecraft':
        result['initial_reader_failure']='First concurrent original-file comparison failed at case13 frame98, followed by a broken PNG stream reading an old file. Fresh case13 matches all 720 stored original RGB hashes and case14 matches all 180 short-prefix hashes. Cause not assigned; use fresh case13 originals rather than old case13 physical files.'
    (DOC/f'{scene}-inputs.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(scene,'PASS four-case bridge; new duplicate controls can reuse verified old originals',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',required=True,choices=['bistro','minecraft']);verify(p.parse_args().scene)
