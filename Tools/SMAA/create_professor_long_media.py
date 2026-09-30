"""Presentation-only, eight independently rendered cases on a genuine 480-frame path."""
import gc,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw
from create_professor_short_media import ROOT,OUT,MEDIA,FONT,SMALL,BG,LABELS,gif_pair,encode_mp4

def collect(scene):
    records={}
    for key in ('audit','1','2','3','5'):
        r=json.loads((ROOT/f'tmp/professor-case{key}-{scene}-validated.json').read_text())
        assert r['validation']=='PASS' and r['frames']==480
        assert r['native_control_all_frames_equal']
        if key=='audit':
            mapping={4:'O-T2X-R',6:'A-CurrentEdge-Stencil',7:'B-PreviousRawEdge-Depth',8:'E-PreviousRawEdge-FirstStencil'}
        else:
            target=[m for m in r['modes'] if m!='O-T2X-R']
            assert len(target)==1
            mapping={int(key):target[0]}
        for case,mode in mapping.items():
            records[case]=dict(root=str(Path(r['capture_root'])/mode),hashes=r['rgb_hashes'][mode],
                               commit=r['commit'],receipt=r['receipt'],mode=mode)
    assert set(records)==set(range(1,9))
    assert records[7]['hashes']==records[8]['hashes']
    return records

def compose(tiles,scene,index,speed):
    w,h=tiles[1].size;gap=10;top=72;label=52
    im=Image.new('RGB',(4*(w+gap)+gap,top+2*(h+label+gap)),BG)
    d=ImageDraw.Draw(im)
    phase='이동' if 60<=index<420 else '정지'
    d.text((10,5),f'{scene.title()} · 새 8초 타임라인 | f{index:03d} · {phase} | {speed}',font=FONT,fill='white')
    d.text((10,29),'정지 1초 → 연속 이동 6초 → 정지 1초 · 원본 480프레임 모두 사용 · 반복/보간 없음',font=SMALL,fill='#c4cbd1')
    d.text((10,49),'전체 화면 축소: 경로 확인용 · 미세 품질은 확대 GIF와 무손실 PNG로 확인 · ③④ Pattern On / 나머지 Off',font=SMALL,fill='#c4cbd1')
    for k,c in enumerate(range(1,9)):
        x=gap+(k%4)*(w+gap);y=top+(k//4)*(h+label+gap)
        d.text((x,y),LABELS[c-1],font=FONT,fill='white')
        d.text((x,y+23),'spatial On' if c in (2,4,6,7,8) else 'spatial Off',font=SMALL,fill='#c4cbd1')
        im.paste(tiles[c],(x,y+label))
    return im

def main():
    all_records=[]
    for scene in ('bistro','minecraft'):
        records=collect(scene);thumbs={}
        # Each source is read independently and verified before presentation resampling.
        for case,r in records.items():
            for i in range(480):
                p=Path(r['root'])/f'frame_{i:05d}.png'
                with Image.open(p) as source:
                    rgb=source.convert('RGB')
                    assert hashlib.sha256(rgb.tobytes()).hexdigest()==r['hashes'][i]
                    thumbs[case,i]=rgb.resize((384,212),Image.Resampling.LANCZOS)
            print('PASS long source:',scene,case,flush=True)
        name=f'{scene}-long';title=f'{scene.title()} 새 8초 전체 경로'
        def render(i,speed='slow=1/6배속 · fast=0.83배속'):
            return compose({c:thumbs[c,i] for c in range(1,9)},scene,i,speed)
        pair=gif_pair(name,render,480)
        video=encode_mp4(MEDIA/f'{name}-60fps.mp4',lambda i:render(i,'정상 속도 60fps'),480)
        render(300,'원본 PNG에서 축소').save(MEDIA/f'{name}-poster.png')
        all_records.append(dict(scene=scene,name=name,title=title,gifs=pair,video=video,
             poster=f'{name}-poster.png',sources=records,source_frames=[0,479],source_fps=60,
             phase_frames={'initial_still':[0,59],'moving':[60,419],'final_still':[420,479]},
             spatial_presentation={'source':[1920,1061],'panel':[384,212],'filter':'Lanczos','purpose':'overview only'},
             original_colors=True,repeated_or_interpolated_frames=False))
        (OUT/'long-media-manifest.json').write_text(json.dumps(dict(case_layout=[[1,2,3,4],[5,6,7,8]],media=all_records),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        del thumbs;gc.collect()
        print('PASS long media:',scene,flush=True)

if __name__=='__main__':main()
