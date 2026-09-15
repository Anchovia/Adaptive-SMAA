"""Derived comparison illustrations, excluded from quality metric inputs."""
from fractions import Fraction
import json
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw
from analyze_candidate_selection_gate import ROOT, OUT, read, paths, rgb

def main():
    runs={r['label']:r for r in read(OUT/'runs.json')};quality=read(OUT/'quality.json')
    old=read(ROOT/'tmp/source-comparison-analysis/comparison.json');records=[]
    target=ROOT/'Docs/Candidate-Selection-Gate-20260915';target.mkdir(parents=True,exist_ok=True)
    labels=['Supersample spatial reference','Standard SMAA T2X-R','Document candidate + document kernel','Source candidate + document kernel']
    for scene in ('bistro','minecraft'):
        sequences=[paths(Path(old['quality'][scene]['reference'])/'SS_Reference',480)]
        sequences += [paths(runs[f'{scene}-Quality-{k}']['report'],480) for k in ('O-T2X-R','profile-0','profile-1')]
        peak=quality['quality'][scene]['peak_candidate_disagreement']['frame']
        delta=np.abs(rgb(sequences[2][peak]).astype(float)-rgb(sequences[3][peak]).astype(float)).mean(axis=-1)
        _,x,y=max((float(delta[y:y+224,x:x+320].mean()),x,y) for y in range(0,1017-224+1,56) for x in range(0,1920-320+1,80))
        box=(x,y,x+320,y+224)
        def tile(n,full=False):
            out=Image.new('RGB',(960,736),'#121a24');draw=ImageDraw.Draw(out)
            for j,seq in enumerate(sequences):
                with Image.open(seq[n]) as im:
                    content=im.convert('RGB') if full else im.convert('RGB').crop(box)
                    content=content.resize((480,254) if full else (480,336))
                ox=(j%2)*480;oy=(j//2)*368
                out.paste(content,(ox,oy+30));draw.text((ox+8,oy+8),f'{labels[j]} | {n}',fill='white')
            return out
        tile(peak).save(OUT/f'{scene}-peak-crop.png');tile(peak,True).save(OUT/f'{scene}-full-frame.png')
        for window,indices in [('motion',range(max(60,peak-12),min(420,peak+12))),('transition',range(410,440))]:
            file=target/f'{scene}-{window}.mp4'
            with av.open(str(file),'w') as mux:
                s=mux.add_stream('libx264',rate=10);s.width=960;s.height=736;s.pix_fmt='yuv420p';s.options={'crf':'18','preset':'fast'}
                for i,n in enumerate(indices):
                    frame=av.VideoFrame.from_image(tile(n));frame.pts=i;frame.time_base=Fraction(1,10)
                    for p in s.encode(frame):mux.mux(p)
                for p in s.encode():mux.mux(p)
            with av.open(str(file)) as decoded:
                frames=list(decoded.decode(video=0));assert len(frames)==len(indices)
                assert all(abs(float(f.pts*f.time_base)-i/10)<1e-6 for i,f in enumerate(frames))
            records.append(dict(scene=scene,window=window,video=str(file),first_frame=indices.start,last_frame=indices.stop-1,
                frames=len(indices),fps=10,crop=box,peak_frame=peak,scope='6x slow H264 illustration; disagreement-selected fixed screen ROI, not object tracking or representative average'))
    (target/'media.json').write_text(json.dumps(records,indent=2))
    print('PASS: four comparison videos with decoded frame/PTS validation')
if __name__=='__main__':main()
