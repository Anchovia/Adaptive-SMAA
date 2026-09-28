"""Matched 60-FPS playback and fixed-palette slow GIFs for artifact inspection."""
import argparse
import json
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

def encode(path,render,n,fps=60):
    sample=render(0);w,h=sample.size
    with av.open(str(path),'w',format='mp4') as out:
        stream=out.add_stream('libx264',rate=Fraction(fps));stream.width=w;stream.height=h
        stream.pix_fmt='yuv420p';stream.options={'crf':'12','preset':'fast'}
        stream.time_base=Fraction(1,fps)
        for i in range(n):
            frame=av.VideoFrame.from_ndarray(np.asarray(render(i)),format='rgb24')
            frame.pts=i;frame.time_base=Fraction(1,fps)
            for packet in stream.encode(frame):out.mux(packet)
        for packet in stream.encode():out.mux(packet)
    with av.open(str(path)) as inp:
        s=inp.streams.video[0];assert s.average_rate==Fraction(fps)
        stamps=[f.pts*s.time_base for f in inp.decode(video=0)]
        assert len(stamps)==n and all(b-a==Fraction(1,fps) for a,b in zip(stamps,stamps[1:]))
    return {'path':str(path.resolve()),'frames':n,'fps':fps,'size':[w,h],'pts_verified':True}

def gif(path,render,start,end):
    frames=[render(i,slow=True) for i in range(start,end)]
    # One shared palette and no dithering avoid independent palette changes
    # being mistaken for temporal instability; GIF still has color loss.
    samples=frames[::max(1,len(frames)//6)]
    atlas=Image.new('RGB',(frames[0].width,frames[0].height*len(samples)))
    for i,f in enumerate(samples):atlas.paste(f,(0,i*f.height))
    palette=atlas.quantize(colors=256,dither=Image.Dither.NONE)
    indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
    durations=[(30,30,40)[i%3] for i in range(len(frames))]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=durations,loop=0,disposal=2,optimize=False)
    with Image.open(path) as im:
        assert im.n_frames==len(frames)
        actual=[]
        for i in range(im.n_frames):im.seek(i);actual.append(im.info['duration'])
        assert actual==durations
    return {'path':str(path.resolve()),'source_frames':[start,end-1],'playback_speed':0.5,'duration_ms':sum(durations),'fixed_palette':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analysis',type=Path,required=True);a=p.parse_args()
    q=json.loads((a.analysis/'reference-quality.json').read_text());assert q['native_and_mask_bridge']==480
    source=Path(q['capture']);reference=Path(q['quality_capture'])
    paths=[reference/'SS-Reference',source/'O-T2X-R',source/'ABL-Contrast-001-R']
    labels=['SS spatial reference','Original T2X-R','Contrast 0.01 T2X-R']
    roi=(420,590,900,910) if q['scene']=='bistro' else (720,240,1200,560)
    out=a.analysis/'Playback';out.mkdir(exist_ok=True)
    def render(i,crop=False,slow=False):
        tw,th=(480,320) if crop else (640,354)
        canvas=Image.new('RGB',(tw*3,th+30),'#15181c');draw=ImageDraw.Draw(canvas)
        for col,(folder,label) in enumerate(zip(paths,labels)):
            with Image.open(folder/f'frame_{i:05d}.png') as im:
                tile=im.convert('RGB').crop(roi) if crop else im.convert('RGB').resize((tw,th),Image.Resampling.LANCZOS)
                canvas.paste(tile,(col*tw,30))
            draw.text((col*tw+5,8),f'{label} | f{i:03d} | '+('0.5x' if slow else '1x'),fill='white')
        return canvas
    metadata={'scene':q['scene'],'roi':roi,'order':labels,'threshold':.01,
              'scope':'Visual inspection only: MP4 uses CRF12 YUV420, GIF uses fixed 256-color palette. Inspect original PNG for disputed pixel-level details. ROI is screen-fixed, not object-tracked.', 'videos':[],'gifs':[]}
    metadata['videos'].append(encode(out/'overview-60fps.mp4',render,240))
    print(q['scene']+' overview PASS',flush=True)
    detail=lambda i,slow=False:render(i,crop=True,slow=slow)
    metadata['videos'].append(encode(out/'detail-60fps.mp4',detail,240))
    for name,start,end in [('moving-detail-half-speed',90,150),('transition-detail-half-speed',160,220),('late-still-detail-half-speed',200,220)]:
        metadata['gifs'].append(gif(out/(name+'.gif'),detail,start,end))
    # Adjacent original RGB crops support inspection independently of video compression.
    for name,indices in [('moving',[110,111,112,113]),('stop',[179,180,181,182]),('still',[200,201,202,203])]:
        sheet=Image.new('RGB',(4*480,3*350),'#15181c')
        for col,i in enumerate(indices):
            frame=detail(i)
            for row in range(3):sheet.paste(frame.crop((row*480,0,(row+1)*480,350)),(col*480,row*350))
        sheet.save(out/(name+'-sequence.png'))
    (out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(q['scene']+' PASS: 2 matched 60fps videos, 3 GIFs, 3 sequence sheets',flush=True)

if __name__=='__main__':main()
