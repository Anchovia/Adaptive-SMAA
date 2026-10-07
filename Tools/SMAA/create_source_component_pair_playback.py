"""Pair native T2X-R with each independent source-component ablation.

Read the verified lossless source frames, not the encoded five-column videos.
No AA implementation, GPU measurement, or quality verdict changes here.
"""
import argparse
import html
import io
import json
from pathlib import Path

import create_source_component_extended_playback as media
from PIL import Image, ImageDraw

CASES = [14, 15, 16, 17]
NAMES = {14: 'Base w0.8', 15: 'Clip', 16: 'Source5tap', 17: 'ColorMix'}


def compose(images, frame, case, box):
    w, h = (384, 212) if box is None else ((box[2]-box[0])*2, (box[3]-box[1])*2)
    canvas = Image.new('RGB', (2*(w+8)+8, h+66), (18, 20, 23))
    draw = ImageDraw.Draw(canvas)
    for col, im in enumerate(images):
        x = 8 + col*(w+8)
        label = media.LABELS[0] if col == 0 else media.LABELS[CASES.index(case)+1]
        draw.text((x, 6), label, font=media.FONT, fill='white')
        draw.text((x, 25), f'f{frame:03d} / {media.phase(frame)}', font=media.SMALL, fill='#cdd7e1')
        draw.text((x, 41), 'full temporal' if col == 0 else 'edge temporal / w0.8', font=media.SMALL, fill='#cdd7e1')
        tile = im.resize((w,h), Image.Resampling.LANCZOS) if box is None else im.crop(box).resize((w,h), Image.Resampling.NEAREST)
        canvas.paste(tile, (x,58))
    return canvas


def make_scene(scene, evidence, out, palette_root):
    metas = {i: media.load(evidence/f'case{i}/case.json') for i in [15,16,17]}
    infos = {i: media.load(evidence/f'case{i}/{scene}-long-capture.json') for i in metas}
    validations = {i: media.verify_capture(infos[i], scene, metas[i]) for i in metas}
    for i in [16,17]:
        for mode in ['O-T2X-R', media.BASE]:
            assert infos[i]['output_hashes'][mode] == infos[15]['output_hashes'][mode]
    sources = [(15,'O-T2X-R'), (15,media.BASE)] + [(i,metas[i]['semantic_id']) for i in [15,16,17]]
    read_retries = []

    def frames(f):
        result = []
        for i,mode in sources:
            path = Path(infos[i]['capture_root'])/mode/f'frame_{f:05d}.png'
            expected = infos[i]['output_hashes'][mode][f]
            # Only a decoded image matching the pinned RGB hash may enter media.
            # A failed read is recorded and discarded; never weaken the check.
            for attempt in range(3):
                payload = path.read_bytes()
                with Image.open(io.BytesIO(payload)) as fp:
                    im = fp.convert('RGB')
                assert im.size == (1920,1061)
                actual = media.pixel_hash(im)
                if actual == expected:
                    break
                event = dict(path=str(path),frame=f,mode=mode,attempt=attempt+1,
                             actual=actual,expected=expected,
                             encoded_sha256=media.hashlib.sha256(payload).hexdigest())
                read_retries.append(event)
                print('Discard mismatched source read',json.dumps(event),flush=True)
            else:
                raise AssertionError((scene,mode,f,str(path),actual,expected))
            result.append(im)
        return result

    specs = [('overview','전체 이동 경로',None)] + media.ROIS[scene]
    first = frames(0)
    writers = {}
    for name,title,box in specs:
        # Reuse the verified five-way common palette for consistent color loss.
        with Image.open(palette_root/f'{scene}-{name}-long-slow.gif') as original:
            assert original.mode == 'P' and original.n_frames == media.FRAMES
            palette = original.copy()
        for case in CASES:
            prefix = f'{scene}-{name}-4-vs-{case}'
            size = compose([first[0],first[CASES.index(case)+1]],0,case,box).size
            writers[name,case] = (
                media.Video(out/f'{prefix}-normal.mp4',size),
                media.Gif(out/f'{prefix}-slow.gif',palette,1,40),
                media.Gif(out/f'{prefix}-fast.gif',palette,2,20))
    sheet_frames = {start+2*p for _,start in media.WINDOWS for p in range(3)}
    pending = {}
    sheets = []
    for f in range(media.FRAMES):
        ims = first if f == 0 else frames(f)
        for name,title,box in specs:
            for index,case in enumerate(CASES,1):
                view = compose([ims[0],ims[index]],f,case,box)
                video,slow,fast = writers[name,case]
                video.write(view)
                quantized = slow.write(view,f)
                fast.write(view,f,quantized)
                if box is not None and f in sheet_frames:
                    pending[name,case] = view.copy()
                if box is not None and f-1 in sheet_frames:
                    sheet = Image.new('RGB',(view.width,view.height*2))
                    sheet.paste(pending.pop((name,case)),(0,0))
                    sheet.paste(view,(0,view.height))
                    path = out/f'{scene}-{name}-4-vs-{case}-f{f-1}-{f}.png'
                    sheet.save(path)
                    sheets.append(dict(path=str(path),roi=box,frames=[f-1,f],case=case,name=name))
        if f%60 == 0:
            print('Verified pair rendering',scene,f,'/720',flush=True)
    results = []
    for name,title,box in specs:
        for case in CASES:
            video,slow,fast = writers[name,case]
            results.append(dict(name=name,title=title,case=case,mode_order=[4,case],roi=box,
                                normal=video.close(),slow=slow.close(),fast=fast.close()))
            print('PASS pair decode',scene,name,case,flush=True)
    return dict(scene=scene,source_validation=validations,source_pngs_checked=3600,
                source_read_retries=read_retries,unmatched_frames_used=0,
                source_frames=720,control_rgb_mismatch=0,results=results,inspection_sheets=sheets)


