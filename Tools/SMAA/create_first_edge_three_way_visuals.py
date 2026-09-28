"""Aligned No-TAA / first-edge / native crops from existing validated PNGs."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from create_temporal_contrast_playback import encode, gif

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'Docs/Temporal-First-Edge-Quality'
OUT = ROOT / 'Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay'
MODES = ['DBG-CurrentSpatial-R', 'ABL-FirstEdge-Reuse-R', 'O-T2X-R']
LABELS = ['No-TAA (jitter ON)', 'Edge-selective T2X-R', 'Original T2X-R']
CLIPS = [
    ('bistro-thin-lines-moving', 'bistro', (360, 590, 720, 830), 90, 150, 3,
     'Bistro: chair legs / table frames / pavement'),
    ('minecraft-moving-boundary', 'minecraft', (960, 280, 1320, 520), 90, 150, 1,
     'Minecraft: moving foreground edge / background reveal'),
    ('minecraft-motion-to-still', 'minecraft', (300, 520, 660, 760), 160, 220, 1,
     'Minecraft: torches / stairs / motion to still'),
    ('bistro-still', 'bistro', (360, 590, 720, 830), 200, 240, 3,
     'Bistro: fixed camera / remaining phase flicker'),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    manifest = dict(
        order=MODES, labels=LABELS, shader_changed=False, recaptured=False,
        scope='Screen-fixed manually selected illustrative ROIs; not representative quality statistics or proof of ghosting reduction. No-TAA retains spatial SMAA and paired jitter, not AA Off or unjittered O-1X.',
        playback='GIF at half speed with fixed shared palette/no dithering. MP4 at original 60 FPS. Loop restart is not an algorithm artifact. No interpolation, sharpening, denoising or image alignment.',
        clips=[],
    )
    for name, scene, roi, start, end, gain, title in CLIPS:
        qp = DOC / f'{scene}-quality.json'
        q = json.loads(qp.read_text())
        assert q['validation'] == 'PASS' and q['selection_mismatches'] == 0
        capture = Path(q['capture'])
        source_digests = {m: hashlib.sha256() for m in MODES}
        originals = {}
        for index in range(start, end):
            originals[index] = []
            for mode in MODES:
                path = capture / mode / f'frame_{index:05d}.png'
                source_digests[mode].update(index.to_bytes(8, 'little'))
                source_digests[mode].update(hashlib.sha256(path.read_bytes()).digest())
                with Image.open(path) as im:
                    assert im.mode == 'RGB' and im.size == (1920, 1061)
                    originals[index].append(im.crop(roi))

        def render(index, slow=False, brightness=gain):
            canvas = Image.new('RGB', (1080, 304), '#15181c')
            draw = ImageDraw.Draw(canvas)
            phase = 'MOVING' if 60 <= index < 180 else 'STILL'
            speed = '0.5x' if slow else '1x / 60 FPS'
            draw.text((8, 4), f'{title} | f{index:03d} | {phase} | {speed} | RGB gain {brightness}x', font=small, fill='#eeeeee')
            for column, (tile, label) in enumerate(zip(originals[index], LABELS)):
                draw.text((column * 360 + 8, 33), label, font=font, fill='white')
                tile = ImageEnhance.Brightness(tile).enhance(brightness) if brightness != 1 else tile
                canvas.paste(tile, (column * 360, 64))
            return canvas

        info = dict(
            name=name, scene=scene, roi=list(roi), first_frame=start, last_frame=end - 1,
            title=title, display_rgb_gain=gain, crop_scale=1,
            quality_report_sha256=hashlib.sha256(qp.read_bytes()).hexdigest(),
            capture=str(capture), source_indexed_file_hash_streams={m: h.hexdigest() for m, h in source_digests.items()},
        )
        info['gif'] = gif(OUT / f'{name}.gif', render, start, end)
        info['mp4'] = encode(OUT / f'{name}-60fps.mp4', lambda i: render(start + i), end - start)
        if gain != 1:
            info['original_brightness_mp4'] = encode(OUT / f'{name}-original-brightness-60fps.mp4', lambda i: render(start + i, brightness=1), end - start)
        # Actual RGB before palette/video compression for independent inspection.
        render(start + (end - start) // 2, slow=True).save(OUT / f'{name}-poster.png')
        sheet = Image.new('RGB', (1080, 304 * 3))
        middle = 179 if start <= 179 < end - 2 else start + (end - start) // 2
        for row, index in enumerate(range(middle, middle + 3)):
            sheet.paste(render(index), (0, row * 304))
        sheet.save(OUT / f'{name}-adjacent-frames.png')
        manifest['clips'].append(info)
        print(f'PASS {name}: {end-start} aligned frames; fixed-palette GIF / verified 60 FPS MP4', flush=True)
    (DOC / 'three-way-visuals.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# No-TAA / edge 선택 / 원본 T2X-R 움직임 비교', '',
        '왼쪽부터 **No-TAA(공간 SMAA·지터 유지) / edge 선택 / 원본 T2X-R**이다.',
        'No-TAA는 AA 전체 Off나 지터를 끈 SMAA 1X가 아니다. 기존 검증된 PNG에서 동일 프레임과',
        '동일 화면 좌표를 잘랐다. 별도 렌더링이나 알고리즘 변경은 없다.', '',
        'GIF는 0.5배속, MP4는 원래 60 FPS다. 원본 픽셀 크기이며 보간·선명화·노이즈 제거는 하지 않았다.',
        'Bistro의 어두운 구조는 보기 쉽도록 세 방식에 동일 RGB 밝기 3배를 적용했다.',
        '원래 밝기의 정속 영상도 제공한다. 밝기 조절 자료를 원래 화질 점수로 사용하지 않는다.',
        '고정 공통 256색 팔레트와 dithering Off를 사용해 GIF의 프레임별 색 변화는 줄였지만',
        '색 양자화로 미세한 차이가 사라질 수 있다. 의심스러운 세부는 MP4/원본 PNG로 확인한다.',
        '재생 마지막에서 처음으로 돌아가는 점프는 알고리즘 잔상으로 세지 않는다.', '',
    ]
    descriptions = [
        '의자·테이블의 가는 다리와 바닥 무늬가 이동할 때 연속적으로 유지되는지 비교한다.',
        '가까운 블록의 경계와 새로 드러나는 뒤쪽 벽면에서 번짐·경계 떨림을 확인한다. 실제 고스팅이 존재하거나 줄었다는 결론을 전제한 선택은 아니다.',
        'frame 180부터 카메라가 멈춘다. 횃불, 계단의 대각 경계와 벽면 무늬가 정지 후에도 번갈아 변하는지 확인한다.',
        '카메라가 이미 멈춘 구간이다. 얇은 다리와 바닥의 남은 변동을 보기 위한 장면이며 움직임 잔상 장면은 아니다.',
    ]
    for clip, description in zip(manifest['clips'], descriptions):
        name = clip['name']
        lines += [f'## {clip["title"]}', '', description, '',
                  f'![{name}]({(OUT / (name + ".gif")).as_posix()})', '',
                  f'[정속 영상]({Path(clip["mp4"]["path"]).as_posix()}) · [인접 프레임 PNG]({(OUT / (name + "-adjacent-frames.png")).as_posix()})', '']
        if 'original_brightness_mp4' in clip:
            lines += [f'[원래 밝기 정속 영상]({Path(clip["original_brightness_mp4"]["path"]).as_posix()})', '']
    lines += ['ROI는 관찰을 위한 수동 선택이며 전체 장면의 대표성이나 품질 우열의 독립 검증을 뜻하지 않는다.',
              '정량 결과는 [No-TAA 비교 보고서](no-taa-report.md)를 참고한다.', '']
    (DOC / 'three-way-visuals.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
