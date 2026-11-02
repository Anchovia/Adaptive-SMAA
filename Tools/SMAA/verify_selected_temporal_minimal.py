"""Compares a capture of the minimal branch with the pre-cleanup capture of the same modes.

Decoded RGB of every frame must match. Usage:
  verify_selected_temporal_minimal.py <new capture root> <pre-cleanup capture root> --out result.json
Each root holds <scene>/<run>/<mode>/frame_NNNNN.png.
"""
import argparse,json,os
import numpy as np
from PIL import Image

BASE='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory'
MODES=['O-T2X-R',BASE+'+NoVelocityAlpha',BASE+'+NoVelocityAlpha+VelocityInEdge']
FRAMES=240

def run_dir(root,scene):
    base=os.path.join(root,scene);runs=sorted(os.listdir(base))
    assert runs,base
    return os.path.join(base,runs[-1])
def rgb(path):
    return np.array(Image.open(path).convert('RGB')).astype(np.int16)
def compare(new,old):
    rows=[]
    for mode in MODES:
        bad=[]
        for f in range(FRAMES):
            name=f'frame_{f:05d}.png';a=rgb(os.path.join(new,mode,name));b=rgb(os.path.join(old,mode,name))
            if a.shape!=b.shape:raise ValueError(f'{mode} {name}: size {a.shape} vs {b.shape}')
            d=np.abs(a-b).max(2)
            if d.any():bad.append(dict(frame=f,pixels=int((d>0).sum()),max=int(d.max())))
        rows.append(dict(mode=mode,frames=FRAMES,mismatched_frames=len(bad),first=bad[:5]))
    return rows
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('new');ap.add_argument('old');ap.add_argument('--out');x=ap.parse_args()
    res={}
    for scene in ('bistro','minecraft'):
        res[scene]=compare(run_dir(x.new,scene),run_dir(x.old,scene))
        for r in res[scene]:print(scene,r['mode'][-32:],'mismatched',r['mismatched_frames'],r['first'][:2])
    res['validation']='PASS' if all(r['mismatched_frames']==0 for s in ('bistro','minecraft') for r in res[s]) else 'MISMATCH'
    print(res['validation'])
    if x.out:
        os.makedirs(os.path.dirname(x.out),exist_ok=True)
        json.dump(res,open(x.out,'w',encoding='utf-8'),indent=1)
