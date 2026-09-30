"""Three matched ROI animations; lossless WebP and fixed-palette GIF for viewing."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from analyze_coverage_pattern_control import ROOT,DOC,A,B,C,rgb,dump

OUT=ROOT/'Projects/CMAA2/Captures/coverage-pattern-control-20260930'
CLIPS=[dict(id='bistro-chairs-moving',scene='bistro',title='Bistro · 의자 다리 / 이동',start=100,end=160,roi=[1190,530,1478,722],fps=30),
       dict(id='minecraft-thin-edges-moving',scene='minecraft',title='Minecraft · 얇은 경계 / 이동',start=100,end=160,roi=[780,460,1068,652],fps=30),
       dict(id='bistro-window-stop',scene='bistro',title='Bistro · 창살 / 이동 → 정지',start=160,end=220,roi=[880,430,1168,622],fps=15)]
FONT=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
BOLD=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',24)
SMALL=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',17)
LABELS={A:'⑥ Edge 선택 · 지터 Off',B:'대조군 전체 화면 · 지터 Off',C:'④ 원본 T2X-R · 지터 On'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    reports={s:json.loads((DOC/f'{s}-capture-validation.json').read_text(encoding='utf-8')) for s in ('bistro','minecraft')}
    assert all(r['validation']=='PASS' for r in reports.values());result=[]
    for clip in CLIPS:
        cap=Path(reports[clip['scene']]['capture']);frames=[];x0,y0,x1,y1=clip['roi']
        for f in range(clip['start'],clip['end']):
            im=Image.new('RGB',(1728,528),(16,18,22));d=ImageDraw.Draw(im)
            d.text((12,6),clip['title'],font=BOLD,fill='white')
            phase='정지' if f>=180 else '이동'
            d.text((12,42),f"f{f:03d} · {phase} · 모두 공간 SMAA 적용 · 같은 영역 2배 확대 · {clip['fps']/60:g}배속",font=FONT,fill=(220,225,232))
            for j,m in enumerate((A,B,C)):
                d.text((j*576+12,80),LABELS[m],font=BOLD,fill='white')
                crop=Image.fromarray(rgb(cap/m/f'frame_{f:05d}.png')[y0:y1,x0:x1]).resize((576,384),Image.Resampling.NEAREST)
                im.paste(crop,(j*576,114))
            d.text((12,498),'동일 시점 직접 비교 · 전체 화면 Off는 temporal stencil 검사만 해제 · 반짝임/선명도/잔상은 구분해서 확인',font=SMALL,fill=(220,225,232))
            frames.append(im)
        durations=[10*(round((i+1)*100/clip['fps'])-round(i*100/clip['fps'])) for i in range(len(frames))]
        webp=OUT/(clip['id']+'.webp')
        frames[0].save(webp,save_all=True,append_images=frames[1:],duration=durations,loop=0,lossless=True,exact=True,method=4)
        with Image.open(webp) as im:
            assert im.n_frames==len(frames)
            for i,f in enumerate(frames):
                im.seek(i);im.load();assert im.convert('RGB').tobytes()==f.tobytes(),('lossless',i)
                assert im.info['duration']==durations[i],('WebP duration',i,im.info)
        # A single palette across all frames avoids adaptive-palette pumping.
        sheet=Image.new('RGB',(432,129*len(frames)))
        for i,f in enumerate(frames):sheet.paste(f.resize((432,129)),(0,i*129))
        palette=sheet.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
        gif=OUT/(clip['id']+'.gif')
        indexed[0].save(gif,save_all=True,append_images=indexed[1:],duration=durations,loop=0,disposal=2,optimize=False)
        with Image.open(gif) as im:
            assert im.n_frames==len(frames)
            for i,f in enumerate(indexed):
                im.seek(i);assert im.info['duration']==durations[i]
                assert im.convert('RGB').tobytes()==f.convert('RGB').tobytes()
        preview=OUT/(clip['id']+'-preview.png');frames[30].save(preview)
        quant_mean=float(np.mean([np.abs(np.asarray(x.convert('RGB')).astype(np.int16)-np.asarray(y).astype(np.int16)).mean() for x,y in zip(indexed,frames)]))
        result.append(dict(clip=clip,webp=str(webp.resolve()),webp_sha256=sha(webp),lossless_webp_all_decoded_frames_exact=True,
            gif=str(gif.resolve()),gif_sha256=sha(gif),gif_fixed_palette_mean_rgb_error=quant_mean,preview=str(preview.resolve()),duration_ms=sum(durations),frames=len(frames)))
        print('PASS',clip['id'],'lossless WebP exact; GIF palette/timing verified',flush=True)
    dump(DOC/'media.json',dict(validation='PASS',clips=result,captures={s:r['capture'] for s,r in reports.items()},
        scope='Display only, metrics use original RGB PNGs. Prefer lossless WebP; GIF has disclosed color quantization. Same fixed palette throughout each GIF. Nearest 2x crop enlargement.'))

if __name__=='__main__':main()
