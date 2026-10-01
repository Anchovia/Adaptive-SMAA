"""60 Hz presentation crops; lossless PNG sheets remain the inspection evidence."""
import json
from fractions import Fraction
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).resolve().parents[2]
D = R / 'Docs/Edge-Persistence-Spatial-Cost'
out = R / 'tmp/spatial-cost-inspection'
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
modes = [('E-PreviousRawEdge-FirstStencil', 'E: existing case 8'),
         ('F-EagerPreviousFetch', 'F: eager lookup'),
         ('G-DepthMask-CurrentWeights', 'G: current weights')]
records = []
for scene, roi, scale in [('bistro', (1230, 582, 1358, 670), 2),
                          ('minecraft', (956, 524, 1020, 620), 3)]:
    source = Path(json.loads((D / f'{scene}-capture.json').read_text())['capture_root'])
    w, h = (roi[2]-roi[0])*scale, (roi[3]-roi[1])*scale
    dest = out / f'{scene}-same-output-60fps.mp4'
    with av.open(str(dest), 'w') as container:
        stream = container.add_stream('libx264', rate=60)
        stream.width, stream.height = 3*(w+8), h+56
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf': '15', 'preset': 'fast'}
        for n, frame in enumerate(range(120, 210)):
            sheet = Image.new('RGB', (stream.width, stream.height), (20, 22, 25))
            draw = ImageDraw.Draw(sheet)
            for col, (mode, label) in enumerate(modes):
                x = col*(w+8)
                draw.text((x+4, 2), label, fill='white', font=font)
                draw.text((x+4, 25), f'frame {frame} / 60 Hz', fill='white', font=font)
                with Image.open(source/mode/f'frame_{frame:05d}.png') as image:
                    sheet.paste(image.crop(roi).resize((w, h), Image.Resampling.NEAREST), (x+4, 50))
            vf = av.VideoFrame.from_ndarray(np.asarray(sheet), format='rgb24')
            vf.pts, vf.time_base = n, Fraction(1, 60)
            for packet in stream.encode(vf):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    with av.open(str(dest)) as container:
        vs = container.streams.video[0]
        assert vs.average_rate == 60
        decoded = list(container.decode(vs))
        assert len(decoded) == 90
        times = [f.pts*f.time_base for f in decoded]
        assert all(b-a == Fraction(1, 60) for a, b in zip(times, times[1:]))
    records.append(dict(scene=scene, path=str(dest), frames=[120, 209], fps=60,
                        roi=roi, scale=scale, presentation_only=True,
                        encoding='H264 yuv420p CRF15; not lossless quality input',
                        playback_watched=False, decode_and_pts_verified=True))
(D/'playback-manifest.json').write_text(json.dumps(records, indent=2)+'\n')
print('PASS decoded frame count and exact 60 Hz timestamps', out)
