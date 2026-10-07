"""Check history/filter isolation and create lossless, consecutive frame evidence."""
import argparse,csv,json,re,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from edge_quality_inputs import sha,ph,rgb,dds,reconstruct

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-History-Source-Color-Blend'
CONTROL_DOC=ROOT/'Docs/Edge-History-Fixed-Weight-080'
MODES=['O-T2X-R','ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080','ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend']
LABELS=['4 J On','14 w=0.8','17 source-color-blend']
ROIS={'bistro':{'chairs':(1230,546,1358,706),'thin-chair':(1230,582,1358,670),'windows':(950,460,1110,588)},
      'minecraft':{'seams':(932,512,1060,672),'thin-seam':(956,524,1020,620),'leaves':(1420,590,1580,718),'grass-seam':(1450,665,1552,719)}}
WINDOWS={'move':range(126,132),'transition':range(178,184),'post-stop':range(190,196),'settled':range(210,216)}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def latest(scene,phase,frames=240):
    return next(r for r in reversed(load(ROOT/'tmp/source-color-blend-runs.json')) if r['scene']==scene and r['phase']==phase and r['frames']==frames)
def capture_root(receipt):
    p=Path(receipt['report']);assert sha(p).upper()==receipt['report_sha256']
    txt=p.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in txt and 'FAIL' not in txt
    return Path(re.search(r'capture_root,\s*(.*?),',txt).group(1).strip())
def weight(p):
    b=Path(p).read_bytes();h,w=struct.unpack_from('<2I',b,12);off=148 if b[84:88]==b'DX10' else 128
    return np.frombuffer(b[off:],np.float32).reshape(h,w)
def verify_trace(capture,scene,phase):
    modes=MODES[1:];frames=sorted(int(p.name[6:11]) for p in (capture/modes[-1]).glob('frame_*-weight.dds'))
    assert len(frames)==(6 if phase=='Test' else 24),(phase,len(frames))
    trace=[]
    for f in frames:
        prefix=lambda m:capture/m/f'frame_{f:05d}'
        reset=f==0 or (phase=='Test' and f==3)
        for suffix in ['-raw.dds','-current.dds','-velocity.dds','-edge.rg8','-coverage.dds']:
            assert sha(str(prefix(modes[0]))+suffix)==sha(str(prefix(modes[1]))+suffix),(scene,f,suffix,'common input/mask changed')
        current=dds(str(prefix(modes[1]))+'-current.dds');cov=dds(str(prefix(modes[1]))+'-coverage.dds')>0
        w=weight(str(prefix(modes[1]))+'-weight.dds');w13=weight(str(prefix(modes[0]))+'-weight.dds')
        assert np.isfinite(w).all() and (w[~cov]==0).all()
        assert np.abs(w[cov]-.8).max(initial=0)<1e-7,(scene,f,'fixed weight is not 0.8')
        assert np.abs(w13[cov]-.8).max(initial=0)<1e-7 and (w13[~cov]==0).all()
        for m in modes:
            out=rgb(str(prefix(m))+'.png');history=dds(str(prefix(m))+'-next-history.dds')
            assert np.array_equal(history[:,:,:3],out),(scene,f,m,'RGB feedback differs')
            assert np.array_equal(history[:,:,3],current[:,:,3]),(scene,f,m,'spatial velocity alpha differs')
            assert np.array_equal(out[~cov],current[:,:,:3][~cov]),(scene,f,m,'nonselected output differs')
            if f-1 in frames and not reset:
                assert sha(str(prefix(m))+'-previous.dds')==sha(str(capture/m/f'frame_{f-1:05d}')+'-next-history.dds'),(scene,f,m,'feedback chain broken')
        if not reset:
            assert np.array_equal(dds(str(prefix(modes[0]))+'-previous.dds')[:,:,3],dds(str(prefix(modes[1]))+'-previous.dds')[:,:,3])
        if reset:assert np.array_equal(rgb(str(prefix(modes[0]))+'.png'),rgb(str(prefix(modes[1]))+'.png')),(scene,f,'seed RGB changed')
        trace.append(dict(frame=f,reset=reset,history_chain_checked=f-1 in frames and not reset,selected_pixels=int(cov.sum()),selected_percent=float(cov.mean()*100),case14_control_mean_selected_weight=float(w13[cov].mean()),case17_mean_selected_weight=float(w[cov].mean()),input_mask_byte_mismatch=0,feedback_rgb_mismatch=0,spatial_alpha_mismatch=0,nonselected_mismatch=0))
    return trace

def sheets(capture,scene,dest):
    dest.mkdir(parents=True,exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14);made=[]
    for name,box in ROIS[scene].items():
        width=(box[2]-box[0])*2;height=(box[3]-box[1])*2
        for phase,frames in WINDOWS.items():
            for pair in range(3):
                fs=list(frames)[pair*2:pair*2+2]
                sheet=Image.new('RGB',(len(MODES)*(width+8)+8,52+2*(height+24)),(18,20,23));draw=ImageDraw.Draw(sheet)
                for col,label in enumerate(LABELS):draw.text((8+col*(width+8),8),label,fill='white',font=font)
                for row,f in enumerate(fs):
                    for col,mode in enumerate(MODES):
                        with Image.open(capture/mode/f'frame_{f:05d}.png') as im:crop=im.crop(box).resize((width,height),Image.Resampling.NEAREST)
                        x=8+col*(width+8);y=52+row*(height+24)
                        draw.text((x,y),f'f{f}',fill='white',font=font);sheet.paste(crop,(x,y+20))
                p=dest/f'{scene}-{name}-{phase}-pair{pair}.png';sheet.save(p)
                made.append(dict(path=str(p),frames=fs,roi=box,scale=2,filter='nearest',tone_adjustment=False))
    for f in [130,180,195]:
        for m in [MODES[0],MODES[-1]]:
            with Image.open(capture/m/f'frame_{f:05d}.png') as im:im.save(dest/f'{scene}-{m}-full-f{f}.png')
    return made
