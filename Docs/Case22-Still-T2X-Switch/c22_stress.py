# Object-motion stress scene: case 4, selected route, case 19, case 22 against the supersample reference.
# ROIs are the fractions of the July stress analyzer (analyze_temporal_stress_quality.py) at 1920x1061.
import json,math,sys,re,glob,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
CAP=Path(sys.argv[1]);AUTOBENCH=Path(sys.argv[2]);OUT=Path(sys.argv[3]);SHEETS=Path(sys.argv[4]);SHEETS.mkdir(parents=True,exist_ok=True)
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
MODES={'4':'O-T2X-R','sel':SEL,'19':SEL+'+VelocityInEdge','22':'SWITCH-StillO-T2X-R-N4+MovingSelected','ref':'SS-Reference'}
W,H=1920,1061
FR={'occluder_path':(0.30,0.45,0.70,0.73),'rotor':(0.30,0.24,0.46,0.48)}
ROIS={k:(round(a*W),round(b*H),round(c*W),round(d*H)) for k,(a,b,c,d) in FR.items()}
def rgb(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(W,H),(str(p),im.mode,im.size);return np.asarray(im).copy()
cap=[p for p in (CAP/'object-motion').iterdir() if p.is_dir()];assert len(cap)==1;cap=cap[0]
for m in MODES.values():assert len(list((cap/m).glob('frame_*.png')))==240,m
route={}
for rp in glob.glob(str(AUTOBENCH/'**/*_results.csv'),recursive=True):
    t=Path(rp).read_text(encoding='utf-8-sig')
    if cap.name not in t:continue
    for m in re.finditer(r'^mode_check,\s*'+re.escape(MODES['22'])+r',\s*(\d+),\s*[-\d.]+,\s*[-\d.]+,\s*(native|selected),\s*(PASS|FAIL)',t,re.M):route[int(m.group(1))]=(m.group(2),m.group(3))
assert len(route)==240,len(route)
segs=[]
for f in range(240):
    r=route[f][0]
    if segs and segs[-1][0]==r:segs[-1][2]=f
    else:segs.append([r,f,f])
res={'capture':str(cap),'rois':ROIS,'route_segments_22':segs,'route_checks_pass':all(v[1]=='PASS' for v in route.values()),'modes':{},'identical_22_vs_4':[]}
roi={k:{n:[] for n in ROIS} for k in MODES if k!='ref'};full={k:[] for k in roi};temporal={k:{n:[] for n in ROIS} for k in roi};prev={}
for f in range(240):
    ref=rgb(cap/MODES['ref']/f'frame_{f:05d}.png').astype(np.float32);imgs={}
    for k in roi:
        a=rgb(cap/MODES[k]/f'frame_{f:05d}.png');imgs[k]=a;d=a.astype(np.float32)-ref;mse=float((d*d).mean())
        full[k].append(dict(frame=f,mae=float(np.abs(d).mean()),psnr=10*math.log10(255**2/mse) if mse>0 else 99))
        for n,(x0,y0,x1,y1) in ROIS.items():
            roi[k][n].append(float(np.abs(d[y0:y1,x0:x1]).mean()))
            if k in prev:temporal[k][n].append(float(np.abs(a[y0:y1,x0:x1].astype(np.float32)-prev[k][y0:y1,x0:x1]).mean()))
        prev[k]=a.astype(np.float32)
    if (imgs['22']==imgs['4']).all():res['identical_22_vs_4'].append(f)
    if f%40==0:print('frame',f,flush=True)
rng=[]
for f in res['identical_22_vs_4']:
    if rng and rng[-1][1]==f-1:rng[-1][1]=f
    else:rng.append([f,f])
res['identical_22_vs_4']=rng
for k in roi:
    res['modes'][k]={'full_mae':float(np.mean([x['mae'] for x in full[k][6:]])),'full_psnr':float(np.mean([x['psnr'] for x in full[k][6:]])),
        'roi_reference_mae':{n:float(np.mean(roi[k][n][6:])) for n in ROIS},'roi_adjacent_mae':{n:float(np.mean(temporal[k][n][6:])) for n in ROIS},
        'per_frame_full':full[k]}
OUT.write_text(json.dumps(res,indent=1),encoding='utf-8')
print('route',segs,'checks',res['route_checks_pass']);print('22 identical to 4',rng)
for k,v in res['modes'].items():print(k,'full MAE %.4f PSNR %.3f'%(v['full_mae'],v['full_psnr']),'ROI ref MAE',{n:round(x,4) for n,x in v['roi_reference_mae'].items()},'adjacent',{n:round(x,4) for n,x in v['roi_adjacent_mae'].items()})
# Sheets: rotor and occluder, consecutive frames, nearest zoom.
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',15)
def sheet(name,box,frames,z,title):
    w,h=(box[2]-box[0])*z,(box[3]-box[1])*z;rows=[('④','4'),('선택 경로','sel'),('22번','22'),('기준 영상','ref')];left=90
    S=Image.new('RGB',(left+len(frames)*(w+5),28+len(rows)*(h+20)),(20,20,20));D=ImageDraw.Draw(S);D.text((6,4),title,fill=(255,255,255),font=font)
    for i,(lab,k) in enumerate(rows):
        y=28+i*(h+20);D.text((4,y+24),lab,fill=(255,255,255),font=font)
        for j,f in enumerate(frames):
            S.paste(Image.open(cap/MODES[k]/f'frame_{f:05d}.png').convert('RGB').crop(box).resize((w,h),Image.NEAREST),(left+j*(w+5),y+20))
            if i==0:D.text((left+j*(w+5),y+1),f'f{f}',fill=(220,220,220),font=font)
    p=SHEETS/f'{name}.png';S.save(p);print(p,S.size)
sheet('stress-rotor-f100-105',ROIS['rotor'],list(range(100,106)),1,f'object-motion 회전 날개 {ROIS["rotor"]}, f100-105, 1배')
sheet('stress-occluder-f100-105',ROIS['occluder_path'],list(range(100,106)),1,f'object-motion 가림판 경로 {ROIS["occluder_path"]}, f100-105, 1배')
sheet('stress-start-rotor-f2-7',ROIS['rotor'],list(range(2,8)),1,f'object-motion 회전 날개, f2-7 (22번은 f5부터 ④), 1배')
full=Image.new('RGB',(2*960+6,2*531+60),(20,20,20));D=ImageDraw.Draw(full)
for i,(lab,k) in enumerate((('④','4'),('선택 경로','sel'),('22번','22'),('기준 영상','ref'))):
    x=(i%2)*966;y=30+(i//2)*561;full.paste(Image.open(cap/MODES[k]/'frame_00100.png').convert('RGB').resize((960,531),Image.LANCZOS),(x,y));D.text((x+4,y-26),f'{lab} f100 (1/2 축소)',fill=(255,255,255),font=font)
full.save(SHEETS/'stress-full-f100.png');print(SHEETS/'stress-full-f100.png')
