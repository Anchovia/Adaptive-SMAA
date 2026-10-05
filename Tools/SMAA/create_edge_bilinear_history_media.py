"""ROI GIF and constant60 MP4 for human review; original PNGs remain authoritative."""
import json
from pathlib import Path
from fractions import Fraction
import av
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from analyze_edge_bilinear_history_rgb import ROOT,DOC,MODES,ROIS,sheets
from edge_quality_inputs import sha

def main():
    media=ROOT/'tmp/edge-bilinear-history-rgb-media';media.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',12);records=[]
    short_labels=['4 Original ON','6 Current OFF','9 Previous OFF','10 Linear OFF']
    for scene in ['bistro','minecraft']:
        q=json.loads((DOC/f'{scene}-capture.json').read_text());capture=Path(q['capture_root'])
        sheets(capture,Path(q['reference_root']),scene,media)
        roi='chair' if scene=='bistro' else 'wall-seam';box=ROIS[scene][roi]
        w=(box[2]-box[0])*2;h=(box[3]-box[1])*2;size=(4*(w+8)+8,h+54)
        frames=[]; mp4=media/f'{scene}-sampler-60fps.mp4';gif=media/f'{scene}-sampler-slow.gif'
        with av.open(str(mp4),'w') as out:
            stream=out.add_stream('libx264',rate=60);stream.width=size[0];stream.height=size[1]
            stream.pix_fmt='yuv420p';stream.options={'crf':'14','preset':'medium','threads':'1'}
            for f in range(60,240):
                canvas=Image.new('RGB',size,(18,20,23));draw=ImageDraw.Draw(canvas)
                for col,(m,label) in enumerate(zip(MODES,short_labels)):
                    x=8+col*(w+8);draw.text((x,6),label,fill='white',font=font)
                    draw.text((x,24),f'f{f} / nearest2x',fill='white',font=font)
                    with Image.open(capture/m/f'frame_{f:05d}.png') as im:crop=im.crop(box).resize((w,h),Image.Resampling.NEAREST)
                    canvas.paste(crop,(x,50))
                frames.append(canvas)
                frame=av.VideoFrame.from_ndarray(np.asarray(canvas),format='rgb24');frame.pts=f-60;frame.time_base=Fraction(1,60)
                for packet in stream.encode(frame):out.mux(packet)
            for packet in stream.encode():out.mux(packet)
        # One common palette avoids independent-palette color pumping. GIF is lossy aid.
        palette=Image.new('RGB',(size[0]*6,size[1]))
        for i,k in enumerate([0,30,60,90,120,179]):palette.paste(frames[k],(size[0]*i,0))
        palette=palette.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
        gifframes=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
        gifframes[0].save(gif,save_all=True,append_images=gifframes[1:],duration=40,loop=0,optimize=False,disposal=2)
        with av.open(str(mp4)) as inp:
            s=inp.streams.video[0];pts=[float(f.pts*f.time_base) for f in inp.decode(s)]
            assert len(pts)==180 and s.average_rate==60 and all(b>a for a,b in zip(pts,pts[1:]))
        with Image.open(gif) as im:
            duration=0;count=im.n_frames
            for i in range(count):im.seek(i);duration+=im.info['duration']
            assert count==180 and duration==7200
        records.append(dict(scene=scene,roi=box,frames=[60,239],frame_count=180,scale=2,filter='nearest',tone_adjustment=False,mode_order=MODES,mp4=str(mp4),mp4_sha256=sha(mp4),mp4_fps=60,mp4_verified_frames=180,mp4_monotonic_pts=True,gif=str(gif),gif_sha256=sha(gif),gif_fps=25,gif_duration_ms=7200,gif_palette='shared256; lossy presentation only',inspection='Decoded/verified. No claim of realtime playback viewed; PNG sheets are direct visual evidence.'))
    (DOC/'media.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print('PASS: two ROI videos/GIFs verified')

if __name__=='__main__':main()
