"""Static phase diagnostic with real 1X/native T2X-R controls and exact first edges."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from analyze_spatial_first_edge import R,D,FULL,SEL,edges,image
def main():
    out=R/'tmp/spatial-first-edge-visuals';out.mkdir(exist_ok=True);records={}
    for scene in ['bistro','minecraft']:
        cap=Path(json.loads((D/f'{scene}-capture.json').read_text())['capture'])
        a,b=[image(cap/SEL/f'frame_{i:05d}.png') for i in [220,221]]
        delta=np.abs(a.astype(np.int16)-b.astype(np.int16)).mean(axis=2);size=320
        score,x,y=max((float(delta[y:y+size,x:x+size].mean()),x,y) for y in range(0,1061-size+1,64) for x in range(0,1920-size+1,64))
        panels=[]
        for i in [220,221]:
            p=Image.new('RGB',(size*4,size+56),'#181c23');draw=ImageDraw.Draw(p)
            for col,(mode,label) in enumerate([('O-1X','Original SMAA 1X (no jitter)'),(FULL,'Original spatial + full T2X-R'),(SEL,'Spatial SMAA + edge temporal')]):
                im=Image.fromarray(image(cap/mode/f'frame_{i:05d}.png')).crop((x,y,x+size,y+size));p.paste(im,(col*size,56));draw.text((col*size+8,8),label,fill='white')
            mask=np.any(edges(cap/SEL/f'frame_{i:05d}-edge.rg8')>0,axis=2).astype(np.uint8)*255
            p.paste(Image.fromarray(mask).convert('RGB').crop((x,y,x+size,y+size)),(size*3,56));draw.text((size*3+8,8),'Actual first-pass edge mask',fill='white')
            draw.text((8,30),f'{scene} | static frame {i} | crop ({x},{y}) | 1:1 pixels | GIF slowed to 4 FPS',fill='#ced6e0')
            p.save(out/f'{scene}-frame-{i}.png');panels.append(p)
        atlas=Image.new('RGB',(size*4,2*(size+56)))
        for k,p in enumerate(panels):atlas.paste(p,(0,k*(size+56)))
        palette=atlas.quantize(colors=256);frames=[p.quantize(palette=palette,dither=Image.Dither.NONE) for p in panels]
        gif=out/f'{scene}-static-phases.gif';frames[0].save(gif,save_all=True,append_images=frames[1:],duration=250,loop=0,optimize=False,disposal=2)
        with Image.open(gif) as verify:assert verify.n_frames==2 and verify.info['duration']==250
        records[scene]=dict(capture=str(cap),frames=[220,221],crop=[x,y,size,size],roi_rgb_step=score,gif=str(gif),gif_sha256=hashlib.sha256(gif.read_bytes()).hexdigest(),
            selection='maximum mean adjacent selective RGB change over a fixed 64px grid',note='Shared 256-color palette, slowed 4 FPS; exact RGB PNG panels retained. Real 1X has no jitter; not a same-sample reference or quality score.')
    (D/'visual-provenance.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8');print('PASS: two-scene static diagnostic PNG/GIF generated and decoded')
if __name__=='__main__':main()
