"""Actual 4/10/13/14 frames: extended detail views, 60fps video and near-normal GIF."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,GifImagePlugin
from create_case14_playback import Video
from verify_four_case_playback_inputs import ROOT,DOC,MODES,load
from edge_quality_inputs import sha

FONT=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
SMALL=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',11)
LABELS=['4 T2X-R','10 spatial H','13 Catmull','14 w=0.8']
DETAIL=['J On / point','J Off / bilinear','J Off / Catmull','J Off / Catmull']
ROIS={'bistro':[
    ('thin-chair','가는 의자·테이블 다리',(1230,582,1358,670)),
    ('windows','밝은 창문과 창살',(950,460,1110,588)),
    ('balcony','발코니의 촘촘한 난간',(920,154,1080,282)),
    ('sign','간판 글자와 곡선',(940,320,1112,398)),
    ('awning','차양의 가는 지지대',(1310,414,1470,518)),
    ('late-chairs','이동 후반의 의자 경계',(1280,570,1440,718))],
    'minecraft':[
    ('thin-seam','얇은 벽 이음선',(956,524,1020,620)),
    ('leaves','나뭇잎의 촘촘한 무늬',(1420,590,1580,718)),
    ('grass-seam','잔디 윗면의 약한 이음선',(1450,665,1552,719)),
    ('railings','전경 블록 난간',(400,700,576,844)),
    ('stairs','계단과 반복 블록 경계',(430,510,606,686)),
    ('water-edge','물과 잔디의 경계',(1160,720,1336,848)),
    ('stone-beam','대각선 석재 구조',(640,326,800,454))]}

def compose(images,f,box=None):
    w,h=(720,398) if box is None else ((box[2]-box[0])*2,(box[3]-box[1])*2)
    cols,rows=(2,2) if box is None else (4,1)
    size=(cols*(w+8)+8,rows*(h+68)+8)
    size=(size[0]+size[0]%2,size[1]+size[1]%2)
    canvas=Image.new('RGB',size,(18,20,23));d=ImageDraw.Draw(canvas)
    phase='initial still' if f<60 else ('moving' if f<660 else 'post-stop')
    for i,im in enumerate(images):
        x=8+(i%cols)*(w+8);y=8+(i//cols)*(h+68)
        d.text((x,y),LABELS[i],font=FONT,fill='white')
        d.text((x,y+18),DETAIL[i],font=SMALL,fill='#cdd7e1')
        d.text((x,y+34),f'f{f:03d} / {phase}',font=SMALL,fill='#cdd7e1')
        tile=im.resize((w,h),Image.Resampling.LANCZOS) if box is None else im.crop(box).resize((w,h),Image.Resampling.NEAREST)
        canvas.paste(tile,(x,y+54))
    return canvas

class Gif:
    def __init__(self,path,palette):self.path=path;self.palette=palette;self.out=path.open('wb');self.hashes=[]
    def write(self,view,f):
        im=view.quantize(palette=self.palette,dither=Image.Dither.NONE)
        if f==0:
            header,_=GifImagePlugin.getheader(im,info={'loop':0,'optimize':False})
            for b in header:self.out.write(b)
        for b in GifImagePlugin.getdata(im,duration=20,disposal=2,include_color_table=False):self.out.write(b)
        self.hashes.append(hashlib.sha256(im.convert('RGB').tobytes()).hexdigest())
    def close(self):
        self.out.write(b';');self.out.close();total=0
        with Image.open(self.path) as im:
            assert im.n_frames==720
            for f in range(720):
                im.seek(f);assert im.info['duration']==20;total+=im.info['duration']
                assert hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()==self.hashes[f]
        assert total==14400
        return dict(path=str(self.path),sha256=sha(self.path),frames=720,fps=50,duration_seconds=14.4,
                    source_fps=60,playback_speed=50/60,fixed_palette=True,dither=False,
                    decoded_frames_verified=True,classification='lossy shared-palette presentation')

def make(scene,out):
    evidence=DOC/f'{scene}-inputs.json';e=load(evidence);assert e['validation']=='PASS'
    roots={m:Path(e['sources'][m]) for m in MODES}
    def images(f):
        ims=[]
        for m in MODES:
            with Image.open(roots[m]/f'frame_{f:05d}.png') as p:
                im=p.convert('RGB');assert im.size==(1920,1061)
                assert hashlib.sha256(im.tobytes()).hexdigest()==e['rgb_hashes'][m][f]
                ims.append(im)
        return ims
    specs=ROIS[scene];samples={name:[] for name,_,_ in specs}
    for f in [0,60,130,180,239,360,480,600,658,700,719]:
        ims=images(f)
        for name,_,box in specs:samples[name].append(compose(ims,f,box).resize((400,220)))
    palettes={}
    for name,tiles in samples.items():
        atlas=Image.new('RGB',(400,220*len(tiles)))
        for i,tile in enumerate(tiles):atlas.paste(tile,(0,i*220))
        palettes[name]=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    first=images(0);full=Video(out/f'{scene}-overview-60fps.mp4',compose(first,0).size)
    writers={name:(Video(out/f'{scene}-{name}-60fps.mp4',compose(first,0,box).size),Gif(out/f'{scene}-{name}-50fps.gif',palettes[name])) for name,_,box in specs}
    for f in range(720):
        ims=first if f==0 else images(f);full.write(compose(ims,f),f)
        for name,_,box in specs:
            view=compose(ims,f,box);video,gif=writers[name];video.write(view,f);gif.write(view,f)
            if f in [130,480,658,700]:view.save(out/f'{scene}-{name}-f{f:03d}.png')
        if f%180==0:print(scene,'media',f,'/720',flush=True)
    result=dict(scene=scene,mode_order=MODES,inputs_sha256=sha(evidence),frames=720,full_video=full.close(),rois=[],inspection_sheets=[])
    for name,title,box in specs:
        video,gif=writers[name];result['rois'].append(dict(name=name,title=title,roi=box,scale=2,filter='nearest',video=video.close(),gif=gif.close()))
    for name,_,box in specs:
        for phase,start in [('moving',126),('late-moving',480),('transition',658),('settled',700)]:
            for pair in range(3):
                fs=[start+pair*2,start+pair*2+1];views=[compose(images(f),f,box) for f in fs]
                sheet=Image.new('RGB',(views[0].width,views[0].height*2),(18,20,23))
                for row,v in enumerate(views):sheet.paste(v,(0,row*v.height))
                path=out/f'{scene}-{name}-{phase}-pair{pair}.png';sheet.save(path)
                result['inspection_sheets'].append(dict(path=str(path),frames=fs,roi=box,scale=2,filter='nearest',tone_adjustment=False))
    for f in [130,480,658,700]:
        for m,im in zip(MODES,images(f)):im.save(out/f'{scene}-{m}-full-f{f:03d}.png')
    (DOC/f'{scene}-media.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(scene,'PASS media; all video/GIF frames decoded and checked',flush=True)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--scene',choices=['bistro','minecraft'],required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);make(a.scene,out)
    sections=[];results=[]
    for scene in ROIS:
        path=DOC/f'{scene}-media.json'
        if not path.exists():continue
        r=load(path);results.append(r)
        s=f'<section><h2>{scene.title()}</h2><p>전체 화면 2×2: 좌상④·우상⑩·좌하⑬·우하⑭</p><video controls loop muted playsinline preload="metadata" src="{Path(r["full_video"]["path"]).name}"></video>'
        for roi in r['rois']:
            s+=f'<h3>{roi["title"]}</h3><p>왼쪽부터 ④·⑩·⑬·⑭ · nearest 2배 · 실제720프레임 · 60fps 영상12초</p><video controls loop muted playsinline preload="metadata" src="{Path(roi["video"]["path"]).name}"></video><p>GIF 50fps ·14.4초 · 원본 재생 속도의 83.3%</p><img loading="lazy" src="{Path(roi["gif"]["path"]).name}"><details><summary>무손실 연속 프레임</summary>'
            for sheet in r['inspection_sheets']:
                if sheet['roi']==roi['roi']:
                    f=Path(sheet['path']).name;s+=f'<p>frames {sheet["frames"]}</p><a href="{f}"><img loading="lazy" src="{f}"></a>'
            s+='</details>'
        sections.append(s+'</section>')
    html='<!doctype html><html lang="ko"><meta charset="utf-8"><title>④·⑩·⑬·⑭ 확장 비교</title><style>body{background:#12151a;color:#edf1f7;font:16px sans-serif;margin:32px auto;max-width:1400px;padding:0 20px}video,img{width:100%;height:auto}section{margin:48px 0}a{color:#b5d7ff}</style><h1>④·⑩·⑬·⑭ 확장 비교</h1><p>모두 Original spatial SMAA Ultra와 camera/depth reprojection을 사용합니다. ④는 전체 화면 native T2X-R·Pattern On·point history·spatial-frame history, ⑩은 현재/재투영 직전 raw edge·Pattern Off·bilinear·spatial-frame history, ⑬은 같은 선택에 normalized Catmull–Rom 5-fetch·resolved RGB feedback·native adaptive 0..0.5, ⑭는 ⑬의 weight를 fixed0.8로 교체합니다.</p><p>장면별 실제720프레임: 정지1초 → 이동10초 → 정지1초. ROI는 화면 고정이며 같은 물체 추적이 아닙니다. 밝기·색상 조정, 보간과 프레임 복제는 없습니다. GIF/MP4는 손실 확인용이고 원본 무손실 PNG를 함께 보존합니다. 이번 자료는 영상 비교이며 새로운 품질 점수나 속도 측정이 아닙니다.</p>'+''.join(sections)+'</html>'
    (out/'comparison.html').write_text(html,encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps(dict(classification='presentation only; no interpolation or repeated source frames',source_frames=[0,719],source_fps=60,mode_order=MODES,results=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
