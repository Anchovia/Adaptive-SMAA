# Eight cases (+ case 19/21) on the selected-temporal routes: R-on regression against the Adaptive
# branch capture, R-off vs R-on identity on still frames, supersample-reference PSNR/SSIM/MAE.
import json,math,sys,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.append('C:/Users/USER/Desktop/research/.research-tools/quality-venv/Lib/site-packages')
import cv2
CAP=Path(sys.argv[1]);REF=Path(sys.argv[2]);BASE=Path(sys.argv[3]);OUT=Path(sys.argv[4])
SEL='ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
SELOFF=SEL.replace('ET2X-R-','ET2X-')
MODES={'O-T2X-R':'O-T2X-R','O-ET2X-R':'ABL-'+SEL,'19':'ABL-'+SEL+'+VelocityInEdge','A-T2X-R':'A-T2X-R','A-ET2X-R':'A-ABL-'+SEL,'21':'A-ABL-'+SEL+'+VelocityInEdge',
       'O-T2X':'O-T2X','O-ET2X':'ABL-'+SELOFF,'A-T2X':'A-T2X','A-ET2X':'A-ABL-'+SELOFF}
RON=['O-T2X-R','O-ET2X-R','19','A-T2X-R','A-ET2X-R','21']
PAIRS=[('O-T2X','O-T2X-R'),('O-ET2X','O-ET2X-R'),('A-T2X','A-T2X-R'),('A-ET2X','A-ET2X-R')]
ROIS={'bistro':{'thin-chair':(1230,582,1358,670)},'minecraft':{'thin-seam':(956,524,1020,620)}}
LUMA=np.array([.2126,.7152,.0722],np.float32)
def rgb(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(str(p),im.mode,im.size);return np.asarray(im).copy()
def gray(a):return a.astype(np.float32)@LUMA
blur=lambda x:cv2.GaussianBlur(x,(11,11),1.5)[5:-5,5:-5]
def ssim_ref(b):b=gray(b);mb=blur(b);return b,mb,blur(b*b)-mb*mb
def ssim(a,r):
    a=gray(a);b,mb,vb=r;ma=blur(a);va=blur(a*a)-ma*ma;cov=blur(a*b)-ma*mb
    return float(np.mean(((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225))))
def phase(f):return 'moving' if 60<=f<180 else 'transition' if 180<=f<210 else 'settled' if f>=220 else 'late-settling' if f>=210 else 'initial'
def one(d):
    x=[p for p in Path(d).iterdir() if p.is_dir()];assert len(x)==1,(d,x);return x[0]
def ranges(lst):
    r=[]
    for f in lst:
        if r and r[-1][1]==f-1:r[-1][1]=f
        else:r.append([f,f])
    return r
res={}
for scene in ('bistro','minecraft'):
    cap=one(CAP/scene);ref=one(REF/scene)/'SS-Reference';base=one(BASE/scene)
    for m in MODES.values():assert len(list((cap/m).glob('frame_*.png')))==240,(scene,m)
    out={'capture':str(cap),'reference':str(ref),'baseline_capture':str(base),'regression':{},'off_equals_on':{},'modes':{}}
    for k in RON:
        mism=[f for f in range(240) if hashlib.sha256(rgb(cap/MODES[k]/f'frame_{f:05d}.png').tobytes()).digest()!=hashlib.sha256(rgb(base/MODES[k]/f'frame_{f:05d}.png').tobytes()).digest()]
        out['regression'][k]={'frames':240,'mismatched_frames':len(mism),'first':mism[:5]}
    per={k:[] for k in MODES};roi={k:{n:[] for n in ROIS[scene]} for k in MODES};hashes={k:[] for k in MODES};same={p:[] for p,_ in PAIRS}
    for f in range(240):
        r=rgb(ref/f'frame_{f:05d}.png');rs=ssim_ref(r);rf=r.astype(np.float32);imgs={}
        for k,m in MODES.items():
            a=rgb(cap/m/f'frame_{f:05d}.png');imgs[k]=a;hashes[k].append(hashlib.sha256(a.tobytes()).hexdigest())
            d=a.astype(np.float32)-rf;mse=float(np.mean(d*d))
            per[k].append(dict(frame=f,phase=phase(f),reference_mae=float(np.abs(d).mean()),psnr=99 if mse==0 else 10*math.log10(255**2/mse),luma_ssim=ssim(a,rs)))
            for n,(x0,y0,x1,y1) in ROIS[scene].items():roi[k][n].append(float(np.abs(d[y0:y1,x0:x1]).mean()))
        for off,on in PAIRS:
            if (imgs[off]==imgs[on]).all():same[off].append(f)
        if f%40==0:print(scene,f,flush=True)
    out['off_equals_on']={f'{off} vs {on}':ranges(same[off]) for off,on in PAIRS}
    for k in MODES:
        o={}
        for ph in ('moving','transition','settled'):
            sel=[x for x in per[k] if x['phase']==ph];idx=[x['frame'] for x in sel]
            o[ph]={q:float(np.mean([x[q] for x in sel])) for q in ('reference_mae','psnr','luma_ssim')}
            o[ph]['roi_mae']={n:float(np.mean([roi[k][n][i] for i in idx])) for n in ROIS[scene]}
        o['settled_distinct_frame_hashes']=len(set(hashes[k][220:240]))
        o['per_frame_psnr']=[round(x['psnr'],4) for x in per[k]]
        out['modes'][k]=o
    res[scene]=out
OUT.write_text(json.dumps(res,indent=1),encoding='utf-8')
for scene,o in res.items():
    print('==',scene,'regression',{k:v['mismatched_frames'] for k,v in o['regression'].items()})
    print('  off==on',o['off_equals_on'])
    for k,v in o['modes'].items():
        print(f"  {k:>9}",' | '.join(f"{ph} PSNR {v[ph]['psnr']:.3f} SSIM {v[ph]['luma_ssim']:.5f} MAE {v[ph]['reference_mae']:.4f} roi {list(v[ph]['roi_mae'].values())[0]:.3f}" for ph in ('moving','transition','settled')),'hashes',v['settled_distinct_frame_hashes'])
