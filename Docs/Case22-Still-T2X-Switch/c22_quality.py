# Case 22 next to case 4, the selected route and case 19: route timeline, RGB regression,
# supersample-reference PSNR/SSIM/MAE (same formulas and phases as the 1-17 remeasurement).
import json,math,sys,hashlib,re,glob
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.append('C:/Users/USER/Desktop/research/.research-tools/quality-venv/Lib/site-packages')
import cv2

CAP=Path(sys.argv[1]);REF=Path(sys.argv[2]);BASE=Path(sys.argv[3]);OUT=Path(sys.argv[4])
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
MODES={'4':'O-T2X-R','sel':SEL,'19':SEL+'+VelocityInEdge','22':'SWITCH-StillO-T2X-R-N4+MovingSelected'}
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
def one(d):
    x=[p for p in Path(d).iterdir() if p.is_dir()];assert len(x)==1,(d,x);return x[0]

res={}
for scene in ('bistro','minecraft'):
    cap=one(CAP/scene);ref=one(REF/scene)/'SS-Reference';base=one(BASE/scene)
    for m in MODES.values():assert len(list((cap/m).glob('frame_*.png')))==240,(scene,m)
    # Route actually drawn per frame for case 22, from the capture report rows.
    rows=[r for r in glob.glob(str(Path(sys.argv[5])/'**/*_results.csv'),recursive=True)]
    route={}
    for rp in rows:
        t=Path(rp).read_text(encoding='utf-8-sig')
        if str(cap).replace('\\','/').split('/')[-1] not in t.replace('\\','/'):continue
        for m in re.finditer(r'^mode_check,\s*'+re.escape(MODES['22'])+r',\s*(\d+),\s*([-\d.]+),\s*([-\d.]+),\s*(native|selected),\s*(PASS|FAIL)',t,re.M):
            route[int(m.group(1))]=(m.group(4),float(m.group(2)),float(m.group(3)),m.group(5))
    assert len(route)==240,(scene,len(route))
    segs=[];prev=None
    for f in range(240):
        r=route[f][0]
        if r!=prev:segs.append([r,f,f]);prev=r
        else:segs[-1][2]=f
    out={'capture':str(cap),'reference':str(ref),'baseline_capture':str(base),'route_segments':segs,
         'route_checks_pass':all(v[3]=='PASS' for v in route.values()),'regression':{},'modes':{},'case22_vs':{}}
    # Original modes must match the baseline capture.
    for k in ('4','sel','19'):
        mism=[f for f in range(240) if hashlib.sha256(rgb(cap/MODES[k]/f'frame_{f:05d}.png').tobytes()).digest()!=hashlib.sha256(rgb(base/MODES[k]/f'frame_{f:05d}.png').tobytes()).digest()]
        out['regression'][k]={'frames':240,'mismatched_frames':len(mism),'first':mism[:5]}
    per={k:[] for k in MODES};roi={k:{n:[] for n in ROIS[scene]} for k in MODES};hashes={k:[] for k in MODES};vs={'4':[],'sel':[]}
    for f in range(240):
        r=rgb(ref/f'frame_{f:05d}.png');rs=ssim_reference(r);rf=r.astype(np.float32);imgs={}
        for k,m in MODES.items():
            a=rgb(cap/m/f'frame_{f:05d}.png');imgs[k]=a;hashes[k].append(hashlib.sha256(a.tobytes()).hexdigest())
            d=a.astype(np.float32)-rf;mse=float(np.mean(d*d))
            per[k].append(dict(frame=f,phase=phase(f),reference_mae=float(np.abs(d).mean()),psnr=99 if mse==0 else 10*math.log10(255**2/mse),luma_ssim=ssim(a,rs)))
            for n,(x0,y0,x1,y1) in ROIS[scene].items():roi[k][n].append(float(np.abs(d[y0:y1,x0:x1]).mean()))
        for c in ('4','sel'):
            e=np.abs(imgs['22'].astype(int)-imgs[c].astype(int)).max(2)
            vs[c].append(dict(frame=f,identical=bool((e==0).all()),changed_pct=float((e>0).mean()*100),max=int(e.max())))
        if f%40==0:print(scene,f,flush=True)
    for k in MODES:
        o={}
        for ph in ('moving','transition','settled'):
            sel=[x for x in per[k] if x['phase']==ph]
            o[ph]={q:float(np.mean([x[q] for x in sel])) for q in ('reference_mae','psnr','luma_ssim')}
            idx=[x['frame'] for x in sel]
            o[ph]['roi_mae']={n:float(np.mean([roi[k][n][i] for i in idx])) for n in ROIS[scene]}
        o['settled_distinct_frame_hashes']=len(set(hashes[k][220:240]))
        o['per_frame']=per[k];o['roi_per_frame']=roi[k]
        out['modes'][k]=o
    out['case22_vs']=vs
    res[scene]=out
OUT.write_text(json.dumps(res,indent=1),encoding='utf-8')
for scene,o in res.items():
    print('==',scene,'route segments',o['route_segments'],'checks',o['route_checks_pass'])
    print('  regression',{k:v['mismatched_frames'] for k,v in o['regression'].items()})
    for k,v in o['modes'].items():
        print(f"  {k:>3}",' | '.join(f"{ph} PSNR {v[ph]['psnr']:.3f} SSIM {v[ph]['luma_ssim']:.5f} MAE {v[ph]['reference_mae']:.4f}" for ph in ('moving','transition','settled')),'hashes',v['settled_distinct_frame_hashes'])
    for c in ('4','sel'):
        same=[x['frame'] for x in o['case22_vs'][c] if x['identical']]
        rng=[]
        for f in same:
            if rng and rng[-1][1]==f-1:rng[-1][1]=f
            else:rng.append([f,f])
        print(f'  22 identical to {c}: {len(same)} frames, ranges {rng}')
