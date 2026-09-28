"""Validate independent baseline captures; no selective implementation in this branch."""
import argparse,csv,hashlib,json,statistics
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Baseline-Restart'
MODES=['AA-Off','O-1X','O-T2X','O-T2X-R','O-1X-Repeat','O-T2X-R-Repeat']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rgb(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(p,im.mode,im.size)
        return np.asarray(im).copy()

def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);a=p.parse_args()
    receipts=json.loads((ROOT/'tmp/baseline-restart-runs.json').read_text(encoding='utf-8-sig'))
    records=[r for r in receipts if r['phase']=='Capture' and r['scene']==a.scene];assert len(records)==1
    receipt=records[0];report=Path(receipt['report']);assert sha(report)==receipt['report_sha256'].lower()
    text=report.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'Aggregate: FAIL' not in text
    checks=[r for r in csv.reader(text.splitlines()) if r and r[0].strip()=='mode_check'];assert len(checks)==1440
    for mode in MODES:
        rows=[[x.strip() for x in r] for r in checks if r[1].strip()==mode]
        assert [int(r[2]) for r in rows]==list(range(240))
        temporal=mode not in ['AA-Off','O-1X','O-1X-Repeat'];reprojection=mode.startswith('O-T2X-R')
        assert all(r[3:6]==['TemporalOn' if temporal else 'TemporalOff','CameraR' if reprojection else 'NoR','PASS'] and not any(r[6:]) for r in rows)
    capture=report.parent;expected=[f'frame_{i:05d}.png' for i in range(240)]
    for mode in MODES:assert [p.name for p in sorted((capture/mode).glob('*.png'))]==expected
    old=json.loads((DOC/'reused-reference-provenance.json').read_text())[a.scene];oldcap=Path(old['capture'])
    repeat_mismatches=0;old_native_mismatches=[];hashes={m:[] for m in MODES[:4]};prev={};rows=[]
    for i,f in enumerate(expected):
        images={m:rgb(capture/m/f) for m in MODES[:4]}
        for m in ['O-1X','O-T2X-R']:
            repeat_mismatches+=int(not np.array_equal(images[m],rgb(capture/(m+'-Repeat')/f)))
        if not np.array_equal(images['O-T2X-R'],rgb(oldcap/'O-T2X-R'/f)):old_native_mismatches.append(i)
        changed=np.any(images['O-1X']!=images['AA-Off'],axis=2)
        for mode,im in images.items():
            hashes[mode].append(hashlib.sha256(im.tobytes()).hexdigest())
            rows.append(dict(frame=i,mode=mode,rgb_step=float(np.abs(im.astype(np.int16)-prev[mode].astype(np.int16)).mean()) if mode in prev else None,
                spatial_changed_pixels=int(changed.sum()) if mode=='O-1X' else None))
            prev[mode]=im
        if i%60==59:print(f'{a.scene}: {i+1}/240 frames validated',flush=True)
    assert repeat_mismatches==0
    static={}
    for window,start,end in [('initial_still',20,60),('late_still',200,240)]:
        static[window]={mode:dict(unique_rgb_frames=len(set(hashes[mode][start:end])),rgb_step=statistics.mean(r['rgb_step'] for r in rows if r['mode']==mode and start<=r['frame']<end)) for mode in MODES[:4]}
        assert static[window]['O-1X']['unique_rgb_frames']==1,'Actual SMAA 1X failed static gate'
        assert static[window]['O-T2X-R']['unique_rgb_frames']==1,'Original T2X-R failed static gate'
    changed=[r['spatial_changed_pixels'] for r in rows if r['mode']=='O-1X'];assert min(changed)>0,'SMAA 1X identical to AA-Off'
    result=dict(scene=a.scene,validation='PASS',receipt=receipt,capture=str(capture),mode_checks=1440,repeat_comparisons=480,repeat_mismatches=repeat_mismatches,
        old_native_comparisons=240,old_native_mismatch_count=len(old_native_mismatches),old_native_mismatch_frames=old_native_mismatches,
        old_quality_report_sha256=old['source_sha256'],old_capture=str(oldcap),reference=old['reference'],reference_reuse_allowed=len(old_native_mismatches)==0,
        static=static,spatial_aa_changed_pixels=dict(min=min(changed),mean=statistics.mean(changed),max=max(changed)),
        scope='Independent original branch capture; original algorithms with preset accessor. Source/CPU flags plus RGB output validation; not GPU capture of each draw.')
    DOC.mkdir(parents=True,exist_ok=True)
    (DOC/f'{a.scene}-capture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (DOC/f'{a.scene}-frames.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(dict(scene=a.scene,static=static,old_native_mismatches=len(old_native_mismatches),spatial_changed=result['spatial_aa_changed_pixels']),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
