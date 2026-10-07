"""Verify the reference bridge and create pair media for the offline frame audit."""
import csv
import html
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import audit_source_temporal_frames as audit

ROOT = audit.ROOT
OUT = ROOT/'Deliverables/SMAA_14_16_17_FrameAudit_20261007'
LONG = ROOT/'Deliverables/SMAA_15_16_17_Extended_20261007/EvidenceLong'
SHORT = ROOT/'Deliverables/SMAA_15_16_17_20261007/Evidence'


def finish(scene):
    result = audit.load(OUT/f'{scene}-audit.json')
    records = list(csv.DictReader((OUT/f'{scene}-per-frame.csv').open(encoding='utf-8')))
    bridge = []
    for case in [16,17]:
        original = list(csv.DictReader((SHORT/f'case{case}/{scene}-quality-per-frame.csv').open(encoding='utf-8')))
        modes = {14:audit.BASE,case:result['semantic_ids'][str(case)]}
        lookup = {(int(r['frame']),r['roi'],r['mode']):float(r['reference_rgb_mae']) for r in original}
        errors = [abs(float(r['reference_rgb_mae'])-lookup[(int(r['frame']),r['roi'],modes[int(r['case'])])])
                  for r in records if 60<=int(r['frame'])<180 and int(r['case']) in modes]
        assert max(errors)<1e-6
        bridge.append(dict(case=case,observations=len(errors),max_reference_mae_difference=max(errors),validation='PASS'))
    infos = {c:audit.load(LONG/f'case{c}/{scene}-long-capture.json') for c in [16,17]}
    sources = {14:(infos[16],audit.BASE),16:(infos[16],result['semantic_ids']['16']),17:(infos[17],result['semantic_ids']['17'])}
    retries,kept,media = [],{},[]
    names = ['thin-chair','windows'] if scene=='bistro' else ['thin-seam','leaves','grass-seam']
    crops = {n:{c:[] for c in audit.CASES} for n in names}
    for f in range(116,156):
        arrays = {c:audit.read_rgb(Path(info['capture_root'])/mode/f'frame_{f:05d}.png',info['output_hashes'][mode][f],retries)
                  for c,(info,mode) in sources.items()}
        if 124<=f<134:
            kept[f] = arrays
        for name in names:
            x0,y0,x1,y1 = audit.ROIS[scene][name]
            for c in audit.CASES:
                crops[name][c].append(Image.fromarray(arrays[c][y0:y1,x0:x1]))
    for name in names:
        scale = 4 if name=='thin-seam' else 2
        for pair in audit.PAIRS:
            frames = []
            for idx,f in enumerate(range(116,156)):
                w,h = crops[name][14][idx].size;w*=scale;h*=scale
                canvas = Image.new('RGB',(2*(w+8)+8,h+60),(18,20,23));draw=ImageDraw.Draw(canvas)
                for col,c in enumerate(pair):
                    x = 8+col*(w+8)
                    draw.text((x,5),f'{c} / JOff / w0.8',font=audit.FONT,fill='white')
                    draw.text((x,23),f'{scene} f{f}',font=audit.FONT,fill='white')
                    canvas.paste(crops[name][c][idx].resize((w,h),Image.Resampling.NEAREST),(x,48))
                frames.append(canvas)
            # One common palette for both panels, no tone change or interpolation.
            samples = Image.new('RGB',(frames[0].width,frames[0].height*4))
            for n,idx in enumerate([0,12,24,39]):samples.paste(frames[idx],(0,n*frames[0].height))
            palette = samples.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
            quantized = [f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
            path = OUT/f'{scene}-{name}-{pair[0]}-vs-{pair[1]}-f116-155-slow.gif'
            quantized[0].save(path,save_all=True,append_images=quantized[1:],duration=80,loop=0,optimize=False,disposal=2)
            with Image.open(path) as check:
                assert check.n_frames==40
                durations=[]
                for idx in range(40):check.seek(idx);check.load();durations.append(check.info['duration'])
                assert sum(durations)==3200
            media.append(dict(path=str(path),pair=pair,frames=[116,155],source_count=40,source_fps=60,
                              playback_fps=12.5,duration_s=3.2,scale=scale,filter='nearest',roi=audit.ROIS[scene][name],
                              role='Indexed GIF viewing aid, not quantitative source',validation='PASS'))
            for offset in [0,2,4,6,8]:
                fs = [124+offset,125+offset]
                result['sheets'].append(audit.sheet(scene,name,audit.ROIS[scene][name],fs,kept,pair,OUT,'extended-moving'))
    result['reference_bridge'] = bridge
    result['media'] = media
    result['supplemental_source_pngs_checked'] = 120
    result['supplemental_source_read_retries'] = retries
    (OUT/f'{scene}-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS supplementary',scene,'reference bridge and',len(media),'GIFs',flush=True)


if __name__=='__main__':
    for scene in ['bistro','minecraft']:finish(scene)
    parts = ['<!doctype html><meta charset="utf-8"><title>14 / 16 / 17 frame audit</title>',
             '<style>body{background:#151719;color:#eee;font:16px system-ui;margin:24px}img{max-width:100%;height:auto}section{margin:24px 0}a{color:#b8d9ff}</style>',
             '<h1>14 / 16 / 17: original-frame audit</h1><p>All Pattern Off, history 0.8. Lossless PNG sheets; nearest crop. GIF: f116..155 at 12.5fps, 3.2s (0.2083x). No brightness adjustment. Auxiliary metrics are not absolute flicker ground truth.</p>']
    for scene in ['bistro','minecraft']:
        result = audit.load(OUT/f'{scene}-audit.json')
        for item in result['media']:
            name = Path(item['path']).name
            parts.append(f'<section><h2>{html.escape(name)}</h2><img src="{html.escape(name)}"></section>')
        for name in audit.ROIS[scene]:
            parts.append(f'<h2>{scene} / {name}: lossless frames</h2>')
            for item in result['sheets']:
                if f'-{name}-' in Path(item['path']).name:
                    filename=Path(item['path']).name
                    parts.append(f'<section><p>{html.escape(filename)}</p><img loading="lazy" src="{html.escape(filename)}"></section>')
    (OUT/'comparison.html').write_text('\n'.join(parts),encoding='utf-8')
