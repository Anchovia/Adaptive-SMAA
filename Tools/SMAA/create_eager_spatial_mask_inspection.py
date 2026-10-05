"""Lossless eager/spatial-mask inspection sheets; lossy playback is presentation only."""
import json
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

R = Path(__file__).resolve().parents[2]
D = R / 'Docs/Edge-Persistence-Eager-Spatial-Mask'
OUT = R / 'tmp/eager-spatial-mask-inspection'
MODES = [('F-EagerPreviousFetch', 'Case 9 / union weights'),
         ('H-EagerDepth-UnionWeights', 'H / metadata + union weights'),
         ('J-EagerDepth-CurrentWeights', 'J / current-only weights')]
WINDOWS = {'moving': range(130, 136), 'transition': range(178, 184),
           'still': range(190, 196)}
ROIS = {'bistro': (1230, 582, 1358, 670),
        'minecraft': (956, 524, 1020, 620)}


def read(root, mode, frame):
    with Image.open(root / mode / f'frame_{frame:05d}.png') as im:
        assert im.size == (1920, 1061) and im.mode == 'RGB'
        return im.copy()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for scene, roi in ROIS.items():
        cap = json.loads((D / f'{scene}-capture.json').read_text())
        assert cap['validation'] == 'PASS'
        root = Path(cap['capture_root'])
        scale = 3
        w, h = (roi[2]-roi[0])*scale, (roi[3]-roi[1])*scale
        col = max(260, w)
        for phase, frames in WINDOWS.items():
            sheet = Image.new('RGB', (col*3+32, (h+24)*len(frames)+40), '#171a1e')
            draw = ImageDraw.Draw(sheet)
            for c, (mode, label) in enumerate(MODES):
                draw.text((8+c*(col+8), 5), label, fill='white')
                for row, f in enumerate(frames):
                    x, y = 8+c*(col+8), 35+row*(h+24)
                    draw.text((x, y), f'{scene} f{f} / Pattern Off / nearest {scale}x', fill='white')
                    crop = read(root, mode, f).crop(roi).resize((w, h), Image.Resampling.NEAREST)
                    sheet.paste(crop, (x, y+18))
            path = OUT / f'{scene}-{phase}-six-frames.png'
            sheet.save(path)
            records.append(dict(scene=scene, phase=phase, source_root=str(root),
                                frames=list(frames), roi=list(roi), scale=scale,
                                sheet=str(path), viewed=False))
        # Full frame remains full resolution. No resizing or color adjustment.
        full = Image.new('RGB', (5776, 1091), '#171a1e')
        draw = ImageDraw.Draw(full)
        for c, (mode, label) in enumerate(MODES):
            draw.text((c*1928, 5), f'{label} / {scene} f131 / Pattern Off', fill='white')
            full.paste(read(root, mode, 131), (c*1928, 30))
        fullpath = OUT / f'{scene}-full-frame-131.png'
        full.save(fullpath)
        records.append(dict(scene=scene, phase='full-frame', source_root=str(root),
                            frames=[131], sheet=str(fullpath), viewed=False))
        # Same source interval, display only. Native 60 Hz; no repeated/dropped frames.
        video = OUT / f'{scene}-frames-120-203-60fps.mp4'
        width, height = col*3+32, h+40
        height += height % 2
        with av.open(str(video), 'w') as container:
            stream = container.add_stream('libx264', rate=60)
            stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
            stream.options = {'crf': '14', 'preset': 'fast'}
            for i, f in enumerate(range(120, 204)):
                canvas = Image.new('RGB', (width, height), '#171a1e')
                draw = ImageDraw.Draw(canvas)
                for c, (mode, label) in enumerate(MODES):
                    x = 8+c*(col+8)
                    draw.text((x, 3), label, fill='white')
                    draw.text((x, 17), f'f{f} / 60 fps / nearest 3x', fill='white')
                    canvas.paste(read(root, mode, f).crop(roi).resize((w, h), Image.Resampling.NEAREST), (x, 34))
                frame = av.VideoFrame.from_ndarray(np.asarray(canvas), format='rgb24')
                frame.pts, frame.time_base = i, Fraction(1, 60)
                for packet in stream.encode(frame): container.mux(packet)
            for packet in stream.encode(): container.mux(packet)
        with av.open(str(video)) as container:
            assert container.streams.video[0].average_rate == 60
            stamps = [f.pts*f.time_base for f in container.decode(video=0)]
        assert len(stamps) == 84 and all(b-a == Fraction(1, 60) for a, b in zip(stamps, stamps[1:]))
        records.append(dict(scene=scene, phase='playback', path=str(video), frames=[120, 203],
                            fps=60, decoded_frames=84, viewed=False, lossy_display_only=True))
    (OUT / 'manifest.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
    print(OUT)


if __name__ == '__main__': main()
