"""Five independent implementations: verified actual-frame long playback.

This is presentation tooling. It neither combines shader implementations nor
computes a new quality score. Source PNGs and controls must match recorded hashes.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import PIL
from PIL import Image, ImageDraw, ImageFont, GifImagePlugin

ROOT = Path(__file__).resolve().parents[2]
try:
    import av
except ModuleNotFoundError:
    dependency_root = next(root for root in [ROOT, *ROOT.parents]
                           if (root / '.research-tools/quality-venv/Lib/site-packages/av').exists())
    # Import bundled Pillow/numpy first; append only the existing PyAV dependency.
    sys.path.append(str(dependency_root / '.research-tools/quality-venv/Lib/site-packages'))
    import av

FRAMES = 720
BASE = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080'
FONT = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 13)
SMALL = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 11)
LABELS = ['4 T2X-R JOn', '14 Base JOff', '15 Clip JOff', '16 5tap JOff', '17 Mix JOff']
ROIS = {
    'bistro': [
        ('chairs', '의자·테이블 다리', (1230, 546, 1358, 706)),
        ('thin-chair', '얇은 의자 구조', (1230, 582, 1358, 670)),
        ('windows', '창살과 반복 경계', (950, 460, 1110, 588)),
        ('scooter', '스쿠터 곡선과 가림 변화', (440, 715, 600, 843)),
        ('lamp', '가로등·화분 경계', (1630, 470, 1758, 630)),
        ('awning', '차양의 대각선 경계', (1320, 360, 1480, 488)),
    ],
    'minecraft': [
        ('seams', '벽 이음선과 가는 경계', (932, 512, 1060, 672)),
        ('thin-seam', '얇은 벽 이음선', (956, 524, 1020, 620)),
        ('leaves', '나뭇잎의 촘촘한 무늬', (1420, 590, 1580, 718)),
        ('grass-seam', '잔디 윗면의 약한 이음선', (1450, 665, 1552, 719)),
        ('stone-blocks', '흰 돌 구조물의 틈·모서리', (1150, 635, 1310, 795)),
        ('diagonal-beam', '대각선 돌 구조·잔디 단차', (470, 355, 614, 483)),
    ],
}
WINDOWS = [('moving', 130), ('late-moving', 480), ('transition', 658), ('still', 700)]


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def pixel_hash(im):
    return hashlib.sha256(im.tobytes()).hexdigest()


def phase(f):
    return 'initial still' if f < 60 else ('moving' if f < 660 else 'final still')


def compose(images, f, box=None):
    w, h = (384, 212) if box is None else ((box[2] - box[0]) * 2, (box[3] - box[1]) * 2)
    canvas = Image.new('RGB', (5 * (w + 8) + 8, h + 66), (18, 20, 23))
    draw = ImageDraw.Draw(canvas)
    for col, im in enumerate(images):
        x = 8 + col * (w + 8)
        draw.text((x, 6), LABELS[col], font=FONT, fill='white')
        draw.text((x, 25), f'f{f:03d} / {phase(f)}', font=SMALL, fill='#cdd7e1')
        draw.text((x, 41), 'full T' if col == 0 else 'edge T / w0.8', font=SMALL, fill='#cdd7e1')
        tile = im.resize((w, h), Image.Resampling.LANCZOS) if box is None else im.crop(box).resize((w, h), Image.Resampling.NEAREST)
        canvas.paste(tile, (x, 58))
    return canvas


class Video:
    def __init__(self, path, size):
        self.path, self.frames = path, 0
        self.out = av.open(str(path), 'w')
        self.stream = self.out.add_stream('libx264', rate=60)
        self.stream.width, self.stream.height = size
        self.stream.pix_fmt = 'yuv420p'
        self.stream.options = {'crf': '12', 'preset': 'fast', 'threads': '2'}

    def write(self, im):
        frame = av.VideoFrame.from_ndarray(np.asarray(im), format='rgb24')
        frame.pts, frame.time_base = self.frames, Fraction(1, 60)
        for packet in self.stream.encode(frame):
            self.out.mux(packet)
        self.frames += 1

    def close(self):
        for packet in self.stream.encode():
            self.out.mux(packet)
        self.out.close()
        with av.open(str(self.path)) as fp:
            stream = fp.streams.video[0]
            pts = [float(f.pts * f.time_base) for f in fp.decode(stream)]
            assert len(pts) == self.frames == FRAMES and stream.average_rate == 60
            assert all(b > a for a, b in zip(pts, pts[1:]))
        return dict(path=str(self.path), sha256=sha(self.path), frames=self.frames,
                    fps=60, seconds=self.frames / 60, playback_speed=1,
                    decoded_count_and_pts_verified=True, classification='lossy H264 CRF12 yuv420p presentation')


class Gif:
    def __init__(self, path, palette, stride, duration_ms):
        self.path, self.palette = path, palette
        self.stride, self.duration_ms = stride, duration_ms
        self.fp, self.hashes, self.indices = path.open('wb'), [], []

    def write(self, im, source_index, quantized=None):
        if source_index % self.stride:
            return
        if quantized is None:
            quantized = im.quantize(palette=self.palette, dither=Image.Dither.NONE)
        if not self.hashes:
            for block in GifImagePlugin.getheader(quantized, info={'loop': 0, 'optimize': False})[0]:
                self.fp.write(block)
        for block in GifImagePlugin.getdata(quantized, duration=self.duration_ms, disposal=2, include_color_table=False):
            self.fp.write(block)
        self.hashes.append(pixel_hash(quantized.convert('RGB')))
        self.indices.append(source_index)
        return quantized

    def close(self):
        self.fp.write(b';')
        self.fp.close()
        total_ms = 0
        with Image.open(self.path) as fp:
            assert fp.n_frames == len(self.hashes) == FRAMES // self.stride
            for i, expected in enumerate(self.hashes):
                fp.seek(i)
                total_ms += fp.info['duration']
                assert pixel_hash(fp.convert('RGB')) == expected, (self.path, i, 'GIF decode changed')
        assert total_ms == len(self.hashes) * self.duration_ms
        return dict(path=str(self.path), sha256=sha(self.path), source_indices=self.indices,
                    frames=len(self.hashes), seconds=total_ms / 1000,
                    fps=1000 / self.duration_ms, playback_speed=self.stride * 1000 / self.duration_ms / 60,
                    decoded_pixel_hashes_verified=True, classification='lossy fixed 256-color palette, no dithering')


def verify_capture(info, scene, meta):
    assert info['validation'] == 'PASS'
    assert info['control_rgb_mismatch'] == 0 and info['control_bridge']['rgb_mismatch'] == 0
    receipt = info['receipt']
    assert receipt['phase'] == 'Capture' and receipt['scene'] == scene
    assert receipt['frames'] == FRAMES and receipt['start_time'] == 2
    assert sha(receipt['report']).upper() == receipt['report_sha256']
    text = Path(receipt['report']).read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and 'Aggregate: FAIL' not in text
    rows = [[c.strip() for c in row] for row in csv.reader(text.splitlines())]
    timeline = next(r for r in rows if r and r[0] == 'presentation_timeline')
    assert timeline[1:6] == ['720', '60', '600', '60', '60fps'] and float(timeline[6]) == 2
    assert not any(r and r[0] == 'trace' for r in rows), 'Long capture must not save diagnostic trace'
    for mode in ['O-T2X-R', BASE, meta['semantic_id']]:
        checks = [r for r in rows if r and r[0] == 'mode_check' and r[1] == mode]
        assert [int(r[2]) for r in checks] == list(range(FRAMES)) and all(r[4] == 'PASS' for r in checks)
        paths = sorted((Path(info['capture_root']) / mode).glob('frame_[0-9][0-9][0-9][0-9][0-9].png'))
        assert len(paths) == FRAMES and len(info['output_hashes'][mode]) == FRAMES
    return dict(report_sha256=sha(receipt['report']), mode_checks=FRAMES * 3, diagnostics_off=True,
                initial_still=60, moving=600, final_still=60, source_fps=60)


def make_scene(scene, evidence, out):
    metadata = {i: load(evidence / f'case{i}/case.json') for i in [15, 16, 17]}
    infos = {i: load(evidence / f'case{i}/{scene}-long-capture.json') for i in metadata}
    validations = {i: verify_capture(infos[i], scene, metadata[i]) for i in metadata}
    for case in [16, 17]:
        for mode in ['O-T2X-R', BASE]:
            assert infos[case]['output_hashes'][mode] == infos[15]['output_hashes'][mode], (scene, case, mode, 'control mismatch')
    sources = [(15, 'O-T2X-R'), (15, BASE)] + [(i, metadata[i]['semantic_id']) for i in [15, 16, 17]]

    def images(f):
        ims = []
        for case, mode in sources:
            path = Path(infos[case]['capture_root']) / mode / f'frame_{f:05d}.png'
            with Image.open(path) as fp:
                im = fp.convert('RGB')
            assert im.size == (1920, 1061) and pixel_hash(im) == infos[case]['output_hashes'][mode][f], (scene, mode, f)
            ims.append(im)
        return ims

    specs = [('overview', '전체 이동 경로', None)] + ROIS[scene]
    sample_frames = sorted({0, 60, 130, 180, 360, 480, 600, 659, 660, 700, 719})
    atlases = {name: Image.new('RGB', (600, len(sample_frames) * 180)) for name, _, _ in specs}
    for row, f in enumerate(sample_frames):
        ims = images(f)
        for name, _, box in specs:
            atlases[name].paste(compose(ims, f, box).resize((600, 180), Image.Resampling.NEAREST), (0, row * 180))
    first = images(0)
    writers = {}
    for name, _, box in specs:
        palette = atlases[name].quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        prefix = f'{scene}-{name}-long'
        writers[name] = (Video(out / f'{prefix}-normal.mp4', compose(first, 0, box).size),
                         Gif(out / f'{prefix}-slow.gif', palette, 1, 40),
                         Gif(out / f'{prefix}-fast.gif', palette, 2, 20))
    sheets = []
    sheet_starts = {start + 2 * pair: (window, pair) for window, start in WINDOWS for pair in range(3)}
    pending = {}
    for f in range(FRAMES):
        ims = first if f == 0 else images(f)
        for name, _, box in specs:
            view = compose(ims, f, box)
            video, slow, fast = writers[name]
            video.write(view)
            quantized = slow.write(view, f)
            fast.write(view, f, quantized)
            if box is not None and f in sheet_starts:
                pending[name] = view.copy()
            if box is not None and f - 1 in sheet_starts:
                window, pair = sheet_starts[f - 1]
                sheet = Image.new('RGB', (view.width, view.height * 2))
                sheet.paste(pending.pop(name), (0, 0))
                sheet.paste(view, (0, view.height))
                path = out / f'{scene}-{name}-{window}-pair{pair}.png'
                sheet.save(path)
                sheets.append(dict(path=str(path), roi=box, name=name, window=window,
                                   frames=[f - 1, f], filter='nearest', scale=2, tone_adjustment=False))
        if f in [130, 480, 660, 700]:
            # Full original PNGs remain available independently of overview resizing.
            for i, im in enumerate(ims):
                im.save(out / f'{scene}-case{[4,14,15,16,17][i]}-full-f{f}.png')
        if f % 60 == 0:
            print('Verified five-way source/media progress', scene, f, '/720', flush=True)
    results = []
    for name, title, box in specs:
        video, slow, fast = writers[name]
        results.append(dict(name=name, title=title, roi=box, filter='Lanczos overview' if box is None else 'nearest',
                            scale=None if box is None else 2, normal=video.close(), slow=slow.close(), fast=fast.close()))
        print('PASS decoded media', scene, name, flush=True)
    return dict(scene=scene, source_frames=FRAMES, source_fps=60, source_validation=validations,
                controls_shared_frames=FRAMES * 4, control_rgb_mismatch=0, source_pngs_checked=FRAMES * 5,
                evidence_sha256={i: sha(evidence / f'case{i}/{scene}-long-capture.json') for i in metadata},
                stable_hash_counts={m: len(set(infos[i]['output_hashes'][m][700:720])) for i, m in sources},
                results=results, inspection_sheets=sheets)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scene', choices=['bistro', 'minecraft', 'all'], default='all')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    print('Media libraries', PIL.__version__, np.__version__, av.__version__, flush=True)
    scenes = ['bistro', 'minecraft'] if args.scene == 'all' else [args.scene]
    for scene in scenes:
        result = make_scene(scene, args.evidence.resolve(), out)
        (out / f'{scene}-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    results = [load(out / f'{scene}-manifest.json') for scene in ['bistro', 'minecraft'] if (out / f'{scene}-manifest.json').exists()]
    manifest = dict(validation='PASS', classification='extended presentation only; no new quality score or GPU timing',
                    mode_order=[4, 14, 15, 16, 17], independent_implementations=True,
                    source_timeline='60 still + 600 moving + 60 still at fixed60',
                    fast='every second source frame; 50fps; 7.2s; 1.6667x',
                    slow='all source frames; 25fps; 28.8s; 0.4167x',
                    normal='all source frames; 60fps; 12s; 1x',
                    actual_playback_observed=False, results=results)
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    html = ['<!doctype html><html lang="ko"><meta charset="utf-8"><title>④·⑭·⑮·⑯·⑰ 긴 비교</title>',
            '<style>body{max-width:1600px;margin:30px auto;padding:20px;background:#12151a;color:#edf2f8;font:16px sans-serif}video,img{max-width:100%;height:auto}section{margin:48px 0}a{color:#a8d3ff}</style>',
            '<h1>④·⑭·⑮·⑯·⑰: 다른 세부 장면과 긴 이동</h1>',
            '<p>왼쪽부터 ④ 원본 SMAA T2X-R / ⑭ fixed0.8 / ⑮ clipping / ⑯ source 5-fetch / ⑰ gamma2 blend. 각 변경은 ⑭에서 독립 분기했습니다. 모두 Original spatial SMAA·camera/depth reprojection On. ④ Pattern On, 나머지 Off입니다.</p>',
            '<p>두 실제 3D 장면 Bistro·Minecraft에서 12개 세부 영역을 비교합니다. 세부 영역은 화면 고정이며 물체를 추적하지 않습니다. 확대는 nearest 2배, 전체 경로만 Lanczos 축소입니다. 색·밝기 보정은 없습니다.</p>',
            '<p>실제 720프레임: 정지 1초 → 연속 이동 10초 → 정지 1초. 반복·보간으로 길이를 늘리지 않았습니다. 정상 MP4 12초, 빠른 GIF 7.2초(1.67배), 느린 GIF 28.8초(0.42배). 빠른 GIF는 홀수 프레임을 생략하므로 세밀한 결함 판단에는 정상 영상·느린 GIF·연속 원본 PNG를 함께 확인하십시오. GIF 256색/MP4 압축에는 손실이 있습니다.</p>',
            '<p>기존 GPU 성능·품질 점수는 그대로입니다. 이번 자료는 긴 재생 비교와 원본 프레임 검사이며 새 품질 점수 측정이 아닙니다. <a href="manifest.json">검증 및 원본 경로</a></p>']
    for scene in results:
        for item in scene['results']:
            html += [f'<section><h2>{scene["scene"]} — {item["title"]}</h2>',
                     f'<p>정상 속도 · 실제 12초</p><video controls loop muted playsinline preload="metadata" src="{Path(item["normal"]["path"]).name}"></video>',
                     f'<p>빠르게 · 1.67배 / 7.2초</p><img loading="lazy" src="{Path(item["fast"]["path"]).name}">',
                     f'<details><summary>느리게 · 0.42배 / 28.8초</summary><img loading="lazy" src="{Path(item["slow"]["path"]).name}"></details>']
            if item['roi'] is not None:
                html.append('<details><summary>이동·이동 후반·정지 전환·안정 구간의 연속 6프레임</summary>')
                for sheet in scene['inspection_sheets']:
                    if sheet['name'] == item['name']:
                        filename = Path(sheet['path']).name
                        html.append(f'<p>{sheet["window"]} · {sheet["frames"]}</p><a href="{filename}"><img loading="lazy" src="{filename}"></a>')
                html.append('</details>')
            html.append('</section>')
    html.append('</html>')
    (out / 'comparison.html').write_text('\n'.join(html), encoding='utf-8')
    print('PASS extended playback sources, controls, GIF decoded pixels, MP4 count/PTS', flush=True)


if __name__ == '__main__':
    main()
