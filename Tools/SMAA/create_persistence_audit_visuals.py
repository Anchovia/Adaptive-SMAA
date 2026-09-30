"""Present existing GPU captures as case 4/6/7/8; do not run the renderer."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageSequence

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'Docs/Edge-Persistence-Cost-Audit'
OUT = ROOT / 'Projects/CMAA2/Captures/edge-persistence-4-6-7-8-20261001'
MODES = [
    ('4', 'O-T2X-R', '④ 원본 T2X-R', 'Pattern On'),
    ('6', 'A-CurrentEdge-Stencil', '⑥ 현재 edge', 'Pattern Off'),
    ('7', 'B-PreviousRawEdge-Depth', '⑦ 직전 edge · 개선 전', 'Pattern Off'),
    ('8', 'E-PreviousRawEdge-FirstStencil', '⑧ 직전 edge · 개선 후', 'Pattern Off'),
]
ROIS = [
    ('minecraft', 'minecraft-thin-line', 'Minecraft · 얇은 선', (956, 524, 1020, 620), 3),
    ('bistro', 'bistro-chairs', 'Bistro · 의자', (1230, 582, 1358, 670), 2),
    ('bistro', 'bistro-window', 'Bistro · 창문', (906, 470, 1034, 558), 2),
]
WINDOWS = [
    ('moving', '이동', list(range(126, 156)), list(range(130, 136))),
    ('stop', '이동 → 정지', list(range(172, 196)), list(range(178, 184))),
    ('still', '정지', list(range(190, 196)), list(range(190, 196))),
]
FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 17)
SMALL = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
BG = '#141719'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compose(title, frame, phase, tiles, scale, playback_note=None):
    width = max(224, tiles[0].width * scale)
    height = tiles[0].height * scale
    gap = 12
    canvas = Image.new('RGB', (4 * width + 5 * gap, height + 115), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 5), f'{title} | f{frame:03d} | {phase}', font=FONT, fill='white')
    speed = playback_note or '60 fps 원본 → 10 fps 재생 (1/6배속)'
    draw.text((gap, 30), f'{speed} · {scale}배 확대 · 색 보정 없음', font=SMALL, fill='#c7ccd1')
    for j, (tile, mode) in enumerate(zip(tiles, MODES)):
        x = gap + j * (width + gap)
        draw.text((x, 58), mode[2], font=FONT, fill='white')
        draw.text((x, 81), mode[3], font=SMALL, fill='#c7ccd1')
        enlarged = tile.resize((tile.width * scale, height), Image.Resampling.NEAREST)
        canvas.paste(enlarged, (x + (width - enlarged.width) // 2, 108))
    return canvas


def save_animation(name, frames):
    # One palette learned from the complete sequence and all four modes.
    # No per-frame palette changes or dithering: neither may invent flicker.
    atlas = Image.new('RGB', (frames[0].width, frames[0].height * len(frames)))
    for i, frame in enumerate(frames):
        atlas.paste(frame, (0, i * frame.height))
    palette = atlas.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    gif = OUT / f'{name}.gif'
    webp = OUT / f'{name}.webp'
    quantized[0].save(gif, save_all=True, append_images=quantized[1:],
                      duration=100, loop=0, optimize=False, disposal=1)
    frames[0].save(webp, save_all=True, append_images=frames[1:],
                   duration=100, loop=0, lossless=True, quality=100, method=4)
    error_sum = 0
    pixel_count = 0
    max_error = 0
    with Image.open(gif) as decoded:
        assert decoded.n_frames == len(frames)
        assert decoded.info['loop'] == 0
        for i, actual in enumerate(ImageSequence.Iterator(decoded)):
            assert actual.info['duration'] == 100
            arr = np.asarray(actual.convert('RGB'))
            assert np.array_equal(arr, np.asarray(quantized[i].convert('RGB')))
            error = np.abs(arr.astype(np.int16) - np.asarray(frames[i]).astype(np.int16))
            error_sum += int(error.sum())
            pixel_count += error.size
            max_error = max(max_error, int(error.max()))
    with Image.open(webp) as decoded:
        assert decoded.n_frames == len(frames)
        for i, actual in enumerate(ImageSequence.Iterator(decoded)):
            assert np.array_equal(np.asarray(actual.convert('RGB')), np.asarray(frames[i]))
    return dict(gif=str(gif), lossless_webp=str(webp),
                gif_sha256=sha(gif.read_bytes()), webp_sha256=sha(webp.read_bytes()),
                gif_mean_rgb_error=error_sum / pixel_count, gif_max_rgb_error=max_error,
                decoded_frame_count=len(frames), duration_ms=100,
                lossless_webp_pixel_exact=True, gif_decoded_matches_quantized=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sorted({f for _, _, frames, sheets in WINDOWS for f in frames + sheets})
    sources = {}
    crops = {}
    for scene in ('bistro', 'minecraft'):
        receipt = json.loads((DOC / f'{scene}-capture.json').read_text(encoding='utf-8'))
        capture = Path(receipt['capture_root'])
        assert all(v == 0 for v in receipt['mismatched_frames'].values())
        selected = [roi for roi in ROIS if roi[0] == scene]
        records = {}
        for case, mode, _, _ in MODES:
            paths = sorted((capture / mode).glob('frame_[0-9][0-9][0-9][0-9][0-9].png'))
            assert [p.name for p in paths] == [f'frame_{i:05d}.png' for i in range(240)]
            records[case] = dict(mode=mode, frames={})
            for index in wanted:
                path = capture / mode / f'frame_{index:05d}.png'
                with Image.open(path) as opened:
                    rgb = opened.convert('RGB')
                    assert rgb.size == (1920, 1061)
                    digest = sha(rgb.tobytes())
                    assert digest == receipt['output_hashes'][mode][index], (scene, mode, index)
                    records[case]['frames'][str(index)] = digest
                    for _, name, _, roi, _ in selected:
                        crops[name, case, index] = rgb.crop(roi)
        assert records['7']['frames'] == records['8']['frames']
        sources[scene] = dict(capture_root=str(capture), frames=records,
                              case7_vs_case8_full_rgb_mismatches=0,
                              receipt_sha256=sha((DOC / f'{scene}-capture.json').read_bytes()))
        print(f'PASS {scene}: {len(wanted)} frames x 4 sources match stored RGB hashes', flush=True)
    media = []
    for scene, name, title, roi, scale in ROIS:
        for window, phase, indices, six in WINDOWS:
            def render(index):
                return compose(title, index, phase,
                               [crops[name, case, index] for case, _, _, _ in MODES], scale)
            frames = [render(index) for index in indices]
            record = save_animation(f'{name}-{window}', frames)
            sheet = Image.new('RGB', (frames[0].width, frames[0].height * len(six)), BG)
            for row, index in enumerate(six):
                sheet.paste(render(index), (0, row * frames[0].height))
            sheet_path = OUT / f'{name}-{window}-six.png'
            sheet.save(sheet_path)
            record.update(scene=scene, name=f'{name}-{window}', roi=roi, scale=scale,
                          frames=indices, six_frames=six, sheet=str(sheet_path))
            media.append(record)
            print(f'PASS media {name}-{window}', flush=True)
    manifest = dict(classification='presentation of existing GPU captures; no new quality or performance run',
                    case_order=[m[0] for m in MODES],
                    case_mapping=[dict(case=m[0], mode=m[1], label=m[2], pattern=m[3]) for m in MODES],
                    source_fps=60, playback_fps=10, enlargement='nearest; no color correction',
                    palette='one sequence-wide palette shared by all cases; dithering off',
                    selected_source_frames=wanted, sources=sources, media=media)
    (DOC / 'visuals-4-6-7-8.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    blocks = []
    for _, name, title, _, _ in ROIS:
        items = []
        for window, phase, _, _ in WINDOWS:
            stem = f'{name}-{window}'
            items.append(f'<h3>{phase}</h3><img src="{stem}.gif"><p><a href="{stem}.webp">무손실 WebP</a> · <a href="{stem}-six.png">연속 6프레임 PNG</a></p>')
        blocks.append(f'<section><h2>{title}</h2>{"".join(items)}</section>')
    (OUT / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>④ ⑥ ⑦ ⑧ 비교</title>'
        '<style>body{background:#141719;color:#eee;font:16px sans-serif;max-width:1120px;margin:32px auto}a{color:#acd3ff}img{max-width:100%}section{margin-top:48px}</style>'
        '<h1>④ 원본 · ⑥ 현재 edge · ⑦ 개선 전 · ⑧ 개선 후</h1>'
        '<p>모두 spatial SMAA 적용. ④ Pattern On, ⑥·⑦·⑧ Off. ⑦·⑧은 실제 별도 캡처이며 RGB가 같습니다. 60 fps 입력을 10 fps로 재생합니다.</p>'
        + ''.join(blocks) + '</html>', encoding='utf-8')
    print(f'PASS manifest and gallery: {OUT}', flush=True)


if __name__ == '__main__':
    main()
