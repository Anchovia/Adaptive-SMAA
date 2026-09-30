"""Compare verified GPU weight and RGB delta captures from independent cases 5/6."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Projects/CMAA2/Captures/history-contribution-20260930'
DOC=ROOT/'Docs/History-Contribution/comparison'
FONT=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',20)
BOLD=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',23)
SMALL=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',17)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git_json(ref,path):return json.loads(subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT))
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def gif(path,frames,fps):
    palette=[v for i in range(256) for v in (i,i,i)]
    indexed=[]
    for im in frames:
        p=Image.frombytes('P',im.size,im.tobytes());p.putpalette(palette);indexed.append(p)
    durations=[10*(round((i+1)*100/fps)-round(i*100/fps)) for i in range(len(frames))]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=durations,loop=0,disposal=2,optimize=False)
    with Image.open(path) as im:
        assert im.n_frames==len(frames)
        for i,f in enumerate(frames):
            im.seek(i);assert im.info['duration']==durations[i]
            assert im.convert('L').tobytes()==f.tobytes()
    return dict(path=str(path.resolve()),sha256=sha(path),frames=len(frames),duration_ms=sum(durations),grayscale_decoded_exact=True)

def render(data,clip,index):
    frame=clip['start']+index
    out=Image.new('L',(1152,1060),0);d=ImageDraw.Draw(out)
    d.text((12,6),clip['title']+' · 실제 history 혼합 기여',font=BOLD,fill=255)
    phase='정지' if frame>=180 else '이동'
    d.text((12,44),f"f{frame:03d} · {phase} · 동일 ROI 2배 확대 · {clip['fps']/60:g}배속 · 두 구현 모두 지터 Off",font=FONT,fill=215)
    for j,case in enumerate((5,6)):
        x=j*576
        d.text((x+12,85),'⑤ 공간 AA 없음' if case==5 else '⑥ 공간 SMAA 적용',font=BOLD,fill=255)
        d.text((x+12,117),'상단: 실제 history 비중 · 검정 0 / 흰색 0.5',font=SMALL,fill=225)
        a=data[case];mask=a['mask'][index];w=a['weight'][index];delta=a['delta'][index]
        mean=float(w[mask].mean()) if mask.any() else 0
        d.text((x+12,144),f'이 ROI의 선택 비율 {mask.mean()*100:.1f}% · 선택 픽셀 평균 비중 {mean*100:.1f}%',font=SMALL,fill=215)
        weight_image=np.rint(np.clip(w,0,.5)*510).astype(np.uint8)
        out.paste(Image.fromarray(weight_image).resize((576,384),Image.Resampling.NEAREST),(x,174))
        d.text((x+12,573),'하단: 현재 색상 → 최종 출력 변화 · 밝기 16배',font=SMALL,fill=225)
        changed=float((delta[mask]>0).mean()*100) if mask.any() else 0
        d.text((x+12,601),f'선택 픽셀 중 RGB가 실제 변한 비율 {changed:.1f}%',font=SMALL,fill=215)
        delta_image=np.minimum(delta.astype(np.uint16)*16,255).astype(np.uint8)
        out.paste(Image.fromarray(delta_image).resize((576,384),Image.Resampling.NEAREST),(x,630))
    d.text((12,1024),'비선택 영역도 검정 · 변화량 = max(|ΔR|, |ΔG|, |ΔB|) · 혼합량/색상 변화는 품질 점수가 아님',font=SMALL,fill=215)
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-ref',required=True);p.add_argument('--spatial-ref',default='d603d29')
    args=p.parse_args();refs={5:args.raw_ref,6:args.spatial_ref}
    refs={c:subprocess.check_output(['git','rev-parse',r],cwd=ROOT,text=True).strip() for c,r in refs.items()}
    analyses={c:{s:git_json(r,f'Docs/History-Contribution/case{c}/{s}-analysis.json') for s in ('bistro','minecraft')} for c,r in refs.items()}
    for c in (5,6):
        for s,a in analyses[c].items():
            assert a['validation']=='PASS' and a['case']==c and a['scene']==s
            assert a['verified_final_rgb_frames']==720 and a['unchanged_coverage_frames']==120
            assert a['nonselected_current_mismatch_pixels']==0
    for scene in ('bistro','minecraft'):
        a,b=analyses[5][scene]['frames'],analyses[6][scene]['frames']
        assert len(a)==len(b)==120
        assert all(x['frame']==y['frame'] and x['coverage_sha256']==y['coverage_sha256'] for x,y in zip(a,b))
    OUT.mkdir(parents=True,exist_ok=True);DOC.mkdir(parents=True,exist_ok=True);clips=[]
    for scene in ('bistro','minecraft'):
        for e5 in analyses[5][scene]['clips']:
            clip=e5['clip'];e6=next(e for e in analyses[6][scene]['clips'] if e['clip']['id']==clip['id'])
            assert clip==e6['clip'];data={}
            for c,e in [(5,e5),(6,e6)]:
                assert sha(e['data'])==e['sha256']
                with np.load(e['data']) as z:data[c]={k:z[k] for k in ('weight','delta','mask')}
                assert data[c]['weight'].shape==(clip['end']-clip['start'],192,288)
            assert np.array_equal(data[5]['mask'],data[6]['mask'])
            frames=[render(data,clip,i) for i in range(clip['end']-clip['start'])]
            movie=gif(OUT/(clip['id']+'-history-contribution.gif'),frames,clip['fps'])
            preview=OUT/(clip['id']+'-history-preview.png');frames[len(frames)//2].save(preview)
            metrics={}
            for c in (5,6):
                m=data[c]['mask'];w=data[c]['weight'][m];d=data[c]['delta'][m]
                metrics[c]=dict(roi_pixel_frame_coverage_percent=float(m.mean()*100),
                    selected_weight_mean=float(w.mean()),selected_changed_percent=float(np.mean(d>0)*100),
                    selected_delta_mean_max_rgb_level=float(d.mean()))
            clips.append(dict(clip=clip,media=movie,preview=str(preview.resolve()),roi_metrics=metrics))
            print('PASS:',clip['id'],'decoded GIF pixels and durations verified',flush=True)
    result=dict(validation='PASS',source_refs=refs,clips=clips,
        global_moving_frame_means={c:{s:a['phases_frame_means']['moving'] for s,a in analyses[c].items()} for c in (5,6)},
        invariants='2880 final RGB frames equal each corrected baseline; 480 unchanged coverage frames; zero current-to-final difference outside selection. Independent branches, no AA semantics change.',
        visualization='Top: actual native GPU weight in 0..0.5, black outside selection too. Bottom: maximum absolute RGB channel change after 8-bit storage, multiplied by 16 and clamped to 255. Fixed scaling, nearest crop enlargement, no filtering. Not quality or timing results.')
    dump(DOC/'media.json',result);dump(OUT/'comparison.json',result)

if __name__=='__main__':main()
