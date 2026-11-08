# Decoded-RGB comparison of two case 22 capture roots (all four modes, 240 frames, both scenes).
import sys,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
A,B,OUT=Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3])
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
MODES=['O-T2X-R',SEL,SEL+'+VelocityInEdge','SWITCH-StillO-T2X-R-N4+MovingSelected']
def one(d):
    x=[p for p in Path(d).iterdir() if p.is_dir()];assert len(x)==1,(d,x);return x[0]
def h(p):
    with Image.open(p) as im:
        assert im.size==(1920,1061);return hashlib.sha256(np.asarray(im.convert('RGB')).tobytes()).hexdigest()
res={'a':str(A),'b':str(B)}
for s in ('bistro','minecraft'):
    a,b=one(A/s),one(B/s);res[s]={}
    for m in MODES:
        mism=[f for f in range(240) if h(a/m/f'frame_{f:05d}.png')!=h(b/m/f'frame_{f:05d}.png')]
        res[s][m]={'frames':240,'mismatched_frames':len(mism),'first':mism[:5]}
        print(s,m[-40:],len(mism))
res['validation']='PASS' if all(v['mismatched_frames']==0 for s in ('bistro','minecraft') for v in res[s].values()) else 'FAIL'
OUT.write_text(json.dumps(res,indent=1),encoding='utf-8');print(res['validation'])
