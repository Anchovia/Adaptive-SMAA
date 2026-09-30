"""Display captured GPU first-pass edge masks, never re-detect edges from RGB."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from analyze_first_edge_stencil import edge, coverage
from create_six_case_stencil_media import CLIPS

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Six-Case-Stencil-Lifecycle'
FONT=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',20)
BOLD=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',24)
HISTORICAL={5:'Docs/First-Edge-Temporal-Only-Stencil',6:'Docs/Spatial-First-Edge-Stencil'}


def git_json(ref,path):
    return json.loads(subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT))


def render(mask,title,frame,fps,count,roi=None):
    im=mask.convert('L')
    if roi:
        im=im.crop(roi).resize((576,384),Image.Resampling.NEAREST)
    canvas=Image.new('L',(im.width,im.height+110),0)
    canvas.paste(im,(0,110))
    draw=ImageDraw.Draw(canvas)
    draw.text((10,4),title,font=BOLD,fill=255)
    draw.text((10,39),f'⑤·⑥ 공통 · 흰색 = temporal 선택 · {fps/60:g}배속',font=FONT,fill=210)
    phase='정지' if frame>=180 else '이동'
    draw.text((10,73),f'f{frame:03d} · {phase} · 전체 화면 {count/(1920*1061)*100:.3f}%',font=FONT,fill=210)
    return canvas.convert('RGB')


def write_gif(path,frames,fps):
    # Direct grayscale indices avoid the approximate RGB-to-palette lookup.
    palette=[v for i in range(256) for v in (i,i,i)]
    indexed=[]
    for im in frames:
        p=Image.frombytes('P',im.size,im.getchannel('R').tobytes())
        p.putpalette(palette)
        assert p.convert('RGB').tobytes()==im.tobytes()
        indexed.append(p)
    durations=[10*(round((i+1)*100/fps)-round(i*100/fps)) for i in range(len(frames))]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=durations,
                    loop=0,disposal=2,optimize=False)
    with Image.open(path) as decoded:
        assert decoded.n_frames==len(frames)
        for i,im in enumerate(frames):
            decoded.seek(i)
            assert decoded.info['duration']==durations[i]
            assert decoded.convert('RGB').tobytes()==im.tobytes()
    return dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                frames=len(frames),duration_ms=sum(durations),average_fps=fps,
                fixed_grayscale_palette=True,dither=False,rendered_rgb_lossless=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    assert not (a.output/'manifest.json').exists(),'Output already complete'
    summary=json.loads((DOC/'summary.json').read_text())
    assert summary['validation']=='PASS'
    records=[]
    for scene in ('bistro','minecraft'):
        src={}
        for case in (5,6):
            branch=next(x for x in summary['branches'] if x['case']==case)
            ref=branch['commit']
            prior=json.loads((DOC/f'case{case}'/f'{scene}-prior.json').read_text())
            cap=git_json(ref,f'{HISTORICAL[case]}/{scene}-capture.json')
            counts=git_json(ref,f'{HISTORICAL[case]}/{scene}-frames.json')
            cfg=git_json(ref,'Docs/Stencil-Lifecycle-Refresh/case.json')
            latest=git_json(ref,f'Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json')[cfg['target']]
            assert cap['validation']=='PASS' and not any(cap['mismatches'].values())
            folder=Path(prior['target_capture'])
            assert folder==Path(cap['capture'])/cfg['target']
            assert [r['frame'] for r in counts]==list(range(240))
            src[case]=dict(folder=folder,counts=counts,latest=latest,ref=ref)
        masks={};verified=[]
        for f in range(100,220):
            current={};hashes={}
            for case in (5,6):
                s=src[case];stem=s['folder']/f'frame_{f:05d}'
                raw=Path(str(stem)+'-edge.rg8')
                mask=edge(raw)
                witness=coverage(Path(str(stem)+'-coverage.dds'))
                assert np.array_equal(mask,witness),(scene,case,f,'GPU coverage mismatch')
                count=int(mask.sum())
                assert count==s['counts'][f]['edge_count']==s['counts'][f]['passing_samples']
                with Image.open(str(stem)+'.png') as im:
                    assert im.mode=='RGB' and im.size==(1920,1061)
                    assert hashlib.sha256(im.tobytes()).hexdigest()==s['latest'][f],(case,f,'latest RGB bridge')
                current[case]=mask
                hashes[str(case)]=hashlib.sha256(raw.read_bytes()).hexdigest()
            assert hashes['5']==hashes['6'] and np.array_equal(current[5],current[6]),(scene,f,'5/6 edge mismatch')
            masks[f]=Image.fromarray(current[6]).convert('1')
            verified.append(dict(frame=f,edge_count=count,rg8_sha256=hashes['6']))
            if f%30==9:print(scene,f,'GPU masks/coverage/5-6/RGB bridge PASS',flush=True)
        count_by_frame={r['frame']:r['edge_count'] for r in verified}
        results=[]
        for clip in [c for c in CLIPS if c['scene']==scene]:
            frames=[render(masks[f],clip['title']+' · edge',f,clip['fps'],count_by_frame[f],clip['roi'])
                    for f in range(clip['start'],clip['end'])]
            result=write_gif(a.output/(clip['id']+'-edges.gif'),frames,clip['fps'])
            result.update(clip=clip,scale=2,interpolation='nearest neighbor')
            results.append(result)
            frames[len(frames)//2].save(a.output/(clip['id']+'-preview.png'))
            del frames
        frames=[render(masks[f],scene.title()+' · 전체 화면 edge',f,30,count_by_frame[f]) for f in range(100,160)]
        full=write_gif(a.output/(scene+'-full-edges.gif'),frames,30)
        full.update(source_frames=[100,159],scale=1)
        frames[30].save(a.output/(scene+'-full-preview.png'))
        del frames
        records.append(dict(scene=scene,validation='PASS',source_frames=[100,219],
            equal_case5_case6_frames=120,coverage_verified_frames=240,latest_rgb_bridge_frames=240,
            sources={str(k):dict(folder=str(v['folder']),reference_commit=v['ref']) for k,v in src.items()},
            frames=verified,crop_gifs=results,full_gif=full))
        print(scene,'PASS: exact grayscale GIFs',flush=True)
    manifest=dict(validation='PASS',scenes=records,
        mask_definition='any(final first-pass RG > 0), verified equal to recorded GPU stencil coverage',
        provenance='GPU edge/coverage captures from 2026-09-29, reused with original-frame RGB hashes equal to corrected 2026-09-30 captures; no new renderer run.',
        scope='Case 5/6 actual temporal selection only. Not masks for cases 1-4, not image-derived edges.',
        no_dilation=True,no_brightness_adjustment=True,no_temporal_interpolation=True,
        output='Black/white masks and grayscale labels; fixed grayscale palette, decoded RGB exact.')
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('PASS: 6 edge-only GIFs; 480 coverage and latest-RGB bridges; 240 equal 5/6 edge frames',flush=True)


if __name__=='__main__':main()
