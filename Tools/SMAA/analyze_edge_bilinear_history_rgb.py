"""Validate RGB-only GPU sampler ablation and prepare original-pixel quality sheets.

This script does not classify quality by a single score. Sheets require direct QA.
Reference is a supersampled spatial proxy, not temporal/ghosting ground truth.
"""
import argparse, csv, json, re, struct
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from edge_quality_inputs import sha, ph, rgb, dds, edges, linear, encoded, reconstruct

MODES = ['O-T2X-R', 'O-ET2X-R-CurrentEdge-Point',
         'O-ET2X-R-PreviousRawEdge-Point', 'ABL-ET2X-R-PreviousRawEdge-BilinearRGB']
LABELS = ['4 Native T2X-R\nPattern ON', '6 Current edge\nPoint / OFF',
          '9 Previous edge\nPoint / OFF', 'New PreviousEdge\nBilinearRGB / OFF', 'SS reference\nSpatial proxy']
ROIS = {'bistro': {'chair': (1230,582,1358,670), 'chairs-wide': (1190,530,1478,722)},
        'minecraft': {'wall-seam': (956,524,1020,620), 'seam-wide': (902,472,1088,666)}}
WINDOWS = {'move': range(130,136), 'before': range(127,133), 'after': range(133,139),
           'transition': range(178,184), 'still': range(190,196)}
ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT/'Docs/Edge-Persistence-Bilinear-History-RGB'

def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def weight_dds(p):
    b=Path(p).read_bytes(); assert b[:4]==b'DDS '
    h,w=struct.unpack_from('<2I',b,12); assert (w,h)==(1920,1061)
    if b[84:88]==b'DX10':
        assert struct.unpack_from('<I',b,128)[0]==41; off=148
    else:
        assert struct.unpack_from('<I',b,84)[0]==114; off=128
    return np.frombuffer(b[off:],np.float32).reshape(h,w)

def bilinear(previous,coords):
    p=coords-.5; ij=np.floor(p).astype(np.int32); frac=p-ij
    h,w=previous.shape[:2]; x0=ij[:,:,0].clip(0,w-1); y0=ij[:,:,1].clip(0,h-1)
    x1=(ij[:,:,0]+1).clip(0,w-1); y1=(ij[:,:,1]+1).clip(0,h-1)
    lp=linear(previous[:,:,:3]); fx=frac[:,:,0,None]; fy=frac[:,:,1,None]
    top=lp[y0,x0]*(1-fx)+lp[y0,x1]*fx
    bot=lp[y1,x0]*(1-fx)+lp[y1,x1]*fx
    span=np.maximum.reduce([lp[y0,x0],lp[y0,x1],lp[y1,x0],lp[y1,x1]])-np.minimum.reduce([lp[y0,x0],lp[y0,x1],lp[y1,x0],lp[y1,x1]])
    return top*(1-fy)+bot*fy,span

def sheets(capture,reference,scene,media):
    media.mkdir(parents=True,exist_ok=True)
    try: font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
    except OSError: font=ImageFont.load_default()
    made=[]
    for name,box in ROIS[scene].items():
        w=(box[2]-box[0])*2; h=(box[3]-box[1])*2
        for window,frames in WINDOWS.items():
            sheet=Image.new('RGB',(5*(w+8)+8,56+len(frames)*(h+24)),(18,20,23))
            draw=ImageDraw.Draw(sheet)
            for col,label in enumerate(LABELS):
                heading_font=font if w>=256 else ImageFont.truetype('C:/Windows/Fonts/consola.ttf',12)
                draw.multiline_text((8+col*(w+8),8),label,fill='white',font=heading_font,spacing=3)
            for row,f in enumerate(frames):
                for col,mode in enumerate(MODES+['reference']):
                    p=(reference if mode=='reference' else capture/mode)/f'frame_{f:05d}.png'
                    with Image.open(p) as im: im=im.crop(box).resize((w,h),Image.Resampling.NEAREST)
                    x=8+col*(w+8);y=56+row*(h+24)
                    draw.text((x,y),f'f{f} {name}',fill='white',font=font);sheet.paste(im,(x,y+20))
            path=media/f'{scene}-{name}-{window}.png';sheet.save(path)
            made.append(dict(path=str(path),roi=box,frames=list(frames),scale=2,filter='nearest',tone_adjustment=False))
    return made

