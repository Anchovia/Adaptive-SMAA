"""Create synchronized visual comparisons from the six corrected capture sets.

No renderer invocation, retiming by interpolation, brightness adjustment, or new
quality score. Source RGB is checked against each pinned branch's recorded hashes.
"""
import argparse
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'Docs/Six-Case-Stencil-Lifecycle'
LABELS = ['① AA-Off', '② SMAA 1X', '③ Temporal-only',
          '④ SMAA T2X-R', '⑤ Edge temporal-only', '⑥ SMAA + edge temporal']
CLIPS = [
    dict(id='bistro-chairs-moving', scene='bistro', title='Bistro · 의자 다리 / 이동',
         roi=[1190, 530, 1478, 722], start=100, end=160, fps=30),
    dict(id='minecraft-thin-edges-moving', scene='minecraft', title='Minecraft · 얇은 경계 / 이동',
         roi=[780, 460, 1068, 652], start=100, end=160, fps=30),
    dict(id='minecraft-leaves-stop', scene='minecraft', title='Minecraft · 나뭇잎 / 이동 → 정지',
         roi=[1180, 770, 1468, 962], start=160, end=220, fps=15),
    dict(id='bistro-window-stop', scene='bistro', title='Bistro · 창살 / 이동 → 정지',
         roi=[880, 430, 1168, 622], start=160, end=220, fps=15),
]
BG, FG, MUTED, ACCENT = '#111821', '#eef2f7', '#aebccc', '#f3c969'
FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 20)
BOLD = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 23)
SMALL = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 17)
TW, TH, LH, TOP, FOOT = 576, 384, 38, 82, 32


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def sources(scene, summary):
    result = []
    for entry in summary['branches']:
        n = entry['case']
        cfg = json.loads((DOC/f'case{n}'/'case.json').read_text())
        cap = json.loads((DOC/f'case{n}'/f'{scene}-capture.json').read_text())
        assert cap['validation'] == 'PASS' and cap['frames_per_mode'] == 240
        assert not any(cap['mismatched_frames'].values())
        raw = subprocess.check_output(['git', 'show', entry['commit']+
            f':Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json'], cwd=ROOT)
        hashes = json.loads(raw)[cfg['target']]
        assert len(hashes) == 240
        folder = Path(cap['capture'])/cfg['target']
        assert folder.is_dir(), folder
        result.append(dict(case=n, branch=entry['branch'], commit=entry['commit'],
                           target=cfg['target'], folder=str(folder), hashes=hashes))
    assert [s['case'] for s in result] == list(range(1, 7))
    return result


def load_crops(clip, src):
    crops, digest = [], hashlib.sha256()
    for f in range(clip['start'], clip['end']):
        row = []
        for s in src:
            p = Path(s['folder'])/f'frame_{f:05d}.png'
            with Image.open(p) as im:
                assert im.mode == 'RGB' and im.size == (1920, 1061), p
                h = hashlib.sha256(im.tobytes()).hexdigest()
                assert h == s['hashes'][f], (s['case'], f, 'RGB hash mismatch')
                digest.update(h.encode('ascii'))
                row.append(im.crop(clip['roi']))
        crops.append(row)
    return crops, digest.hexdigest()


def tile(im, case):
    canvas = Image.new('RGB', (TW, TH+LH), BG)
    ImageDraw.Draw(canvas).text((12, 6), LABELS[case-1], font=FONT, fill=FG)
    scaled = im.resize((TW, TH), Image.Resampling.NEAREST)
    canvas.paste(scaled, (0, LH))
    assert ImageChops.difference(canvas.crop((0, LH, TW, TH+LH)), scaled).getbbox() is None
    return canvas


