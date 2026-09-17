"""Aligned SS-reference quality, exact selection counts, and native hash bridge."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

MODES = ('O-T2X-R','ABL-Contrast-0005-R','ABL-Contrast-001-R','ABL-Contrast-002-R')
MASKS = dict(zip(MODES[1:], ('DBG-ContrastMask-0005-R','DBG-ContrastMask-001-R','DBG-ContrastMask-002-R')))
WINDOWS = {'all':(0,240),'moving':(60,180),'transition':(160,220),'late_still':(200,240)}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rgb(path):
    with Image.open(path) as im:
        a=np.asarray(im.convert('RGB'))
    assert a.shape==(1061,1920,3), (path,a.shape)
    return a

def luma(a):
    a=a.astype(np.float32)
    return a[:,:,0]*.2126+a[:,:,1]*.7152+a[:,:,2]*.0722

def blur(a):
    x=np.arange(-5,6,dtype=np.float32);k=np.exp(-x*x/4.5);k/=k.sum()
    p=np.pad(a,((0,0),(5,5)),mode='reflect');h=np.zeros_like(a)
    for i,w in enumerate(k):h+=p[:,i:i+a.shape[1]]*w
    p=np.pad(h,((5,5),(0,0)),mode='reflect');v=np.zeros_like(a)
    for i,w in enumerate(k):v+=p[i:i+a.shape[0]]*w
    return v

def ssim(a,b,mb,vb):
    ma=blur(a);va=blur(a*a)-ma*ma;cov=blur(a*b)-ma*mb
    values=((2*ma*mb+6.5025)*(2*cov+58.5225))/np.maximum((ma*ma+mb*mb+6.5025)*(va+vb+58.5225),1e-12)
    return float(values[5:-5,5:-5].mean(dtype=np.float64))

def edge(a):
    p=np.pad(a,1,mode='reflect')
    gx=-p[:-2,:-2]+p[:-2,2:]-2*p[1:-1,:-2]+2*p[1:-1,2:]-p[2:,:-2]+p[2:,2:]
    gy=-p[:-2,:-2]-2*p[:-2,1:-1]-p[:-2,2:]+p[2:,:-2]+2*p[2:,1:-1]+p[2:,2:]
    return float(np.hypot(gx,gy).mean(dtype=np.float64))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',required=True,choices=('bistro','minecraft'))
    p.add_argument('--capture',required=True,type=Path)
    p.add_argument('--quality-capture',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--expected-frames',type=int,default=240)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    n=a.expected_frames;expected=[f'frame_{i:05d}.png' for i in range(n)]
    dirs=[a.quality_capture/d for d in ('O-T2X-R',*MASKS.values(),'SS-Reference')]
    for d in dirs:assert [f.name for f in sorted(d.glob('*.png'))]==expected,d
    reports=list(a.quality_capture.glob('*_results.csv'));assert len(reports)==1
    report=reports[0].read_text(encoding='utf-8-sig')
    for token in ('Aggregate: PASS',f'Scene: {a.scene}','1920 x 1061',f'Frames: {n}',
                  '2x linear resolution, 3x3 within-frame grid, 8x MSAA'):
        assert token in report,token
    bridge=0
    for name in ('O-T2X-R','DBG-ContrastMask-001-R'):
        for f in expected:
            assert sha(a.quality_capture/name/f)==sha(a.capture/name/f),(name,f)
            bridge+=1
    print(f'PASS {a.scene}: exact native/mask bridge {bridge} frames',flush=True)
    rows=[];coverage=[];prev={};previous_ref=None;previous_ref_rgb=None;pixel_hashes={};ref_hashes=[];semantics=0;ref_steps=[]
    for i,f in enumerate(expected):
        ref=rgb(a.quality_capture/'SS-Reference'/f);r=luma(ref);er=edge(r)
        # SSIM is the secondary sampled spatial metric; MAE/PSNR and temporal
        # change still cover every frame, as do selection checks and CGVQM clips.
        do_ssim=i%10==0
        if do_ssim:mr=blur(r);vr=blur(r*r)-mr*mr
        ref_hashes.append(sha(a.quality_capture/'SS-Reference'/f))
        if i>=200:
            delta=np.abs(ref.astype(np.int16)-previous_ref_rgb.astype(np.int16))
            ref_steps.append({'max_rgb_step':int(delta.max()),'changed_channels':int(np.count_nonzero(delta)),
                              'mean_rgb_step':float(delta.mean(dtype=np.float64))})
        masks={m:rgb(a.quality_capture/name/f) for m,name in MASKS.items()}
        for m,mask in masks.items():
            assert np.all((mask==0)|(mask==255)) and np.all(mask==mask[:,:,0,None])
            masks[m]=mask[:,:,0]==255
        assert not np.any(masks[MODES[3]] & ~masks[MODES[2]])
        assert not np.any(masks[MODES[2]] & ~masks[MODES[1]])
        native=rgb(a.capture/MODES[0]/f);spatial=rgb(a.capture/'DBG-CurrentSpatial-R'/f)
        images={MODES[0]:native}
        for m in MODES:
            path=a.capture/m/f
            t=native if m==MODES[0] else rgb(path);images[m]=t;y=luma(t)
            pixel_hashes.setdefault(m,hashlib.sha256()).update(t.tobytes())
            if m in masks:
                selected=masks[m];count=int(np.count_nonzero(selected))
                assert not np.any(np.any(t!=native,axis=2) & selected),(i,m,'selected')
                assert not np.any(np.any(t!=spatial,axis=2) & ~selected),(i,m,'bypassed')
                semantics+=1
            else:count=t.shape[0]*t.shape[1]
            coverage.append({'frame':i,'mode':m,'selected_pixels':count,'total_pixels':1920*1061,
                             'selected_percent':100*count/(1920*1061)})
            d=t.astype(np.float32)-ref.astype(np.float32);mse=float(np.square(d).mean(dtype=np.float64))
            row={'frame':i,'mode':m,'rgb_mae':float(np.abs(d).mean(dtype=np.float64)),
                 'rgb_psnr_db':10*math.log10(255**2/mse) if mse else None,'luma_ssim':ssim(y,r,mr,vr) if do_ssim else None,
                 'edge_reference_ratio':edge(y)/er if er else None,
                 'luma_delta1':float(np.abs(y-prev[m]).mean(dtype=np.float64)) if m in prev else None,
                 'reference_delta_residual':float(np.abs((y-prev[m])-(r-previous_ref)).mean(dtype=np.float64)) if m in prev else None}
            rows.append(row);prev[m]=y
        previous_ref=r;previous_ref_rgb=ref
        if i in (90,179,200,201):
            names=['SS-Reference',*MODES];ims=[ref,*[images[m] for m in MODES]]
            sheet=Image.new('RGB',(1800,448),'#15181c');draw=ImageDraw.Draw(sheet)
            for col,(name,im) in enumerate(zip(names,ims)):
                sheet.paste(Image.fromarray(im).resize((360,199)),(360*col,24))
                diff=np.clip(np.abs(im.astype(np.int16)-ref)*4,0,255).astype(np.uint8)
                sheet.paste(Image.fromarray(diff).resize((360,199)),(360*col,249))
                draw.text((360*col+4,5),name,fill='white');draw.text((360*col+4,230),'reference difference x4',fill='white')
            sheet.save(a.output/f'reference-frame-{i:03d}.png')
        if i%30==29:print(f'{a.scene}: {i+1}/{n}',flush=True)
    for filename,data in [('per-frame-reference.csv',rows),('per-frame-coverage.csv',coverage)]:
        with (a.output/filename).open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=data[0]);w.writeheader();w.writerows(data)
    summary={};counts={}
    for window,(start,end) in WINDOWS.items():
        if end>n:continue
        summary[window]={};counts[window]={}
        for m in MODES:
            selected=[x for x in rows if x['mode']==m and start<=x['frame']<end]
            summary[window][m]={k:float(np.mean([x[k] for x in selected if x[k] is not None])) for k in rows[0] if k not in ('frame','mode')}
            c=[x['selected_pixels'] for x in coverage if x['mode']==m and start<=x['frame']<end]
            counts[window][m]={'mean_pixels':float(np.mean(c)),'min_pixels':min(c),'max_pixels':max(c),
                'total_pixels':1920*1061,'mean_percent':100*float(np.mean(c))/(1920*1061),'skipped_percent':100-100*float(np.mean(c))/(1920*1061)}
    result={'scene':a.scene,'capture':str(a.capture.resolve()),'quality_capture':str(a.quality_capture.resolve()),
            'quality_report_sha256':sha(reports[0]),'frame_count':n,'resolution':[1920,1061],
            'native_and_mask_bridge':bridge,'selection_semantics_frames':semantics,'selection_mismatches':0,
            'reference_late_still_unique_png':len(set(ref_hashes[200:240])) if n==240 else None,
            'reference_late_still_steps':ref_steps,
            'test_full_sequence_pixel_sha256':{m:h.hexdigest() for m,h in pixel_hashes.items()},
            'windows':WINDOWS,'ssim_stride':10,'quality':summary,'coverage':counts,
            'limitations':'SS spatial reference includes baseline MIP/sharpen tuning; not absolute temporal truth. Delta residual is reference-compensated screen-space change, not optical-flow or pure ghosting.'}
    # Bistro SS accumulation has sparse 1-level quantization changes. Preserve
    # them in the evidence rather than equating PNG hash variety with flicker.
    if n==240:assert all(x['max_rgb_step']<=1 and x['changed_channels']<=16 for x in ref_steps)
    (a.output/'reference-quality.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS {a.scene}: reference quality and exact pixel counts',flush=True)

if __name__=='__main__':main()
