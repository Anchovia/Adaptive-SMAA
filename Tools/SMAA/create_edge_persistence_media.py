"""Original-color comparison of a CPU hypothesis and captured GPU controls."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from edge_persistence_trace_inputs import A,C,dds,edges,rgb,reconstruct,dump,sha
from analyze_edge_persistence_gate import DOC,OUT

FONT=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',16)
BOLD=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',20)
CLIPS=[('minecraft-line-moving','minecraft','thin_edges',(964,524,996,588),range(130,136),4),
       ('minecraft-line-stop','minecraft','thin_edges',(956,524,1020,620),range(178,184),2),
       ('minecraft-line-still','minecraft','thin_edges',(956,524,1020,620),range(190,196),2),
       ('bistro-chairs-moving','bistro','chairs',(1230,582,1358,670),range(130,136),2),
       ('bistro-window-stop','bistro','window',(906,470,1034,558),range(178,184),2),
       ('bistro-window-still','bistro','window',(906,470,1034,558),range(190,196),2)]

def custom(scene,box,frames,report):
    cap=Path(report['input_capture']);data={};x0,y0,x1,y1=box;r=np.s_[y0:y1,x0:x1]
    for f in frames:
        pre=cap/A/f'frame_{f:05d}';cur=dds(str(pre)+'-current.dds');prev=dds(str(pre)+'-previous.dds');v=dds(str(pre)+'-velocity.dds')
        pred=reconstruct(cur,prev,v);q=pred['coords'];inside=(q[:,:,0]>=0)&(q[:,:,0]<1920)&(q[:,:,1]>=0)&(q[:,:,1]<1061)
        e=edges(str(pre)+'-edge.rg8').any(axis=2);ep=edges(cap/A/f'frame_{f-1:05d}-edge.rg8').any(axis=2)
        ix=np.floor(q[:,:,0]).astype(int).clip(0,1919);iy=np.floor(q[:,:,1]).astype(int).clip(0,1060)
        added=ep[iy,ix]&inside&~e;base=rgb(str(pre)+'.png');proxy=np.where(added[:,:,None],pred['full_resolve'],base)
        ref=next(s['reference_path'] for s in report['sources'] if s['frame']==f)
        row=dict(base=base,proxy=proxy,native=rgb(cap/C/f'frame_{f:05d}.png'),reference=rgb(ref),added_mask=added,safe=pred['safe']&inside)
        for k,v in row.items():data.setdefault(k,[]).append(v[r].copy())
    return {k:np.stack(v) for k,v in data.items()}

def main():
    OUT.mkdir(parents=True,exist_ok=True);clips=list(CLIPS);records=[]
    for scene in ['bistro','minecraft']:
        j=json.loads((DOC/f'{scene}-results.json').read_text());assert j['validation']=='PASS'
        clips.append((scene+'-error-increase',scene,None,tuple(j['reference_increase_patch']['roi']),range(130,136),3))
    for name,scene,region,box,frames,scale in clips:
        report=json.loads((DOC/f'{scene}-results.json').read_text())
        if region:
            a=np.load(OUT/f'{scene}-{region}.npz');rx,ry,_,_=a['roi'];x0,y0,x1,y1=box
            ix=[int(np.flatnonzero(a['frames']==f)[0]) for f in frames]
            data={k:a[k][ix,y0-ry:y1-ry,x0-rx:x1-rx] for k in ['base','proxy','native','reference','added_mask','safe']}
        else:data=custom(scene,box,frames,report)
        x0,y0,x1,y1=box;w=(x1-x0)*scale;h=(y1-y0)*scale;top=130;rh=h+28;gap=8
        sheet=Image.new('RGB',(5*w+6*gap,top+rh*len(frames)+62),(19,21,24));d=ImageDraw.Draw(sheet)
        d.text((8,6),name,font=BOLD,fill='white')
        d.text((8,38),f'원본 색상 / ROI {box} / nearest {scale}배 / CPU 가설은 GPU 실행 결과 아님',font=FONT,fill='white')
        labels=['⑥ 현재 edge\nGPU / Pattern Off','직전 edge 유지\nCPU 가설 / Off','④ 원본 T2X-R\nGPU / Pattern On','고해상도 참조\nspatial proxy','추가 선택 위치\n흰색 = 추가']
        for k,label in enumerate(labels):d.multiline_text((gap+k*(w+gap),77),label,font=FONT,fill='white',spacing=2)
        anim=[]
        for i,f in enumerate(frames):
            panels=[data[k][i] for k in ['base','proxy','native','reference']]+[np.repeat((data['added_mask'][i]*255).astype(np.uint8)[:,:,None],3,axis=2)]
            for k,p in enumerate(panels):
                x=gap+k*(w+gap);y=top+rh*i;d.text((x,y),f'f{f:03d}',font=FONT,fill='white')
                sheet.paste(Image.fromarray(p).resize((w,h),Image.Resampling.NEAREST),(x,y+26))
            im=Image.new('RGB',(3*w+4*gap,h+108),(19,21,24));di=ImageDraw.Draw(im)
            for k in range(3):
                di.multiline_text((gap+k*(w+gap),5),labels[k],font=FONT,fill='white')
                im.paste(Image.fromarray(panels[k]).resize((w,h),Image.Resampling.NEAREST),(gap+k*(w+gap),50))
            di.text((8,h+58),f'{name} / f{f:03d} / 6fps (0.1배속)',font=FONT,fill='white');anim.append(im)
        d.text((8,top+rh*len(frames)),'CPU 가설: 현재 edge OR 재투영한 직전 raw edge. 색상/weight/feedback은 유지.',font=FONT,fill='white')
        d.text((8,top+rh*len(frames)+26),'참조 오차는 고스팅 정답이 아님. Point 경계의 불확실한 픽셀은 정량 검사에서 분리.',font=FONT,fill='white')
        png=OUT/(name+'.png');sheet.save(png);webp=OUT/(name+'.webp')
        durations=[round((i+1)*1000/6)-round(i*1000/6) for i in range(len(anim))]
        anim[0].save(webp,save_all=True,append_images=anim[1:],duration=durations,loop=0,lossless=True,exact=True)
        with Image.open(webp) as decoded:
            duration=0;originals={im.tobytes() for im in anim}
            for i in range(decoded.n_frames):
                decoded.seek(i);decoded.load();assert decoded.convert('RGB').tobytes() in originals;duration+=decoded.info['duration']
            assert duration==sum(durations)
        records.append(dict(name=name,scene=scene,roi=box,frames=list(frames),scale=scale,png=str(png),png_sha256=sha(png),webp=str(webp),
            lossless_roundtrip=True,unsafe_added_pixel_frames=int((data['added_mask']&~data['safe']).sum())))
        print('PASS',name,flush=True)
    dump(DOC/'media.json',dict(validation='PASS',items=records,scope='Original-color CPU hypothesis vs GPU captures; no new GPU quality/timing claim.'))

if __name__=='__main__':main()