def analyze(scene):
    records=load(ROOT/'tmp/edge-bilinear-history-rgb-runs.json')
    receipt=next(r for r in reversed(records) if r['scene']==scene and r['phase']=='Capture')
    report=Path(receipt['report']); assert sha(report).upper()==receipt['report_sha256']
    txt=report.read_text(encoding='utf-8-sig'); assert 'Aggregate: PASS' in txt and 'FAIL' not in txt
    capture=Path(re.search(r'capture_root,\s*(.*?),',txt).group(1).strip())
    reference=Path(load(ROOT/'Docs/Baseline-Restart/reused-reference-provenance.json')[scene]['reference'])
    old6=load(ROOT/f'Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json')
    old9=load(DOC/f'sources/{scene}-case9-capture.json')['output_hashes']
    expected={MODES[0]:old6['O-T2X-R'],MODES[1]:old6['ABL-Spatial-FirstEdge-Stencil-PatternOff-R'],MODES[2]:old9['F-EagerPreviousFetch']}
    hashes={m:[] for m in MODES}; rows=[]; prev_luma={}; prev_delta={}
    delta_summary=[]; still_mismatch=[]
    for f in range(240):
        arr={m:rgb(capture/m/f'frame_{f:05d}.png') for m in MODES}; ref=rgb(reference/f'frame_{f:05d}.png')
        for m,a in arr.items():
            h=ph(a);hashes[m].append(h)
            if m in expected: assert h==expected[m][f], (scene,m,f,'old RGB bridge mismatch')
        dif=np.abs(arr[MODES[3]].astype(np.int16)-arr[MODES[2]].astype(np.int16))
        delta_summary.append(dict(frame=f,changed_pixels=int(np.any(dif,axis=2).sum()),mae=float(dif.mean()),max=int(dif.max())))
        if f>=190 and np.any(dif):still_mismatch.append(f)
        for roi,box in ROIS[scene].items():
            x0,y0,x1,y1=box;r=ref[y0:y1,x0:x1]
            for m,a in arr.items():
                a=a[y0:y1,x0:x1]; diff=np.abs(a.astype(np.float32)-r.astype(np.float32))
                lum=a.astype(np.float32)@np.array([.2126,.7152,.0722],np.float32); k=(m,roi)
                d=lum-prev_luma[k] if k in prev_luma else None
                rows.append(dict(frame=f,phase='still-before' if f<60 else 'move' if f<180 else 'still-after',roi=roi,mode=m,reference_rgb_mae=float(diff.mean()),reference_psnr=float(10*np.log10(255**2/max(float((diff**2).mean()),1e-12))),luma_adjacent_mae=None if d is None else float(np.abs(d).mean()),luma_second_difference_mae=None if d is None or k not in prev_delta else float(np.abs(d-prev_delta[k]).mean())))
                prev_luma[k]=lum
                if d is not None:prev_delta[k]=d
    traceframes=sorted(int(p.name[6:11]) for p in (capture/MODES[2]).glob('frame_*-weight.dds'))
    assert len(traceframes)==43
    trace=[]; model_frames={60,61,130,131,132,133,134,135,178,179,180,181,190,191}
    for f in traceframes:
        prefix=lambda m: capture/m/f'frame_{f:05d}'
        for suffix in ['-raw.dds','-current.dds','-previous.dds','-velocity.dds','-edge.rg8','-coverage.dds','-weight.dds']:
            assert sha(str(prefix(MODES[2]))+suffix)==sha(str(prefix(MODES[3]))+suffix),(scene,f,suffix,'input or weight changed')
        current=dds(str(prefix(MODES[3]))+'-current.dds');cov=dds(str(prefix(MODES[3]))+'-coverage.dds')>0
        weight=weight_dds(str(prefix(MODES[3]))+'-weight.dds')
        out=rgb(str(prefix(MODES[3]))+'.png');assert np.array_equal(out[~cov],current[:,:,:3][~cov]),(scene,f,'nonselected changed')
        assert np.isfinite(weight).all() and (weight>=0).all() and (weight<=.5).all() and (weight[~cov]==0).all()
        if f==0: assert np.array_equal(cov,np.any(edges(str(prefix(MODES[3]))+'-edge.rg8')>0,axis=2))
        item=dict(frame=f,selected_pixels=int(cov.sum()),selected_percent=float(cov.mean()*100),positive_weight_pixels=int((weight>0).sum()),mean_selected_weight=float(weight[cov].mean()),nonselected_rgb_mismatch=0,paired_input_mask_weight_byte_mismatch=0)
        if f in model_frames:
            previous=dds(str(prefix(MODES[3]))+'-previous.dds');vel=dds(str(prefix(MODES[3]))+'-velocity.dds')
            rec=reconstruct(current,previous,vel);safe=cov&rec['safe']
            err=np.abs(rec['weight'][safe]-weight[safe]);assert float(err.max(initial=0))<3e-6,(scene,f,'point alpha weight mirror')
            # Ideal float bilinear is diagnostic; D3D11 texture units have finite filtering precision.
            lp,span=bilinear(previous,rec['coords']);lc=linear(current[:,:,:3]);mix=lc+(lp-lc)*weight[:,:,None]
            cpu=encoded(mix);rgb_error=np.abs(cpu[safe].astype(np.int16)-out[safe].astype(np.int16))
            point_gpu=rgb(str(prefix(MODES[2]))+'.png');point_err=np.abs(rec['full_resolve'][safe].astype(np.int16)-point_gpu[safe].astype(np.int16))
            assert int(point_err.max(initial=0))<=1
            # Conservative diagnostic envelope, not an exact NVIDIA sampler mirror.
            # DX11 7.18.8/7.18.16: >=8 fractional bits in coordinates and fixed-format
            # filtering at format precision. Bound the two coordinate errors by 2/256
            # times four-texel span and filter arithmetic by 1/255 in linear RGB.
            # Also allow .5/255 linear for input conversion and one encoded output level.
            envelope=weight[:,:,None]*(span/128+1/255)+.5/255
            low=encoded(mix-envelope).astype(np.int16)-1;high=encoded(mix+envelope).astype(np.int16)+1
            inside=(out.astype(np.int16)>=low)&(out.astype(np.int16)<=high)
            assert inside[safe].all(),(scene,f,'bilinear finite-precision diagnostic envelope')
            item.update(safe_model_pixels=int(safe.sum()),point_weight_max_error=float(err.max(initial=0)),point_rgb_max_error=int(point_err.max(initial=0)),bilinear_ideal_cpu_rgb_max_error=int(rgb_error.max(initial=0)),bilinear_ideal_cpu_rgb_mae=float(rgb_error.mean()),bilinear_diagnostic_envelope_failures=0)
        trace.append(item)
    media=ROOT/'tmp/edge-bilinear-history-rgb-media'
    made=sheets(capture,reference,scene,media)
    metrics=DOC/f'{scene}-quality-per-frame.csv';metrics.parent.mkdir(parents=True,exist_ok=True)
    with metrics.open('w',newline='',encoding='utf-8') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summaries=[]
    for roi in ROIS[scene]:
        for phase,lo,hi in [('central-move',60,179),('move-to-still',172,189),('late-still',190,239)]:
            for m in MODES:
                v=[r for r in rows if r['roi']==roi and r['mode']==m and lo<=r['frame']<=hi]
                summaries.append(dict(roi=roi,window=phase,first_frame=lo,last_frame=hi,mode=m,reference_rgb_mae=float(np.mean([r['reference_rgb_mae'] for r in v])),reference_psnr_mean=float(np.mean([r['reference_psnr'] for r in v])),luma_adjacent_mae=float(np.mean([r['luma_adjacent_mae'] for r in v])),luma_second_difference_mae=float(np.mean([r['luma_second_difference_mae'] for r in v]))))
    result=dict(validation='PASS',classification='RGB-only sampler ablation; visual QA pending',receipt=receipt,capture_root=str(capture),reference_root=str(reference),reference_classification='supersampled spatial proxy',frames_per_mode=240,control_bridges={'native4':240,'current_edge6':240,'previous_raw_edge9':240,'RGB_mismatch':0},output_hashes=hashes,paired_trace_frames=43,trace=trace,new_vs_case9=delta_summary,late_still_different_frames=still_mismatch,roi_metrics=summaries,media=made,limitations=['ROI temporal differences include camera motion','Ideal CPU filter has finite-precision GPU tolerance; not an exact hardware filter claim','CGVQM not rerun; visual QA required','Camera/depth motion only; no moving-object or disocclusion ground truth'])
    path=DOC/f'{scene}-capture.json';path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(scene=scene,validation='PASS',control_bridge_rgb_mismatch=0,paired_trace_frames=43,late_still_different_frames=still_mismatch,result=str(path),media_count=len(made))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True)
    analyze(p.parse_args().scene)
