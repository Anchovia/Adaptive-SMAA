"""Lossless case18/case19 comparison sheets; GIFs are palette viewing aids."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from create_color_blend_inspection import ROIS, WINDOWS, FONT, rgb
from verify_color_blend_optimization import receipt
from verify_case19_spatial import MODES, CASE18

def sheet(rows,frames,roi,scale,title,path):
    x0,y0,x1,y1=roi;w,h=(x1-x0)*scale,(y1-y0)*scale
    im=Image.new('RGB',(max(800,16+(w+8)*len(frames)-8),40+len(rows)*(h+24)),(24,24,24));draw=ImageDraw.Draw(im)
    draw.text((8,8),title,font=FONT,fill=(235,235,235))
    for index,(name,load) in enumerate(rows):
        y=40+index*(h+24);draw.text((8,y),name,font=FONT,fill=(235,235,235))
        for col,frame in enumerate(frames):
            crop=Image.fromarray(load(frame)[y0:y1,x0:x1]).resize((w,h),Image.Resampling.NEAREST)
            im.paste(crop,(8+col*(w+8),y+20))
    im.save(path)
    return dict(path=str(path),sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),frames=frames,roi=list(roi),scale=scale,filter='nearest')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--out',required=True);x=ap.parse_args()
    out=Path(x.out);out.mkdir(parents=True,exist_ok=True);manifest=[]
    for scene in ('bistro','minecraft'):
        r,base,_=receipt(x.label,scene,'Case19')
        get=lambda mode:lambda f:rgb(base/mode/f'frame_{f:05d}.png')
        native,old,new=get(MODES[0]),get(CASE18),get(MODES[-1])
        def diff(f):return np.clip(np.abs(old(f).astype(np.int16)-new(f).astype(np.int16))*16,0,255).astype(np.uint8)
        roi_name='thin-chair' if scene=='bistro' else 'thin-seam';roi=ROIS[scene][roi_name]
        for window,frames in WINDOWS.items():
            rows=[('4 native T2X-R (paired pattern On)',native),('18 (pattern Off)',old),
                  ('19 RGBA8 + Gather (pattern Off)',new),('|18 - 19| x16 (amplified difference)',diff)]
            manifest.append(dict(scene=scene,window=window,**sheet(rows,frames,roi,3,
                f'{scene} {roi_name} f{frames[0]}..{frames[-1]}; original pixels, nearest 3x',out/f'{scene}-{window}.png')))
        for frame in (130,181,230):
            for name,load in [('case18',old),('case19-combined',new)]:
                p=out/f'{scene}-full-f{frame}-{name}.png';Image.fromarray(load(frame)).save(p)
                manifest.append(dict(scene=scene,frame=frame,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),kind='lossless full frame copy'))
        x0,y0,x1,y1=roi;w,h=(x1-x0)*3,(y1-y0)*3;frames=[]
        for frame in range(60,210):
            im=Image.new('RGB',(24+w*3,h+32),(24,24,24));draw=ImageDraw.Draw(im)
            for col,(name,load) in enumerate([('4',native),('18',old),('19 combined',new)]):
                draw.text((8+col*(w+4),4),f'f{frame} {name}',font=FONT,fill=(235,235,235))
                im.paste(Image.fromarray(load(frame)[y0:y1,x0:x1]).resize((w,h),Image.Resampling.NEAREST),(8+col*(w+4),28))
            frames.append(im)
        p=out/f'{scene}-4-18-19.gif';durations=[(30,30,40)[i%3] for i in range(150)]
        frames[0].save(p,save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=False)
        with Image.open(p) as gif:
            count=gif.n_frames;duration=0
            for i in range(count):gif.seek(i);duration+=gif.info['duration']
        assert duration==5000
        manifest.append(dict(scene=scene,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),frames=count,
            duration_ms=duration,source_frames=[60,209],playback='0.5x average of fixed 60 Hz capture',kind='palette viewing aid; PNG is reference',receipt=r))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=1)+'\n',encoding='utf-8')
    print(f'PASS: {len(manifest)} inspection artifacts')
if __name__=='__main__':main()
