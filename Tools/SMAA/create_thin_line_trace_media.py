"""Original-color stage sheets and lossless animations for line-loss diagnosis."""
import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from analyze_thin_line_trace import ROOT,DOC,OUT,A,C,rgb,dump

FONT=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',17)
BOLD=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',19)
CLIPS=[('minecraft-line-moving','minecraft','thin_edges',(964,524,996,588),range(130,136),4),
       ('minecraft-line-witness','minecraft','thin_edges',(964,524,996,588),range(130,133),4),
       ('minecraft-line-stop','minecraft','thin_edges',(956,524,1020,620),range(178,184),3),
       ('minecraft-line-still','minecraft','thin_edges',(956,524,1020,620),range(190,196),3),
       ('bistro-chairs-moving','bistro','chairs',(1230,582,1358,670),range(130,136),2),
       ('bistro-window-stop','bistro','window',(906,470,1034,558),range(178,184),2),
       ('bistro-window-still','bistro','window',(906,470,1034,558),range(190,196),2)]
def image(a):return Image.fromarray(a.astype(np.uint8))
def main():
    OUT.mkdir(parents=True,exist_ok=True);items=[]
    for name,scene,region,box,frames,scale in CLIPS:
        va=json.loads((DOC/f'{scene}-capture-validation.json').read_text());assert va['validation']=='PASS'
        aa=np.load(OUT/f'{scene}-{region}-edge-off.npz');cc=np.load(OUT/f'{scene}-{region}-native-on.npz')
        x0,y0,x1,y1=box;rx,ry,_,_=aa['roi'];r=np.s_[y0-ry:y1-ry,x0-rx:x1-rx]
        w=(x1-x0)*scale;h=(y1-y0)*scale;gap=8;rowh=h+28;top=125
        labels=['AA 전 입력','현재 spatial','Edge 선택','이전 색\n가상 조회','최종\nEdge Off','원본\nT2X-R On']
        sheet=Image.new('RGB',(6*w+7*gap,top+len(frames)*rowh+60),(18,20,23));d=ImageDraw.Draw(sheet)
        d.text((8,5),name,font=BOLD,fill='white')
        d.text((8,34),f'원본 색상 / ROI {box} / nearest {scale}배 / 각 행 동일 프레임',font=FONT,fill='#dddddd')
        for j,label in enumerate(labels):d.text((gap+j*(w+gap),70),label,font=FONT,fill='white')
        anim=[]
        for i,f in enumerate(frames):
            ix=int(np.where(aa['frames']==f)[0][0]);assert cc['frames'][ix]==f
            mask=aa['mask'][ix][r];edge=np.repeat((mask*255).astype(np.uint8)[:,:,None],3,axis=2)
            panels=[aa['raw'][ix][r],aa['current'][ix][r],edge,aa['previous_point'][ix][r],aa['final'][ix][r],cc['final'][ix][r]]
            for j,panel in enumerate(panels):
                x=gap+j*(w+gap);y=top+i*rowh;d.text((x,y),f'f{f:03d}',font=FONT,fill='white')
                sheet.paste(image(panel).resize((w,h),Image.Resampling.NEAREST),(x,y+26))
            clip=Image.new('RGB',(3*w+4*gap,h+90),(18,20,23));cd=ImageDraw.Draw(clip)
            for j,(label,key,data) in enumerate([('현재 spatial','current',aa),('최종 Edge Off','final',aa),('원본 T2X-R On','final',cc)]):
                cd.text((gap+j*(w+gap),5),label,font=FONT,fill='white')
                clip.paste(image(data[key][ix][r]).resize((w,h),Image.Resampling.NEAREST),(gap+j*(w+gap),35))
            cd.text((8,h+42),f'{name} / f{f:03d} / 원본 색상 / 6fps = 0.1배속',font=FONT,fill='white');anim.append(clip)
        y=top+len(frames)*rowh
        d.text((8,y),'이전 색은 저장 입력에서 CPU로 조회. 비선택 위치는 실제 GPU history 접근이 아님.',font=FONT,fill='#dddddd')
        d.text((8,y+26),'선 소실/단절과 프레임별 출현을 직접 비교. Point 경계 근처는 별도 불확실성 표시 데이터 참조.',font=FONT,fill='#dddddd')
        png=OUT/(name+'-stages.png');sheet.save(png)
        webp=OUT/(name+'-slow.webp');dur=[round((i+1)*1000/6)-round(i*1000/6) for i in range(len(anim))]
        anim[0].save(webp,save_all=True,append_images=anim[1:],duration=dur,loop=0,lossless=True,exact=True)
        with Image.open(webp) as check:
            # Identical still frames may be coalesced by WebP; the elapsed display
            # duration is checked and each decoded frame must match a source frame.
            elapsed=0;source={im.tobytes() for im in anim}
            for i in range(check.n_frames):check.seek(i);check.load();assert check.convert('RGB').tobytes() in source;elapsed+=check.info['duration']
            assert elapsed==sum(dur)
        items.append(dict(id=name,scene=scene,roi=box,frames=list(frames),scale=scale,png=str(png),webp=str(webp),
            png_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),lossless_webp_verified=True,
            uncertain_point_pixels=int(sum((~aa['safe'][int(np.where(aa['frames']==f)[0][0])][r]).sum() for f in frames))))
        print('PASS',name,flush=True)
    dump(DOC/'media.json',dict(validation='PASS',items=items,scope='Original-color PNGs and lossless slow animation. CPU point-history shown for diagnosis, not an added GPU pass.'))
if __name__=='__main__':main()