def analyze(scene,phase,frames=240):
    receipt=latest(scene,phase,frames);capture=capture_root(receipt)
    result=dict(validation='PASS',classification='single history weight ablation; quality judgment requires direct frames',receipt=receipt,capture_root=str(capture))
    if frames==240:result['trace']=verify_trace(capture,scene,phase)
    if phase=='Capture':
        source=load(CONTROL_DOC/f'{scene}-capture.json');old=Path(source['capture_root']);assert source['validation']=='PASS'
        reference=Path(load(ROOT/'Docs/Baseline-Restart/reused-reference-provenance.json')[scene]['reference'])
        hashes={m:[] for m in MODES};rows=[];delta=[];last={};lastd={};last_change={m:0 for m in MODES};old_arrays={}
        short=load(DOC/f'{scene}-capture.json') if frames==720 else None
        for f in range(frames):
            arr={m:rgb(capture/m/f'frame_{f:05d}.png') for m in MODES}
            for m,a in arr.items():
                digest=ph(a);hashes[m].append(digest)
                if frames==240 and m!=MODES[-1]:assert digest==source['output_hashes'][m][f],(scene,m,f,'control RGB bridge')
                if frames==720 and f<180:assert digest==short['output_hashes'][m][f],(scene,m,f,'long prefix bridge')
                if m in old_arrays and not np.array_equal(a,old_arrays[m]):last_change[m]=f
                old_arrays[m]=a
            if frames!=240:continue
            ref=rgb(reference/f'frame_{f:05d}.png')
            d=np.abs(arr[MODES[-1]].astype(np.int16)-arr[MODES[1]].astype(np.int16))
            delta.append(dict(frame=f,changed_pixels=int(np.any(d,axis=2).sum()),rgb_mae=float(d.mean()),max_channel_error=int(d.max())))
            for name,(x0,y0,x1,y1) in ROIS[scene].items():
                r=ref[y0:y1,x0:x1]
                for m,a in arr.items():
                    a=a[y0:y1,x0:x1];diff=a.astype(np.float32)-r.astype(np.float32)
                    lum=a.astype(np.float32)@np.array([.2126,.7152,.0722],np.float32);key=(m,name)
                    dt=lum-last[key] if key in last else None
                    rows.append(dict(frame=f,roi=name,mode=m,reference_rgb_mae=float(np.abs(diff).mean()),psnr=float(10*np.log10(255**2/max(float((diff**2).mean()),1e-12))),luma_delta=None if dt is None else float(np.abs(dt).mean()),luma_second_delta=None if dt is None or key not in lastd else float(np.abs(dt-lastd[key]).mean())))
                    last[key]=lum
                    if dt is not None:lastd[key]=dt
        result.update(output_hashes=hashes,rgb_hashes=hashes,whole_rgb_last_change=last_change,control_rgb_mismatch=0,bridge_frames=540 if frames==720 else 480)
        if frames==240:
            result['control_bridge']=dict(native4=240,case14=240,rgb_mismatch=0,source_evidence_path=str(CONTROL_DOC/f'{scene}-capture.json'),source_evidence_sha256=sha(CONTROL_DOC/f'{scene}-capture.json'))
            with (DOC/f'{scene}-quality-per-frame.csv').open('w',newline='',encoding='utf-8') as fp:
                wr=csv.DictWriter(fp,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
            summary=[]
            for name in ROIS[scene]:
                for window,lo,hi in [('moving',60,179),('transition',172,189),('still',190,239)]:
                    for m in MODES:
                        v=[r for r in rows if r['roi']==name and r['mode']==m and lo<=r['frame']<=hi]
                        summary.append(dict(roi=name,window=window,mode=m,reference_rgb_mae=float(np.mean([r['reference_rgb_mae'] for r in v])),psnr_mean=float(np.mean([r['psnr'] for r in v])),luma_delta=float(np.mean([r['luma_delta'] for r in v])),luma_second_delta=float(np.mean([r['luma_second_delta'] for r in v]))))
            result.update(reference_root=str(reference),reference_classification='supersampled spatial proxy; not temporal ground truth',new_vs_case14_control=delta,roi_metrics=summary,media=sheets(capture,scene,ROOT/'tmp/source-color-blend/media'),limitations=['Raw temporal differences include camera motion and blur','Case4 pattern On versus selected Off is not coverage-only comparison','GPU filter versus CPU ideal is bounded; not pixel-exact','No object motion or previous-depth disocclusion rejection'])
        else:result['control_bridge']=dict(common_pose_frames_per_mode=180,modes=3,rgb_mismatch=0)
    suffix='long-capture' if frames==720 else phase.lower()
    (DOC/f'{scene}-{suffix}.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(scene=scene,phase=phase,frames=frames,validation='PASS',trace_frames=len(result.get('trace',[])),capture=str(capture))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);p.add_argument('--phase',choices=['Test','Capture'],required=True);p.add_argument('--frames',type=int,choices=[240,720],default=240);a=p.parse_args();analyze(a.scene,a.phase,a.frames)
