"""Encode derived ROI illustrations; never used as metric inputs."""
from pathlib import Path
from fractions import Fraction
import json
import av
from PIL import Image, ImageSequence

repo=Path(__file__).resolve().parents[2]
root=repo/'tmp/recovered-clipping/analysis';out=repo/'Docs/Recovered-Clipping-Ablation-20260915'
out.mkdir(parents=True,exist_ok=True)
records=[]
for source in sorted(root.glob('*.gif')):
    target=out/(source.stem+'.mp4')
    with Image.open(source) as gif,av.open(str(target),'w') as mux:
        assert gif.info['duration']==100
        s=mux.add_stream('libx264',rate=10);s.width,s.height=gif.size;s.pix_fmt='yuv420p'
        s.options={'crf':'18','preset':'fast'};count=0
        for i,im in enumerate(ImageSequence.Iterator(gif)):
            f=av.VideoFrame.from_image(im.convert('RGB'));f.pts=i;f.time_base=Fraction(1,10)
            for packet in s.encode(f):mux.mux(packet)
            count+=1
        for packet in s.encode():mux.mux(packet)
    with av.open(str(target)) as decoded:
        frames=list(decoded.decode(video=0));assert len(frames)==count
        assert all(abs(float(f.pts*f.time_base)-i/10)<1e-6 for i,f in enumerate(frames))
    records.append(dict(source=str(source),video=str(target),frames=count,fps=10,
        presentation='6x slow motion relative to 60-Hz capture; lossy H.264 viewing copy, excluded from metrics'))
(out/'media.json').write_text(json.dumps(records,indent=2))