def finish(out, evidence, palette_root):
    results = [media.load(out/f'{scene}-manifest.json') for scene in ['bistro','minecraft']
               if (out/f'{scene}-manifest.json').exists()]
    assert len(results) == 2, 'Both complete scene manifests are required'
    provenance = {}
    for scene in ['bistro','minecraft']:
        for case in [15,16,17]:
            path = evidence/f'case{case}/{scene}-long-capture.json'
            info = media.load(path)
            provenance[f'{scene}/case{case}'] = dict(path=str(path),sha256=media.sha(path),
                                                      capture_root=info['capture_root'])
    manifest = dict(validation='PASS',classification='pair presentation; no new quality or timing',
                    pair_order=[[4,i] for i in CASES],source='verified lossless PNG, not encoded media',
                    evidence_root=str(evidence),palette_root=str(palette_root),source_provenance=provenance,
                    timeline='60 still + 600 moving + 60 still at fixed60',actual_playback_observed=False,
                    normal='60fps/12s/1x',slow='25fps/28.8s/0.4167x',fast='stride2/50fps/7.2s/1.6667x',
                    results=results)
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    page = ['<!doctype html><html lang="ko"><meta charset="utf-8"><title>④와 개별 구현 2개씩 비교</title>',
            '<style>body{max-width:1000px;margin:24px auto;padding:20px;background:#12151a;color:#edf2f8;font:16px sans-serif}video,img{max-width:100%;height:auto}section{margin:40px 0}a{color:#a8d3ff}</style>',
            '<h1>④와 ⑭·⑮·⑯·⑰ 각각 비교</h1><p>항상 왼쪽 ④, 오른쪽 비교 구현. 모두 Original spatial SMAA와 camera/depth reprojection On. ④ Pattern On, 다른 구현 Off.</p>',
            '<p>실제 720프레임: 정지 1초 → 이동 10초 → 정지 1초. 정상 영상 12초/1배, 빠른 GIF 7.2초/1.67배, 느린 GIF 28.8초/0.42배. 원본 PNG에서 생성. 확대 nearest 2배, 전체 경로만 Lanczos 축소. 색·밝기 보정 없음. GIF 256색 및 MP4 압축 손실은 원본과 구분합니다.</p><p><a href="manifest.json">원본 경로와 검증 기록</a></p>']
    for case in CASES:
        page.append(f'<h2>④ ↔ {case}: {NAMES[case]}</h2>')
        for scene in results:
            for item in scene['results']:
                if item['case'] != case:
                    continue
                page += [f'<section><h3>{scene["scene"]} — {html.escape(item["title"])}</h3>',
                         f'<p>정상 12초</p><video controls loop muted playsinline preload="metadata" src="{Path(item["normal"]["path"]).name}"></video>',
                         f'<p>빠르게</p><img loading="lazy" src="{Path(item["fast"]["path"]).name}">',
                         f'<details><summary>느리게</summary><img loading="lazy" src="{Path(item["slow"]["path"]).name}"></details></section>']
    page.append('</html>')
    (out/'comparison.html').write_text('\n'.join(page),encoding='utf-8')
    print('PASS pair gallery',len(results),'scenes',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--palette-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scene',choices=['bistro','minecraft'])
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if args.scene:
        result = make_scene(args.scene,args.evidence.resolve(),out,args.palette_root.resolve())
        (out/f'{args.scene}-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    else:
        finish(out,args.evidence.resolve(),args.palette_root.resolve())
