"""Verify GPU feedback chains, unchanged controls, and prepare lossless visual evidence."""
import argparse,csv,json,re,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from edge_quality_inputs import sha,ph,rgb,dds,reconstruct

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-Persistence-Resolved-RGB-Feedback'
MODES=['O-T2X-R','ABL-ET2X-R-PreviousRawEdge-BilinearRGB','ABL-ET2X-R-PreviousRawEdge-ResolvedRGB']
LABELS=['4 Native T2X-R / ON','10 Spatial history / OFF','11 Resolved RGB / OFF']
ROIS={'bistro':{'chairs':(1190,530,1478,722),'thin-chair':(1230,582,1358,670)},
      'minecraft':{'seams':(902,472,1088,666),'thin-seam':(956,524,1020,620)}}
WINDOWS={'move':range(130,136),'transition':range(178,184),'still':range(190,196)}

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def capture_root(receipt):
    p=Path(receipt['report']);assert sha(p).upper()==receipt['report_sha256']
    txt=p.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in txt and 'FAIL' not in txt
    return Path(re.search(r'capture_root,\s*(.*?),',txt).group(1).strip())
def latest(scene,phase):
    return next(r for r in reversed(load(ROOT/'tmp/edge-resolved-rgb-feedback-runs.json')) if r['scene']==scene and r['phase']==phase and r['frames']==240)
def weight(p):
    b=Path(p).read_bytes();h,w=struct.unpack_from('<2I',b,12)
    off=148 if b[84:88]==b'DX10' else 128
    return np.frombuffer(b[off:],np.float32).reshape(h,w)

def verify_trace(capture,scene,phase):
    selected=MODES[1:];frames=sorted(int(p.name[6:11]) for p in (capture/selected[1]).glob('frame_*-weight.dds'))
    assert len(frames)==(6 if phase=='Test' else 43),len(frames)
    trace=[]
    for f in frames:
        prefix=lambda m:capture/m/f'frame_{f:05d}'
        reset=f==0 or (phase=='Test' and f==3)
        for suffix in ['-raw.dds','-current.dds','-velocity.dds','-edge.rg8','-coverage.dds','-weight.dds']:
            assert sha(str(prefix(selected[0]))+suffix)==sha(str(prefix(selected[1]))+suffix),(scene,f,suffix)
        current=dds(str(prefix(selected[1]))+'-current.dds')
        cov=dds(str(prefix(selected[1]))+'-coverage.dds')>0
        w=weight(str(prefix(selected[1]))+'-weight.dds')
        assert np.isfinite(w).all() and (w>=0).all() and (w<=.5).all() and (w[~cov]==0).all()
        out=rgb(str(prefix(selected[1]))+'.png')
        history=dds(str(prefix(selected[1]))+'-next-history.dds')
        assert np.array_equal(history[:,:,:3],out),(scene,f,'feedback RGB != visible')
        assert np.array_equal(history[:,:,3],current[:,:,3]),(scene,f,'velocity alpha changed')
        assert np.array_equal(out[~cov],current[:,:,:3][~cov]),(scene,f,'nonselected changed')
        prior=dds(str(prefix(selected[1]))+'-previous.dds')
        prior10=dds(str(prefix(selected[0]))+'-previous.dds')
        if not reset:assert np.array_equal(prior[:,:,3],prior10[:,:,3]),(scene,f,'point alpha source changed')
        chain=False
        if f-1 in frames and not reset:
            assert sha(str(prefix(selected[1]))+'-previous.dds')==sha(str(capture/selected[1]/f'frame_{f-1:05d}')+'-next-history.dds'),(scene,f,'broken history chain')
            chain=True
        if reset:
            assert np.array_equal(out,rgb(str(prefix(selected[0]))+'.png')),(scene,f,'reset seed differs')
        else:
            vel=dds(str(prefix(selected[1]))+'-velocity.dds');rec=reconstruct(current,prior,vel)
            safe=cov&rec['safe'];assert np.abs(rec['weight'][safe]-w[safe]).max(initial=0)<3e-6
        assert np.array_equal(dds(str(prefix(selected[0]))+'-next-history.dds'),dds(str(prefix(selected[0]))+'-current.dds')),(scene,f,'case10 spatial history changed')
        trace.append(dict(frame=f,reset=reset,history_chain_checked=chain,selected_pixels=int(cov.sum()),selected_percent=float(cov.mean()*100),mean_selected_weight=float(w[cov].mean()),positive_weight_percent=float((w>0).mean()*100),feedback_rgb_mismatch=0,spatial_alpha_mismatch=0,nonselected_mismatch=0,paired_mask_input_weight_mismatch=0))
    return trace

