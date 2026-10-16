"""Compare case-17/native-4 RGB captures between labelled clean runs.

Hashes decoded RGB arrays (PNG has no alpha) exactly as the earlier
analyzers did, bridges to recorded per-frame hashes, and reports the location
and magnitude of any mismatch. Equal hashes mean identical 8-bit RGB output;
this says nothing about quality.
"""
import argparse,os,hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
# Receipts from this worktree plus any extra files listed in COLOR_BLEND_RUNS (os.pathsep separated).
RUNS=[ROOT/'tmp/color-blend-preservation-runs.json']+[Path(x) for x in os.environ.get('COLOR_BLEND_RUNS','').split(os.pathsep) if x]
CASE17='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend'
NATIVE='O-T2X-R'
MODES=[CASE17,NATIVE]

def runs():
    seen={}
    for p in RUNS:
        if p.exists():
            for r in json.loads(p.read_text(encoding='utf-8-sig')):seen[r['report']]=r
    return list(seen.values())
def receipt(label,scene,phase):
    r=[x for x in runs() if x['label']==label and x['scene']==scene and x['phase']==phase]
    assert len(r)==1,(label,scene,phase,len(r))
    r=r[0];report=Path(r['report'])
    assert hashlib.sha256(report.read_bytes()).hexdigest().upper()==r['report_sha256']
    text=report.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and ',FAIL' not in text.replace(' ','')
    return r,text
def rgb(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(p,im.mode,im.size)
        return np.asarray(im).copy()
def phase_rows(text):
    rows={}
    for m in re.finditer(r'^mode_check,\s*([^,]+),\s*(\d+),\s*([-\d.]+),\s*([-\d.]+),\s*(\w+)',text,re.M):
        rows[(m.group(1).strip(),int(m.group(2)))]=(float(m.group(3)),float(m.group(4)),m.group(5))
    return rows
def hashes(label,scene,phase='Capture'):
    r,text=receipt(label,scene,phase);root=Path(r['capture_root']);out={}
    checks=phase_rows(text)
    for mode in MODES:
        files=sorted((root/mode).glob('frame_?????.png'))
        assert [int(p.stem[6:]) for p in files]==list(range(240)),(label,scene,mode,len(files))
        out[mode]=[hashlib.sha256(rgb(p).tobytes()).hexdigest() for p in files]
        assert all(checks[(mode,f)][2]=='PASS' for f in range(240)),(label,scene,mode)
    # Start phase: native T2X jitter at f0 must be the frame-index-0 offset after reset.
    start=checks[(NATIVE,0)][:2];case17=checks[(CASE17,0)][:2]
    return r,root,out,dict(native_f0_jitter=start,case17_f0_jitter=case17)
def compare(label_a,label_b,scene):
    ra,root_a,ha,pa=hashes(label_a,scene);rb,root_b,hb,pb=hashes(label_b,scene);result=[]
    for mode in MODES:
        bad=[f for f in range(240) if ha[mode][f]!=hb[mode][f]];detail=[]
        for f in bad[:20]:
            a=rgb(root_a/mode/f'frame_{f:05d}.png').astype(np.int16);b=rgb(root_b/mode/f'frame_{f:05d}.png').astype(np.int16)
            d=np.abs(a-b);ys,xs=np.nonzero(d.max(axis=2))
            detail.append(dict(frame=f,changed_pixels=int(len(xs)),max_channel_error=int(d.max()),bbox=[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]))
        result.append(dict(mode=mode,frames=240,mismatch_frames=len(bad),first_mismatch=detail))
    return dict(scene=scene,a=label_a,b=label_b,a_executable=ra['executable_sha256'],b_executable=rb['executable_sha256'],
        a_start_phase=pa,b_start_phase=pb,modes=result,validation='PASS' if all(m['mismatch_frames']==0 for m in result) else 'MISMATCH')
def bridge(label,scene,record):
    _,_,h,_=hashes(label,scene);doc=json.loads(Path(record).read_text(encoding='utf-8'))
    recorded=doc['rgb_hashes'];out=[]
    for mode in MODES:
        bad=[f for f in range(240) if h[mode][f]!=recorded[mode][f]]
        out.append(dict(mode=mode,frames=240,mismatch_frames=len(bad),first=bad[:10]))
    return dict(scene=scene,label=label,record=str(record),record_sha256=hashlib.sha256(Path(record).read_bytes()).hexdigest(),modes=out,
        validation='PASS' if all(m['mismatch_frames']==0 for m in out) else 'MISMATCH')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['compare','bridge']);ap.add_argument('a');ap.add_argument('b')
    ap.add_argument('--scene',required=True);ap.add_argument('--out')
    x=ap.parse_args()
    res=compare(x.a,x.b,x.scene) if x.kind=='compare' else bridge(x.a,x.scene,x.b)
    txt=json.dumps(res,indent=2);print(txt)
    if x.out:Path(x.out).parent.mkdir(parents=True,exist_ok=True);Path(x.out).write_text(txt+'\n',encoding='utf-8')