def render(row, clip, f, single=None, realtime=False):
    width, height = (TW*2, TOP+(TH+LH)*3+FOOT) if single is None else (TW, TOP+TH+LH+FOOT)
    canvas = Image.new('RGB', (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 6), clip['title'], font=BOLD, fill=FG)
    speed = 1 if realtime else clip['fps']/60
    phase = '정지' if f >= 180 else '이동'
    draw.text((12, 44), f'2배 확대 · {speed:g}배속 · frame {f:03d} · {phase}', font=FONT,
              fill=ACCENT if f >= 180 else MUTED)
    if single is None:
        for i, im in enumerate(row):
            canvas.paste(tile(im, i+1), ((i%2)*TW, TOP+(i//2)*(TH+LH)))
    else:
        canvas.paste(tile(row[single-1], single), (0, TOP))
    draw.text((12, height-26), '③·④ 지터 On / ⑤·⑥ Off · 화면 고정 영역', font=SMALL, fill=MUTED)
    return canvas


def shared_palette(crops):
    # The same palette is used for every time point AND all six configurations.
    frames = range(0, len(crops), max(1, len(crops)//10))
    samples = [im for i in frames for im in crops[i]]
    w, h = samples[0].size
    atlas = Image.new('RGB', (w*6, h*((len(samples)+5)//6)))
    for i, im in enumerate(samples):
        atlas.paste(im, ((i%6)*w, (i//6)*h))
    base = atlas.quantize(colors=248, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    colors = base.getpalette()[:248*3]
    colors += [17,24,33, 238,242,247, 174,188,204, 243,201,105,
               0,0,0, 255,255,255, 80,95,110, 140,153,168]
    palette = Image.new('P', (1,1))
    palette.putpalette(colors)
    return palette


def save_gif(path, frames, palette, fps):
    indexed = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    durations = [10*(round((i+1)*100/fps)-round(i*100/fps)) for i in range(len(frames))]
    indexed[0].save(path, save_all=True, append_images=indexed[1:], duration=durations,
                    loop=0, disposal=2, optimize=False)
    with Image.open(path) as check:
        assert check.n_frames == len(frames)
        for i, expected in enumerate(indexed):
            check.seek(i)
            assert check.info['duration'] == durations[i]
            assert check.convert('RGB').tobytes() == expected.convert('RGB').tobytes()
    return dict(path=str(path.resolve()), sha256=sha(path), frames=len(frames),
                duration_ms=sum(durations), average_fps=fps, fixed_shared_palette=True,
                dither=False, decoded_quantized_rgb_exact=True)


def save_mp4(path, frames):
    with av.open(str(path), 'w') as out:
        stream = out.add_stream('libx264', rate=60)
        stream.width, stream.height = frames[0].size
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf':'10', 'preset':'fast'}
        stream.time_base = Fraction(1,60)
        for i, im in enumerate(frames):
            f = av.VideoFrame.from_ndarray(np.asarray(im), format='rgb24')
            f.pts, f.time_base = i, Fraction(1,60)
            for packet in stream.encode(f): out.mux(packet)
        for packet in stream.encode(): out.mux(packet)
    with av.open(str(path)) as inp:
        stream = inp.streams.video[0]
        assert stream.average_rate == 60
        times = [f.pts*stream.time_base for f in inp.decode(video=0)]
        assert len(times) == len(frames)
        assert all(b-a == Fraction(1,60) for a,b in zip(times,times[1:]))
    return dict(path=str(path.resolve()), sha256=sha(path), frames=len(frames), fps=60,
                pts_verified=True, encoding='H264 CRF10 yuv420p; playback, not lossless evidence')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--clip', choices=[c['id'] for c in CLIPS])
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = json.loads((DOC/'summary.json').read_text())
    assert summary['validation'] == 'PASS' and summary['native_reference_cross_branch_rgb_equal']
    selected = [c for c in CLIPS if args.clip is None or c['id'] == args.clip]
    for clip in selected:
        out = args.output/clip['id']; out.mkdir(exist_ok=True)
        if (out/'manifest.json').exists():
            previous = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            assert previous['summary_sha256'] == sha(DOC/'summary.json')
            for item in [previous['comparison_gif'], previous['realtime_video'], *previous['individual_gifs']]:
                assert sha(item['path']) == item['sha256']
            print(clip['id'], 'already verified', flush=True)
            continue
        src = sources(clip['scene'], summary)
        crops, digest = load_crops(clip, src)
        print(clip['id'], '360 source frames RGB exact', flush=True)
        pal = shared_palette(crops)
        frames = [render(row, clip, clip['start']+i) for i,row in enumerate(crops)]
        grid = save_gif(out/'six-way.gif', frames, pal, clip['fps'])
        frames[len(frames)//2].save(out/'preview.png')
        del frames
        individual = []
        for n in range(1,7):
            frames = [render(row, clip, clip['start']+i, single=n) for i,row in enumerate(crops)]
            individual.append(save_gif(out/f'case{n}.gif', frames, pal, clip['fps']))
            del frames
        frames = [render(row, clip, clip['start']+i, realtime=True) for i,row in enumerate(crops)]
        video = save_mp4(out/'six-way-60fps.mp4', frames)
        del frames
        # Full-color, adjacent original frames for checking stop/ghosting details.
        indices = [179,180,181,182] if clip['start'] == 160 else [128,129,130,131]
        sequence = Image.new('RGB', (TW*2, 50+6*(192+30)), BG)
        draw = ImageDraw.Draw(sequence)
        draw.text((12,8), '원본 RGB · 인접 프레임 · '+str(indices), font=FONT, fill=FG)
        for case in range(6):
            y=50+case*222
            draw.text((10,y+2), LABELS[case], font=FONT, fill=FG)
            for col,f in enumerate(indices): sequence.paste(crops[f-clip['start']][case], (col*288,y+30))
        sequence.save(out/'adjacent-original-rgb.png')
        metadata = dict(validation='PASS', clip=clip, case_order=LABELS,
                        layout='2 columns x 3 rows: [1,2] / [3,4] / [5,6]',
                        summary_sha256=sha(DOC/'summary.json'), source_fps=60,
                        crop_scale=2, spatial_resize='nearest neighbor', color_adjustment='none',
                        frame_interpolation=False, source_rgb_verified_count=len(crops)*6,
                        source_rgb_digest=digest,
                        sources=[{k:v for k,v in s.items() if k!='hashes'} for s in src],
                        comparison_gif=grid, individual_gifs=individual, realtime_video=video,
                        original_rgb_sequence=str((out/'adjacent-original-rgb.png').resolve()),
                        interpretation='Visual inspection only. GIF has 256-color quantization. '
                        'No new quality score or absolute ghosting claim. Pattern On 3/4 vs Off 5/6. '
                        'Screen-fixed ROIs; only camera motion, not moving-object validation.')
        dump(out/'manifest.json', metadata)
        print(clip['id'], 'PASS: 7 GIFs, verified 60fps video, original RGB sheet', flush=True)
    manifests=[json.loads((args.output/c['id']/'manifest.json').read_text(encoding='utf-8'))
               for c in CLIPS if (args.output/c['id']/'manifest.json').exists()]
    dump(args.output/'manifest.json', dict(validation='PASS', clips=manifests))


if __name__ == '__main__': main()
