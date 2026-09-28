"""Two-frame, shared-palette static diagnostic. Deliberately slowed, not quality scoring."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from analyze_first_edge_only import R, D, FULL, SEL, NATIVE, edges, image


def main():
    output = R/'tmp/first-edge-only-visuals'
    output.mkdir(exist_ok=True)
    records = {}
    for scene in ['bistro', 'minecraft']:
        data = json.loads((D/f'{scene}-capture.json').read_text())
        cap = Path(data['capture'])
        a, b = [image(cap/SEL/f'frame_{i:05d}.png') for i in [220, 221]]
        delta = np.abs(a.astype(np.int16)-b.astype(np.int16)).mean(axis=2)
        # Deterministic display ROI: maximal mean adjacent RGB change on a 64px grid.
        size = 320
        score, x, y = max((float(delta[y:y+size,x:x+size].mean()), x, y)
                          for y in range(0,1061-size+1,64) for x in range(0,1920-size+1,64))
        panels = []
        for i in [220,221]:
            p = Image.new('RGB',(size*4, size+56),'#181c23')
            draw = ImageDraw.Draw(p)
            for column, (mode,label) in enumerate([(NATIVE,'Original SMAA T2X-R'),(FULL,'Temporal-only full screen'),(SEL,'First-edge temporal-only')]):
                im = Image.fromarray(image(cap/mode/f'frame_{i:05d}.png')).crop((x,y,x+size,y+size))
                p.paste(im,(column*size,56));draw.text((column*size+8,8),label,fill='white')
            mask = np.any(edges(cap/SEL/f'frame_{i:05d}-edge.rg8')>0,axis=2).astype(np.uint8)*255
            p.paste(Image.fromarray(mask).convert('RGB').crop((x,y,x+size,y+size)),(size*3,56))
            draw.text((size*3+8,8),'Actual first-pass edge mask',fill='white')
            draw.text((8,30),f'{scene} | static frame {i} | crop ({x},{y}) | 1:1 pixels | GIF slowed to 4 FPS',fill='#ced6e0')
            p.save(output/f'{scene}-frame-{i}.png')
            panels.append(p)
        # One palette for both phases avoids phase-specific GIF quantization.
        atlas = Image.new('RGB',(size*4,2*(size+56)))
        for k,p in enumerate(panels):atlas.paste(p,(0,k*(size+56)))
        palette = atlas.quantize(colors=256)
        frames = [p.quantize(palette=palette,dither=Image.Dither.NONE) for p in panels]
        gif = output/f'{scene}-static-phases.gif'
        frames[0].save(gif,save_all=True,append_images=frames[1:],duration=250,loop=0,optimize=False,disposal=2)
        with Image.open(gif) as verify:
            assert verify.n_frames == 2
            assert verify.info['duration'] == 250
        records[scene] = dict(capture=str(cap),frames=[220,221],crop=[x,y,size,size],roi_rgb_step=score,
                              selection='maximum mean selective adjacent-RGB difference over fixed 64px grid',
                              gif=str(gif),gif_sha256=hashlib.sha256(gif.read_bytes()).hexdigest(),
                              note='Shared 256-color palette, 4 FPS slowed diagnostic; exact RGB PNG panels retained. Not ground truth or a representative average.')
    (D/'visual-provenance.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(records,indent=2))


if __name__ == '__main__':main()
