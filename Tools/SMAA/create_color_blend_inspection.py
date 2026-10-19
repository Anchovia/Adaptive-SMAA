"""Original-pixel inspection sheets and two-way GIFs for the case-17 cleanup.

Sheets paste lossless PNG crops with nearest-neighbour scaling only (no tone
change). Amplified differences are drawn in separate, labelled rows. GIFs are
palette-converted viewing aids; the PNG frames remain the reference.
"""
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from verify_color_blend_preservation import receipt,CASE17,NATIVE
from verify_color_blend_optimization import receipt as optimization_receipt

ROIS={'bistro':{'thin-chair':(1230,582,1358,670),'chairs':(1230,546,1358,706),'windows':(950,460,1110,588)},
      'minecraft':{'thin-seam':(956,524,1020,620),'seams':(932,512,1060,672),'leaves':(1420,590,1580,718),'grass-seam':(1450,665,1552,719)}}
WINDOWS={'moving':list(range(126,132)),'transition':list(range(178,184)),'failure-window':list(range(124,134)),'settled':[230]}
try:FONT=ImageFont.truetype('arial.ttf',14)
except OSError:FONT=ImageFont.load_default()

def root(label,scene,harness='Preservation'):
    if harness=='Optimization':
        r,_,_=optimization_receipt(label,scene,harness);return Path(r['capture_root'])
    r,_=receipt(label,scene,'Capture');return Path(r['capture_root'])
def rgb(p):
    with Image.open(p) as im:assert im.mode=='RGB';return np.asarray(im).copy()
def sheet(rows,frames,roi,scale,title,path):
    x0,y0,x1,y1=roi;w,h=(x1-x0)*scale,(y1-y0)*scale
    img=Image.new('RGB',(16+w*len(frames)+8*(len(frames)-1),40+len(rows)*(h+24)),(24,24,24));d=ImageDraw.Draw(img)
    d.text((8,8),title,font=FONT,fill=(235,235,235))
    for r,(name,get) in enumerate(rows):
        y=40+r*(h+24);d.text((8,y),name,font=FONT,fill=(235,235,235))
        for c,f in enumerate(frames):
            a=get(f)[y0:y1,x0:x1];img.paste(Image.fromarray(a).resize((w,h),Image.Resampling.NEAREST),(8+c*(w+8),y+20))
    img.save(path);return dict(path=str(path),sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),frames=frames,roi=list(roi),scale=scale,filter='nearest')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--before',required=True);ap.add_argument('--after',required=True);ap.add_argument('--after-name',default='17 cleanup')
    ap.add_argument('--after-harness',choices=['Preservation','Optimization'],default='Preservation')
    ap.add_argument('--after-mode',default=CASE17)
    ap.add_argument('--out',required=True);x=ap.parse_args();out=Path(x.out);out.mkdir(parents=True,exist_ok=True);manifest=[]
    for scene,rois in ROIS.items():
        rb,ra=root(x.before,scene),root(x.after,scene,x.after_harness)
        load=lambda base,mode:(lambda f:rgb(base/mode/f'frame_{f:05d}.png'))
        before,after,native=load(rb,CASE17),load(ra,x.after_mode),load(ra,NATIVE)
        def diff(f,amp=16):
            d=np.abs(before(f).astype(np.int16)-after(f).astype(np.int16))*amp;return np.clip(d,0,255).astype(np.uint8)
        for roi_name,roi in rois.items():
            scale=3 if roi_name in ('thin-seam','thin-chair','grass-seam') else 2
            for win,frames in WINDOWS.items():
                rows=[(f'17 before ({x.before}) original',before),(f'{x.after_name} ({x.after}) original',after),('4 native T2X-R (pattern On) original',native),
                      ('|17 before - 17 after| x16 (amplified difference, not an image)',diff)]
                title=f'{scene} {roi_name} {win} f{frames[0]}..{frames[-1]}; nearest {scale}x; 17 pattern Off, 4 pattern On'
                manifest.append(dict(scene=scene,roi_name=roi_name,window=win,**sheet(rows,frames,roi,scale,title,out/f'{scene}-{roi_name}-{win}.png')))
        for f in (130,181,230):
            for mode,get in [('case17-selected',after),('case4',native)]:
                p=out/f'{scene}-full-f{f}-{mode}.png';Image.fromarray(get(f)).save(p)
                manifest.append(dict(scene=scene,frame=f,mode=mode,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),kind='full frame copy'))
        # Two-way playback: case 4 | case 17 cleanup, f60..209 every frame, 30 fps file = 0.5x of 60 Hz capture.
        roi=rois['thin-seam' if scene=='minecraft' else 'thin-chair'];x0,y0,x1,y1=roi;s=3;w,h=(x1-x0)*s,(y1-y0)*s;frames=[]
        for f in range(60,210):
            img=Image.new('RGB',(w*2+24,h+30),(24,24,24));d=ImageDraw.Draw(img)
            d.text((8,6),f'f{f}  4 native (On)',font=FONT,fill=(235,235,235));d.text((16+w,6),f'{x.after_name} (Off)',font=FONT,fill=(235,235,235))
            img.paste(Image.fromarray(native(f)[y0:y1,x0:x1]).resize((w,h),Image.Resampling.NEAREST),(8,26))
            img.paste(Image.fromarray(after(f)[y0:y1,x0:x1]).resize((w,h),Image.Resampling.NEAREST),(16+w,26))
            frames.append(img)
        gif=out/f'{scene}-{"thin-seam" if scene=="minecraft" else "thin-chair"}-4-vs-17selected.gif'
        # GIF durations are multiples of 10 ms. 30/30/40 yields 5000 ms for
        # these 150 source frames, exactly 0.5x playback on average.
        durations=[(30,30,40)[i%3] for i in range(len(frames))]
        frames[0].save(gif,save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=False)
        with Image.open(gif) as g:
            n=g.n_frames;duration_ms=0
            for i in range(n):g.seek(i);duration_ms+=g.info['duration']
        assert duration_ms==5000,(gif,duration_ms)
        manifest.append(dict(scene=scene,path=str(gif),sha256=hashlib.sha256(gif.read_bytes()).hexdigest(),frames=n,first=60,last=209,
            duration_ms=duration_ms,duration_pattern_ms=[30,30,40],speed='0.5x average of 60 Hz capture',
            after_mode=x.after_mode,after_harness=x.after_harness,kind='palette GIF viewing aid; PNG is the reference'))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=1)+'\n',encoding='utf-8');print('PASS',len(manifest))
if __name__=='__main__':main()
