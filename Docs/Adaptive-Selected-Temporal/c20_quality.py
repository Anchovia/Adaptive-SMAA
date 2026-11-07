# Frame-aligned spatial-reference quality for cases 20/21 next to case 4, the selected route and case 19.
# PSNR / luma SSIM / RGB MAE use the same formulas and phases as the 1-17 remeasurement
# (analyze_all_case_remeasurement.py). The reference is a supersample spatial proxy, not temporal ground truth.
import json,math,sys,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.append('C:/Users/USER/Desktop/research/.research-tools/quality-venv/Lib/site-packages')
import cv2

CAP=Path(sys.argv[1]);REF=Path(sys.argv[2]);OUT=Path(sys.argv[3])
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
MODES={'4':'O-T2X-R','sel':SEL,'19':SEL+'+VelocityInEdge','A4':'A-T2X-R','20':'A-'+SEL,'21':'A-'+SEL+'+VelocityInEdge'}
ROIS={'bistro':{'thin-chair':(1230,582,1358,670),'windows':(950,460,1110,588)},
 'minecraft':{'thin-seam':(956,524,1020,620),'leaves':(1420,590,1580,718),'grass-seam':(1450,665,1552,719)}}
LUMA=np.array([.2126,.7152,.0722],np.float32)
def rgb(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(str(p),im.mode,im.size)
        return np.asarray(im).copy()
def gray(a):return a.astype(np.float32)@LUMA
blur=lambda x:cv2.GaussianBlur(x,(11,11),1.5)[5:-5,5:-5]
def ssim_reference(b):
    b=gray(b);mb=blur(b);vb=blur(b*b)-mb*mb;return b,mb,vb
def ssim(a,r):
    a=gray(a);b,mb,vb=r;ma=blur(a);va=blur(a*a)-ma*ma;cov=blur(a*b)-ma*mb
    return float(np.mean(((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225))))
def phase(f):return 'moving' if 60<=f<180 else 'transition' if 180<=f<210 else 'settled' if f>=220 else 'late-settling' if f>=210 else 'initial'

res={}
for scene in ('bistro','minecraft'):
    caps=[d for d in (CAP/scene).iterdir() if d.is_dir()];assert len(caps)==1,caps;cap=caps[0]
    refs=[d for d in (REF/scene).iterdir() if d.is_dir()];assert len(refs)==1,refs;ref=refs[0]/'SS-Reference'
    assert len(list(ref.glob('frame_*.png')))==240,ref
    for m in MODES.values():assert len(list((cap/m).glob('frame_*.png')))==240,(scene,m)
    rows={k:[] for k in MODES};roi={k:{r:[] for r in ROIS[scene]} for k in MODES};hashes={k:[] for k in MODES}
    for f in range(240):
        r=rgb(ref/f'frame_{f:05d}.png');rs=ssim_reference(r);rf=r.astype(np.float32)
        for k,m in MODES.items():
            a=rgb(cap/m/f'frame_{f:05d}.png');hashes[k].append(hashlib.sha256(a.tobytes()).hexdigest())
            d=a.astype(np.float32)-rf;mse=float(np.mean(d*d))
            rows[k].append(dict(frame=f,phase=phase(f),reference_mae=float(np.abs(d).mean()),psnr=99 if mse==0 else 10*math.log10(255**2/mse),luma_ssim=ssim(a,rs)))
            for name,(x0,y0,x1,y1) in ROIS[scene].items():
                roi[k][name].append(dict(frame=f,phase=phase(f),mae=float(np.abs(d[y0:y1,x0:x1]).mean())))
        if f%40==0:print(scene,f,flush=True)
    out={'capture':str(cap),'reference':str(ref),'modes':{}}
    for k in MODES:
        o={}
        for ph in ('moving','transition','settled'):
            sel=[x for x in rows[k] if x['phase']==ph]
            o[ph]={q:float(np.mean([x[q] for x in sel])) for q in ('reference_mae','psnr','luma_ssim')}
            o[ph]['roi_mae']={n:float(np.mean([x['mae'] for x in roi[k][n] if x['phase']==ph])) for n in ROIS[scene]}
        o['settled_distinct_frame_hashes']=len(set(hashes[k][220:240]))
        o['per_frame']=rows[k]
        out['modes'][k]=o
    res[scene]=out
OUT.write_text(json.dumps(res,indent=1),encoding='utf-8')
for scene,o in res.items():
    print('==',scene)
    for k,v in o['modes'].items():
        print(f"{k:>3}",' | '.join(f"{ph} PSNR {v[ph]['psnr']:.3f} SSIM {v[ph]['luma_ssim']:.5f} MAE {v[ph]['reference_mae']:.4f}" for ph in ('moving','transition','settled')),'hashes',v['settled_distinct_frame_hashes'])
        print('    ROI',' | '.join(f"{ph}: "+', '.join(f"{n} {x:.3f}" for n,x in v[ph]['roi_mae'].items()) for ph in ('moving','transition')))
