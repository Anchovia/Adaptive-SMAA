"""Use all 240 captured frames for 8-second GIFs and native-speed playback."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

from create_persistence_audit_visuals import BG, DOC, MODES, OUT, ROIS, compose, sha
from create_temporal_contrast_playback import encode


def save_gif(path, frames):
    # Include every frame and every case when building the single fixed palette.
    atlas = Image.new('RGB', (frames[0].width, frames[0].height * len(frames)))
    for i, frame in enumerate(frames):
        atlas.paste(frame, (0, i * frame.height))
    palette = atlas.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    indexed = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    durations = [30, 30, 40] * 80
    indexed[0].save(path, save_all=True, append_images=indexed[1:], duration=durations,
                    loop=0, disposal=1, optimize=False)
    with Image.open(path) as opened:
        assert opened.n_frames == 240 and opened.info['loop'] == 0
        for i, frame in enumerate(ImageSequence.Iterator(opened)):
            assert frame.info['duration'] == durations[i]
            assert np.array_equal(np.asarray(frame.convert('RGB')), np.asarray(indexed[i].convert('RGB')))
    return dict(path=str(path), frames=240, duration_ms=8000, playback_speed=0.5,
                fixed_palette=True, dithering=False, decoded_frames_verified=True,
                sha256=sha(path.read_bytes()))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    crops = {}
    sources = {}
    for scene in ('bistro', 'minecraft'):
        receipt = json.loads((DOC / f'{scene}-capture.json').read_text(encoding='utf-8'))
        cap = Path(receipt['capture_root'])
        selected = [r for r in ROIS if r[0] == scene]
        hashes = {}
        for case, mode, _, _ in MODES:
            hashes[case] = []
            for i in range(240):
                with Image.open(cap / mode / f'frame_{i:05d}.png') as opened:
                    rgb = opened.convert('RGB')
                    assert rgb.size == (1920, 1061)
                    digest = sha(rgb.tobytes())
                    assert digest == receipt['output_hashes'][mode][i], (scene, mode, i)
                    hashes[case].append(digest)
                    for _, name, _, roi, _ in selected:
                        crops[name, case, i] = rgb.crop(roi)
        assert hashes['7'] == hashes['8']
        sources[scene] = dict(capture_root=str(cap), modes=dict((m[0], m[1]) for m in MODES),
                              validated_rgb_frames=960, case7_vs_case8_mismatches=0,
                              receipt_sha256=sha((DOC / f'{scene}-capture.json').read_bytes()))
        print(f'PASS all 960 source RGB hashes: {scene}', flush=True)

    records = []
    for scene, name, title, roi, scale in ROIS:
        def render(i, slow=False):
            phase = '시작 정지' if i < 60 else ('이동' if i < 180 else '이동 후 정지')
            speed = '30 fps 재생 · 0.5배속 · 전체 8초' if slow else '60 fps 재생 · 정상 속도 · 전체 4초'
            frame = compose(title, i, phase, [crops[name, c, i] for c, _, _, _ in MODES], scale, speed)
            padded = Image.new('RGB', (frame.width, frame.height + frame.height % 2), BG)
            padded.paste(frame, (0, 0))
            return padded

        mp4 = encode(OUT / f'{name}-full-60fps.mp4', render, 240, fps=60)
        print(f'PASS normal-speed MP4: {name}', flush=True)
        frames = [render(i) for i in range(240)]
        webp = OUT / f'{name}-full-realtime.webp'
        durations = [17, 17, 16] * 80
        frames[0].save(webp, save_all=True, append_images=frames[1:], duration=durations,
                       lossless=True, quality=100, loop=0, method=4)
        with Image.open(webp) as opened:
            assert opened.n_frames == 240
            for i, frame in enumerate(ImageSequence.Iterator(opened)):
                rgb = frame.convert('RGB')  # Forces loading the frame's timestamp metadata.
                assert np.array_equal(np.asarray(rgb), np.asarray(frames[i]))
                assert opened.info['duration'] == durations[i]
        del frames
        gif = save_gif(OUT / f'{name}-full-half-speed.gif', [render(i, True) for i in range(240)])
        for i in (60, 100, 130, 180, 192):
            render(i).save(OUT / f'{name}-full-f{i:03d}.png')
        records.append(dict(scene=scene, name=name, roi=roi, scale=scale, gif=gif, mp4=mp4,
                            lossless_webp=dict(path=str(webp), frames=240, duration_ms=4000,
                                durations_ms=durations, pixel_exact=True, sha256=sha(webp.read_bytes()))))
        print(f'PASS 8-second GIF and realtime lossless WebP: {name}', flush=True)
    manifest = dict(source_fps=60, source_frames=[0, 239], source_duration_seconds=4,
                    classification='longer playback of existing captures; not a longer camera path or new GPU run',
                    timeline={'initial_still': [0, 59], 'moving': [60, 179], 'final_still': [180, 239]},
                    case_order=['4', '6', '7', '8'], sources=sources, media=records,
                    display_limits='MP4 is CRF12 yuv420p presentation; GIF has 256 colors. WebP preserves composed RGB.')
    (DOC / 'long-playback-4-6-7-8.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    blocks = []
    for _, name, title, _, _ in ROIS:
        blocks.append(f'<section><h2>{title}</h2><p>정상 속도 · 60fps · 실제 4초</p>'
                      f'<video controls loop muted playsinline src="{name}-full-60fps.mp4"></video>'
                      f'<p><a href="{name}-full-realtime.webp">정상 속도 무손실 WebP</a></p>'
                      f'<p>전체 프레임 · 0.5배속 · 8초 (이전 GIF의 3배 속도)</p><img src="{name}-full-half-speed.gif"></section>')
    (OUT / 'long-playback.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<title>전체 타임라인 · ④ ⑥ ⑦ ⑧</title><style>body{background:#141719;color:#eee;font:16px sans-serif;max-width:1120px;margin:32px auto}a{color:#acd3ff}img,video{max-width:100%}section{margin-top:48px}</style>'
        '<h1>④ 원본 · ⑥ 현재 edge · ⑦ 개선 전 · ⑧ 개선 후</h1>'
        '<p>모두 spatial SMAA 적용. ④ Pattern On, ⑥·⑦·⑧ Off. 기존 전체 240프레임: 정지 1초 → 이동 2초 → 정지 1초. ⑦·⑧ 출력 동일.</p>'
        + ''.join(blocks) + '</html>', encoding='utf-8')
    print('PASS all long playback exports', flush=True)


if __name__ == '__main__':
    main()
