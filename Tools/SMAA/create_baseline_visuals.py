"""Visual controls from the independent baseline; no edge-selective mode."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageEnhance,ImageFont
from create_temporal_contrast_playback import encode,gif
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Baseline-Restart'
def main():
    records=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    for scene in ['bistro','minecraft']:
        q=json.loads((DOC/f'{scene}-capture.json').read_text());assert q['validation']=='PASS'
        cap=Path(q['capture']);out=ROOT/'Projects/CMAA2/AutoBench/BaselineRestart'/scene/'Playback';out.mkdir(parents=True,exist_ok=True)
        roi=(360,590,720,830) if scene=='bistro' else (300,520,660,760);gain=3 if scene=='bistro' else 1
        modes=['AA-Off','O-1X','O-T2X-R'];labels=['AA OFF (no jitter)','Original SMAA 1X (no jitter)','Original T2X-R']
        frames={}
        for i in range(160,220):
            frames[i]=[]
            for m in modes:
                with Image.open(cap/m/f'frame_{i:05d}.png') as im:frames[i].append(im.crop(roi))
        def render(i,slow=False):
            canvas=Image.new('RGB',(1080,304),'#15181c');d=ImageDraw.Draw(canvas)
            d.text((7,3),f'{scene} | f{i:03d} | '+('MOVING' if i<180 else 'STILL')+f' | RGB gain {gain}x | '+('0.5x' if slow else '1x / 60 FPS'),font=font,fill='white')
            for j,(tile,label) in enumerate(zip(frames[i],labels)):
                d.text((j*360+7,33),label,font=font,fill='white');canvas.paste(ImageEnhance.Brightness(tile).enhance(gain),(j*360,64))
            return canvas
        g=gif(out/'baseline-transition.gif',render,160,220);v=encode(out/'baseline-transition-60fps.mp4',lambda i:render(160+i),60)
        render(200).save(out/'baseline-still.png')
        records.append(dict(scene=scene,roi=roi,gain=gain,gif=g,mp4=v,order=modes))
        print('PASS baseline playback: '+scene,flush=True)
    (DOC/'playback.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
