"""Offline, frame-aligned 14/16/17 quality audit; no renderer changes.

Raw temporal differences and shared optical-flow residuals are diagnostics,
not absolute flicker/ghosting ground truth. Thin-line thresholds are reported
as a sensitivity sweep rather than a binary visibility verdict.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.append('C:/Users/USER/Desktop/research/.research-tools/quality-venv/Lib/site-packages')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2
from edge_quality_inputs import dds

ROOT = Path(__file__).resolve().parents[2]
BASE = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080'
CASES = [14,16,17]
PAIRS = [(14,16),(14,17),(16,17)]
ROIS = {'bistro': {'thin-chair': (1230,582,1358,670), 'windows': (950,460,1110,588)},
        'minecraft': {'thin-seam': (956,524,1020,620), 'leaves': (1420,590,1580,718),
                      'grass-seam': (1450,665,1552,719)}}
LUMA = np.array([.2126,.7152,.0722],np.float32)
FONT = ImageFont.truetype('C:/Windows/Fonts/consola.ttf',13)
FLOW_PARAMS = dict(pyr_scale=.5,levels=3,winsize=15,iterations=3,poly_n=5,poly_sigma=1.2,flags=0)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rgb(path,expected,retries):
    for attempt in range(3):
        payload = Path(path).read_bytes()
        with Image.open(io.BytesIO(payload)) as fp:
            im = fp.convert('RGB')
        assert im.size == (1920,1061)
        actual = hashlib.sha256(im.tobytes()).hexdigest()
        if actual == expected:
            return np.asarray(im).copy()
        retries.append(dict(path=str(path),attempt=attempt+1,actual=actual,expected=expected,
                            encoded_sha256=hashlib.sha256(payload).hexdigest()))
    raise AssertionError((str(path),actual,expected))


def flow_map(previous,current):
    pg = cv2.cvtColor(previous,cv2.COLOR_RGB2GRAY)
    cg = cv2.cvtColor(current,cv2.COLOR_RGB2GRAY)
    forward = cv2.calcOpticalFlowFarneback(pg,cg,None,**FLOW_PARAMS)
    backward = cv2.calcOpticalFlowFarneback(cg,pg,None,**FLOW_PARAMS)
    yy,xx = np.mgrid[:cg.shape[0],:cg.shape[1]].astype(np.float32)
    mx,my = xx+backward[:,:,0],yy+backward[:,:,1]
    sampled = cv2.remap(forward,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    error = np.linalg.norm(backward+sampled,axis=2)
    valid = (mx>=1)&(my>=1)&(mx<=cg.shape[1]-2)&(my<=cg.shape[0]-2)&np.isfinite(error)&(error<=1)
    return mx,my,valid


def windows(f):
    if 60<=f<660:
        return 'moving'
    if 660<=f<700:
        return 'post-stop'
    if f>=700:
        return 'settled'
    return 'initial'


def sheet(scene,name,box,frames,arrays,pair,out,tag):
    scale = 4 if name=='thin-seam' else 2
    w,h = (box[2]-box[0])*scale,(box[3]-box[1])*scale
    canvas = Image.new('RGB',(2*(w+8)+8,2*(h+60)),(18,20,23))
    draw = ImageDraw.Draw(canvas)
    for row,f in enumerate(frames):
        for col,case in enumerate(pair):
            x,y = 8+col*(w+8),row*(h+60)
            draw.text((x,y+5),f'{case} / JOff / w0.8',font=FONT,fill='white')
            draw.text((x,y+23),f'{scene} f{f} {windows(f)}',font=FONT,fill='#cdd7e1')
            im = Image.fromarray(arrays[f][case]).crop(box).resize((w,h),Image.Resampling.NEAREST)
            canvas.paste(im,(x,y+48))
    path = out/f'{scene}-{name}-{pair[0]}-vs-{pair[1]}-{tag}-f{frames[0]}-{frames[1]}.png'
    canvas.save(path)
    return dict(path=str(path),roi=box,frames=frames,pair=pair,scale=scale,filter='nearest',tone_adjustment=False)


def line_probe(evidence,short,scene_arrays,retries):
    cap = Path(short['capture_root'])
    rows = []
    for f in range(126,132):
        p = cap/BASE/f'frame_{f:05d}-current.dds'
        current = dds(p)[:,:,:3]
        x = int(np.argmin((current[578:612,966:984].astype(np.float32)@LUMA).mean(axis=0)))+966
        def contrasts(a):
            lum = a[578:612,x-3:x+4].astype(np.float32)@LUMA
            return .5*(lum[:,0]+lum[:,6])-lum[:,3]
        source_c = contrasts(current)
        for case in CASES:
            c = contrasts(scene_arrays[f][case])
            rows.append(dict(frame=f,case=case,x=x,y0=578,y1=612,spatial_mean=float(source_c.mean()),
                             contrast_mean=float(c.mean()),contrast_min=float(c.min()),
                             below_1=int((c<1).sum()),below_2=int((c<2).sum()),below_4=int((c<4).sum()),
                             below_8=int((c<8).sum()),row_contrast=c.tolist()))
    return dict(classification='Shared current-spatial x search, fixed y strip; not full object tracking or visibility ground truth',
                selection='argmin current spatial mean luma in x966..983/y578..611',
                background='mean of columns x-3 and x+3; contrast minus center x',
                thresholds=[1,2,4,8],units='encoded Rec709 luma levels 0..255',rows=rows,
                current_source=str(cap),frames=[126,131])


def analyze(scene,evidence,short_evidence,out):
    infos = {i:load(evidence/f'case{i}/{scene}-long-capture.json') for i in [16,17]}
    metas = {i:load(evidence/f'case{i}/case.json') for i in [16,17]}
    shorts = {i:load(short_evidence/f'case{i}/{scene}-capture.json') for i in [16,17]}
    assert infos[16]['output_hashes'][BASE] == infos[17]['output_hashes'][BASE]
    sources = {14:(infos[16],BASE),16:(infos[16],metas[16]['semantic_id']),17:(infos[17],metas[17]['semantic_id'])}
    for case,(info,mode) in sources.items():
        original_short = shorts[16 if case==14 else case]
        assert info['output_hashes'][mode][:180] == original_short['output_hashes'][mode][:180]
        assert info['validation']=='PASS'
    ref_info = load(ROOT/'Docs/Baseline-Restart/reused-reference-provenance.json')[scene]
    ref_root = Path(ref_info['reference'])
    cv2.setNumThreads(1)
    rows,full_delta,retries,kept = [],[],[],{}
    last,last_delta,previous_halo = {},{},{}
    last_rgb = {}
    last_change = {c:0 for c in CASES}
    save_frames = {f for start in [126,480,658,700] for f in range(start,start+6)}
    for f in range(720):
        arrays = {c:read_rgb(Path(info['capture_root'])/mode/f'frame_{f:05d}.png',info['output_hashes'][mode][f],retries)
                  for c,(info,mode) in sources.items()}
        for c in CASES:
            if c in last_rgb and not np.array_equal(arrays[c],last_rgb[c]):
                last_change[c] = f
            last_rgb[c] = arrays[c]
        if f in save_frames:
            kept[f] = arrays
        reference = None
        if 60<=f<180:
            with Image.open(ref_root/f'frame_{f:05d}.png') as fp:
                reference = np.asarray(fp.convert('RGB')).copy()
        for c in [16,17]:
            d = np.abs(arrays[c].astype(np.int16)-arrays[14].astype(np.int16))
            full_delta.append(dict(frame=f,case=c,rgb_mae=float(d.mean()),max_channel=int(d.max()),
                                   changed_pixels=int(np.any(d>0,axis=2).sum()),pixels_delta_ge4=int(np.any(d>=4,axis=2).sum())))
        for name,box in ROIS[scene].items():
            x0,y0,x1,y1 = box
            hx0,hy0,hx1,hy1 = max(0,x0-32),max(0,y0-32),min(1920,x1+32),min(1061,y1+32)
            halos = {c:arrays[c][hy0:hy1,hx0:hx1] for c in CASES}
            sl = np.s_[y0-hy0:y1-hy0,x0-hx0:x1-hx0]
            alignment = flow_map(previous_halo[name][14],halos[14]) if name in previous_halo else None
            for c in CASES:
                a = arrays[c][y0:y1,x0:x1].astype(np.float32)
                lum = a@LUMA
                key = (name,c)
                dt = lum-last[key] if key in last else None
                d2 = None if dt is None or key not in last_delta else float(np.abs(dt-last_delta[key]).mean())
                residual = valid_fraction = None
                if alignment is not None:
                    mx,my,valid = alignment
                    prev = cv2.remap(previous_halo[name][c].astype(np.float32),mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
                    mask = valid[sl]
                    error = np.abs(lum-(prev[sl]@LUMA))
                    valid_fraction = float(mask.mean())
                    residual = float(error[mask].mean()) if mask.any() else None
                relative = np.abs(a-arrays[14][y0:y1,x0:x1].astype(np.float32))
                rows.append(dict(scene=scene,frame=f,phase=windows(f),roi=name,case=c,
                                 raw_luma_delta=None if dt is None else float(np.abs(dt).mean()),raw_luma_second_delta=d2,
                                 flow_luma_residual=residual,flow_valid_fraction=valid_fraction,
                                 reference_rgb_mae=None if reference is None else float(np.abs(a-reference[y0:y1,x0:x1]).mean()),
                                 vs14_rgb_mae=float(relative.mean()),vs14_max_channel=float(relative.max())))
                last[key] = lum
                if dt is not None:
                    last_delta[key] = dt
            previous_halo[name] = halos
        if f%120==0:
            print('Verified frame audit',scene,f,'/720',flush=True)
    metrics = ['raw_luma_delta','raw_luma_second_delta','flow_luma_residual','flow_valid_fraction','reference_rgb_mae','vs14_rgb_mae']
    summary = []
    for name in ROIS[scene]:
        for label,lo,hi in [('early-moving',60,179),('moving',60,659),('transition',658,689),('settled',700,719)]:
            for c in CASES:
                subset = [r for r in rows if r['roi']==name and r['case']==c and lo<=r['frame']<=hi]
                entry = dict(roi=name,window=label,case=c,start=lo,end=hi,frames=len(subset))
                entry['metric_sample_counts'] = {}
                for key in metrics:
                    values = [r[key] for r in subset if r[key] is not None]
                    entry[key] = float(np.mean(values)) if values else None
                    entry['metric_sample_counts'][key] = len(values)
                summary.append(entry)
    for filename,data in [(f'{scene}-per-frame.csv',rows),(f'{scene}-full-delta.csv',full_delta)]:
        with (out/filename).open('w',newline='',encoding='utf-8') as fp:
            wr = csv.DictWriter(fp,fieldnames=list(data[0]));wr.writeheader();wr.writerows(data)
    sheets = []
    for name,box in ROIS[scene].items():
        for tag,start in [('moving',126),('late-moving',480),('transition',658),('settled',700)]:
            for pair in PAIRS:
                for offset in [0,2,4]:
                    fs = [start+offset,start+offset+1]
                    sheets.append(sheet(scene,name,box,fs,kept,pair,out,tag))
        fig,ax = plt.subplots(2,1,figsize=(10,6),sharex=True)
        for c in CASES:
            subset = [r for r in rows if r['roi']==name and r['case']==c and 60<=r['frame']<660]
            for j,key in enumerate(['raw_luma_second_delta','flow_luma_residual']):
                ax[j].plot([r['frame'] for r in subset],[r[key] for r in subset],label=str(c),linewidth=.8,alpha=.8)
        ax[0].set_ylabel('Raw luma second difference')
        ax[1].set_ylabel('Shared-flow aligned residual')
        ax[1].set_xlabel('Source frame / motion60..659')
        for a in ax:
            a.set_ylim(bottom=0);a.legend();a.grid(alpha=.2)
        fig.suptitle(f'{scene} / {name}: auxiliary variation, not absolute flicker')
        fig.tight_layout();fig.savefig(out/f'{scene}-{name}-variation.png',dpi=160);plt.close(fig)
    result = dict(validation='PASS',scene=scene,mode_order=CASES,semantic_ids={c:mode for c,(info,mode) in sources.items()},
                  pattern='All Off',history_weight=.8,spatial='Original SMAA Ultra',reprojection='camera/depth only',
                  source_pngs_checked=2160,source_read_retries=retries,unmatched_frames_used=0,
                  source_provenance={c:dict(capture=info['capture_root'],evidence=str(evidence/f'case{16 if c==14 else c}/{scene}-long-capture.json')) for c,(info,mode) in sources.items()},
                  reference_root=str(ref_root),reference_scope='frames60..179 only; supersampled spatial proxy, not temporal ground truth',
                  flow_reference='case14 output with 32px ROI halo; shared across all modes; may be biased by temporal filtering',
                  flow_parameters=FLOW_PARAMS,flow_fb_threshold=1,flow_doc='https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html',
                  whole_rgb_last_change=last_change,summary=summary,sheets=sheets,full_delta=full_delta,
                  libraries=dict(numpy=np.__version__,opencv=cv2.__version__,matplotlib=matplotlib.__version__),
                  inspection_complete=False,actual_playback_observed=False)
    if scene=='minecraft':
        result['line_probe'] = line_probe(evidence,shorts[16],kept,retries)
        probe = result['line_probe']['rows']
        fig,ax = plt.subplots(figsize=(8,4))
        for c in CASES:
            subset = [r for r in probe if r['case']==c]
            ax.plot([r['frame'] for r in subset],[r['contrast_mean'] for r in subset],marker='o',label=str(c))
        ax.set_ylim(0,30);ax.set_xlabel('Source frame');ax.set_ylabel('Shared-strip mean contrast / 0..255 luma')
        ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'minecraft-line-contrast.png',dpi=160);plt.close(fig)
    (out/f'{scene}-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS frame audit',scene,'2160 source frames',len(rows),'ROI observations',flush=True)


if __name__=='__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--scene',choices=['bistro','minecraft'],required=True)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--short-evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    analyze(args.scene,args.evidence.resolve(),args.short_evidence.resolve(),args.output.resolve())
