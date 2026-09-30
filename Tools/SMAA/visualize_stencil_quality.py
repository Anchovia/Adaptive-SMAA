"""Synchronized quality videos and original-pixel sequence sheets from pinned captures."""
import argparse,json
from functools import lru_cache
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageEnhance
from create_temporal_contrast_playback import encode,gif
from stencil_quality_common import DOC,OUT,SCENES,LABELS,manifest,sha,write_sources
from analyze_stencil_quality import ROIS

ORDER=['AA-Off','O-1X','ABL-TemporalOnly-R','O-T2X-R','Raw-Edge-Stencil-Off-R','Spatial-Edge-Stencil-Off-R']
DETAIL=['SS-Reference','O-1X','O-T2X-R','Spatial-Edge-Stencil-Off-R']
ISOLATE=['SS-Reference','O-T2X-R','Spatial-Full-Off-R','Spatial-Edge-Stencil-Off-R']
SHORT={'SS-Reference':'SS spatial reference','AA-Off':'1 AA-Off','O-1X':'2 SMAA 1X',
       'ABL-TemporalOnly-R':'3 Temporal-only','O-T2X-R':'4 Original T2X-R',
       'Raw-Edge-Stencil-Off-R':'5 Edge / no spatial','Spatial-Edge-Stencil-Off-R':'6 SMAA + edge',
       'Spatial-Full-Off-R':'Full temporal / jitter Off'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',required=True,choices=SCENES);scene=p.parse_args().scene
    data=manifest(scene);gate=json.loads((DOC/f'{scene}-cgvqm.json').read_text());assert gate['validation']=='PASS'
    paths={'SS-Reference':data['reference'],**data['sequences']}
    output=OUT/scene/'Playback';output.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    @lru_cache(maxsize=9)
    def frame(mode,i):
        with Image.open(paths[mode]/f'frame_{i:05d}.png') as im:return im.convert('RGB').copy()
    def render(i,modes,roi=None,scale=1,columns=2,gain=1.,slow=False):
        tw,th=(640,354) if roi is None else ((roi[2]-roi[0])*scale,(roi[3]-roi[1])*scale)
        rows=(len(modes)+columns-1)//columns;canvas=Image.new('RGB',(tw*columns,(th+30)*rows+32),'#11161d');draw=ImageDraw.Draw(canvas)
        draw.text((8,7),f'{scene} | frame {i:03d} | '+('MOVING' if 60<=i<180 else 'STILL')+f' | RGB display gain {gain:g}x | '+('0.5x playback' if slow else '60 FPS'),font=font,fill='white')
        for n,m in enumerate(modes):
            im=frame(m,i);im=im.resize((tw,th),Image.Resampling.LANCZOS) if roi is None else im.crop(roi).resize((tw,th),Image.Resampling.NEAREST)
            if gain!=1:im=ImageEnhance.Brightness(im).enhance(gain)
            x=(n%columns)*tw;y=(n//columns)*(th+30)+32
            draw.text((x+7,y+5),SHORT[m],font=font,fill='white');canvas.paste(im,(x,y+30))
        return canvas
    artifacts=[]
    def video(name,render_frame):
        result=encode(output/(name+'.mp4'),render_frame,240)
        result['sha256']=sha(Path(result['path']));artifacts.append(result);print(f'PASS {scene} {name}',flush=True)
    video('six-cases-overview-60fps',lambda i:render(i,ORDER,columns=3))
    primary=ROIS[scene]['chair-legs' if scene=='bistro' else 'foliage'];gain=3 if scene=='bistro' else 1
    video('thin-detail-60fps',lambda i:render(i,DETAIL,primary,2,gain=gain))
    video('pattern-selection-60fps',lambda i:render(i,ISOLATE,primary,2,gain=gain))
    boundary=ROIS[scene]['foreground-boundary']
    video('boundary-detail-60fps',lambda i:render(i,DETAIL,boundary,2,gain=gain))
    for label,indices in [('moving',[110,111,112,113]),('stopping',[179,180,181,182]),('late-still',[200,201,202,203])]:
        roi=primary;l,t,r,b=roi;w,h=r-l,b-t
        sheet=Image.new('RGB',(w*4,(h+28)*len(DETAIL)+36),'#11161d');draw=ImageDraw.Draw(sheet)
        draw.text((8,7),f'{scene} | {label} | source-size crop | RGB gain {gain}x',font=font,fill='white')
        for row,m in enumerate(DETAIL):
            for col,i in enumerate(indices):
                tile=ImageEnhance.Brightness(frame(m,i).crop(roi)).enhance(gain)
                x=col*w;y=36+row*(h+28);draw.text((x+5,y+3),f'{SHORT[m]} / f{i}',font=font,fill='white');sheet.paste(tile,(x,y+28))
        path=output/(label+'-sequence.png');sheet.save(path);artifacts.append(dict(path=str(path),sha256=sha(path),kind='sequence-png',frames=indices))
    for name,roi in ROIS[scene].items():
        path=output/(name+'-frame110.png');render(110,ISOLATE,roi,2,gain=gain).save(path)
        artifacts.append(dict(path=str(path),sha256=sha(path),kind='comparison-png',frame=110,roi=roi))
    for name,first,end in [('moving-half-speed',90,150),('transition-half-speed',160,220)]:
        item=gif(output/(name+'.gif'),lambda i,slow=False:render(i,DETAIL,primary,1,gain=gain,slow=slow),first,end)
        item['sha256']=sha(Path(item['path']));artifacts.append(item)
    result=dict(validation='PASS',scene=scene,artifacts=artifacts,rois=ROIS[scene],primary_roi=primary,
                overview_order=ORDER,detail_order=DETAIL,isolation_order=ISOLATE,detail_display_gain=gain,
                scope='Visualization only: MP4 CRF12 YUV420, fixed-palette GIF, nearest 2x ROI enlargement. All quantitative metrics use unmodified PNG. Screen-fixed ROIs; camera motion only.')
    (DOC/f'{scene}-visuals.json').write_text(json.dumps(result,indent=2)+'\n');write_sources(f'{scene}-visual-sources.json')


if __name__=='__main__':main()