def sheets(capture,scene,dest):
    dest.mkdir(parents=True,exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
    made=[]
    for name,box in ROIS[scene].items():
        w=(box[2]-box[0])*2;h=(box[3]-box[1])*2
        for phase,frames in WINDOWS.items():
            # Three separate two-frame sheets avoid shrinking the thin line evidence.
            for pair in range(3):
                fs=list(frames)[pair*2:pair*2+2]
                sheet=Image.new('RGB',(3*(w+8)+8,52+2*(h+24)),(18,20,23));draw=ImageDraw.Draw(sheet)
                for col,label in enumerate(LABELS):draw.text((8+col*(w+8),8),label,fill='white',font=font)
                for row,f in enumerate(fs):
                    for col,mode in enumerate(MODES):
                        with Image.open(capture/mode/f'frame_{f:05d}.png') as im:crop=im.crop(box).resize((w,h),Image.Resampling.NEAREST)
                        x=8+col*(w+8);y=52+row*(h+24)
                        draw.text((x,y),f'f{f} / {name}',fill='white',font=font);sheet.paste(crop,(x,y+20))
                p=dest/f'{scene}-{name}-{phase}-pair{pair}.png';sheet.save(p)
                made.append(dict(path=str(p),frames=fs,roi=box,scale=2,filter='nearest',tone_adjustment=False))
    for f in [130,180,195]:
        for mode in MODES:
            with Image.open(capture/mode/f'frame_{f:05d}.png') as im:im.save(dest/f'{scene}-{mode}-full-f{f}.png')
    return made

def analyze(scene,phase):
    receipt=latest(scene,phase);capture=capture_root(receipt)
    trace=verify_trace(capture,scene,phase)
    result=dict(validation='PASS',classification='feedback GPU correctness; quality judgment pending',receipt=receipt,capture_root=str(capture),trace=trace)
    if phase=='Capture':
        oldreceipt=next(r for r in reversed(load(ROOT/'tmp/edge-bilinear-history-rgb-runs.json')) if r['scene']==scene and r['phase']=='Capture')
        old=capture_root(oldreceipt)
        reference=Path(load(ROOT/'Docs/Baseline-Restart/reused-reference-provenance.json')[scene]['reference'])
        hashes={m:[] for m in MODES};rows=[];delta=[];last={};lastd={}
        for f in range(240):
            arr={m:rgb(capture/m/f'frame_{f:05d}.png') for m in MODES};ref=rgb(reference/f'frame_{f:05d}.png')
            for m,a in arr.items():
                hashes[m].append(ph(a))
                if m in MODES[:2]:assert ph(a)==ph(rgb(old/m/f'frame_{f:05d}.png')),(scene,m,f,'old RGB bridge mismatch')
            d=np.abs(arr[MODES[2]].astype(np.int16)-arr[MODES[1]].astype(np.int16))
            delta.append(dict(frame=f,changed_pixels=int(np.any(d,axis=2).sum()),rgb_mae=float(d.mean()),max=int(d.max())))
            for name,(x0,y0,x1,y1) in ROIS[scene].items():
                r=ref[y0:y1,x0:x1]
                for m,a in arr.items():
                    a=a[y0:y1,x0:x1];diff=a.astype(np.float32)-r.astype(np.float32)
                    lum=a.astype(np.float32)@np.array([.2126,.7152,.0722],np.float32);key=(m,name)
                    dt=lum-last[key] if key in last else None
                    rows.append(dict(frame=f,roi=name,mode=m,reference_rgb_mae=float(np.abs(diff).mean()),psnr=float(10*np.log10(255**2/max(float((diff**2).mean()),1e-12))),luma_delta=None if dt is None else float(np.abs(dt).mean()),luma_second_delta=None if dt is None or key not in lastd else float(np.abs(dt-lastd[key]).mean())))
                    last[key]=lum
                    if dt is not None:lastd[key]=dt
        with (DOC/f'{scene}-quality-per-frame.csv').open('w',newline='') as fp:
            wr=csv.DictWriter(fp,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
        summary=[]
        for name in ROIS[scene]:
            for window,lo,hi in [('moving',60,179),('transition',172,189),('still',190,239)]:
                for m in MODES:
                    values=[r for r in rows if r['roi']==name and r['mode']==m and lo<=r['frame']<=hi]
                    summary.append(dict(roi=name,window=window,mode=m,reference_rgb_mae=float(np.mean([v['reference_rgb_mae'] for v in values])),psnr_mean=float(np.mean([v['psnr'] for v in values])),luma_delta=float(np.mean([v['luma_delta'] for v in values])),luma_second_delta=float(np.mean([v['luma_second_delta'] for v in values]))))
        result.update(control_bridge=dict(native4=240,case10=240,rgb_mismatch=0,source_receipt=oldreceipt),reference_root=str(reference),reference_classification='supersampled spatial proxy; not temporal ground truth',output_hashes=hashes,new_vs_case10=delta,roi_metrics=summary,media=sheets(capture,scene,ROOT/'tmp/edge-resolved-rgb-feedback/media'),limitations=['Camera motion contributes to raw time differences','No CGVQM model invocation in this analyzer','Frame visual inspection required before quality claims','Camera/depth motion only'])
    (DOC/f'{scene}-{phase.lower()}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(scene=scene,phase=phase,validation='PASS',trace_frames=len(trace),feedback_chain_checks=sum(t['history_chain_checked'] for t in trace),capture=str(capture))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);p.add_argument('--phase',choices=['Test','Capture'],default='Capture');a=p.parse_args();analyze(a.scene,a.phase)
