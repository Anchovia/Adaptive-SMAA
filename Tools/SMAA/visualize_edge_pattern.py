"""Qualitative static-phase panels and 60 FPS moving crop video; no quantitative scoring on encodes."""
import json,shutil,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from analyze_edge_pattern import D,ITEM,FULL,SEL,ONSEL,ONFULL,image,sha
def main():
    allresults={}
    for scene in ['bistro','minecraft']:
        q=json.loads((D/f'{scene}-capture.json').read_text());cap=Path(q['capture']);old=Path(q['prior']);native=Path(q.get('native_baseline',q['prior']))
        out=cap/'visuals';out.mkdir(exist_ok=True)
        a,b=[image(old/ONSEL/f'frame_{i:05d}.png') for i in [220,221]]
        delta=np.abs(a.astype(np.int16)-b.astype(np.int16)).mean(axis=2);size=320
        score,x,y=max((float(delta[y:y+size,x:x+size].mean()),x,y) for y in range(0,1061-size+1,64) for x in range(0,1920-size+1,64));box=(x,y,x+size,y+size)
        sources=[(native/'AA-Off','AA-Off (no spatial AA)'),(old/ONFULL,'Full temporal only (pattern ON)'),(old/ONSEL,f'Item {ITEM} pattern ON'),(cap/SEL,f'Item {ITEM} pattern OFF')]
        def panel(i,subtitle):
            p=Image.new('RGB',(1280,376),'#18202a');draw=ImageDraw.Draw(p)
            for col,(folder,label) in enumerate(sources):
                with Image.open(folder/f'frame_{i:05d}.png') as im:p.paste(im.crop(box),(col*size,56))
                draw.text((col*size+8,8),label,fill='white')
            draw.text((8,32),f'{scene} / frame {i} / 1:1 crop ({x},{y}) / {subtitle}',fill='#ccd5df');return p
        panels=[panel(i,'Static diagnostic: slowed to 4 FPS') for i in [220,221]]
        atlas=Image.new('RGB',(1280,752))
        for j,p in enumerate(panels):p.save(out/f'static-{220+j}.png');atlas.paste(p,(0,j*376))
        pal=atlas.quantize(colors=256);frames=[p.quantize(palette=pal,dither=Image.Dither.NONE) for p in panels]
        gif=out/'static-pattern-on-off.gif';frames[0].save(gif,save_all=True,append_images=frames[1:],duration=250,loop=0,optimize=False,disposal=2)
        with Image.open(gif) as im:assert im.n_frames==2
        ffmpeg=shutil.which('ffmpeg');assert ffmpeg
        video=out/'moving-pattern-on-off.mp4'
        cmd=[ffmpeg,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1280x376','-r','60','-i','-','-an','-c:v','libx264','-crf','16','-preset','medium','-pix_fmt','yuv420p',str(video)]
        with subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE) as proc:
            for i in range(60,180):proc.stdin.write(panel(i,'Moving comparison: native 60 FPS').tobytes())
            proc.stdin.close();error=proc.stderr.read();assert proc.wait(timeout=120)==0,error
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames,avg_frame_rate,width,height','-of','json',str(video)]))['streams'][0]
        assert probe['nb_read_frames']=='120' and probe['avg_frame_rate']=='60/1'
        allresults[scene]=dict(crop=[x,y,size,size],selection='maximum ON adjacent-frame delta over fixed 64px grid in late still frames 220/221',on_roi_rgb_step=score,gif=str(gif),png=str(out/'static-220.png'),video=str(video),video_sha256=sha(video),probe=probe,note='Diagnostic crop chosen for old static artifact, not representative of all moving features. Lossy playback is qualitative only.')
    (D/'visual-provenance.json').write_text(json.dumps(allresults,indent=2)+'\n');print('PASS: visual artifacts generated and decoded')
if __name__=='__main__':main()
