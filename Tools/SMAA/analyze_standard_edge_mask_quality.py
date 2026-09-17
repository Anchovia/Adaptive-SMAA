"""Full-timeline native Standard/edge-mask quality comparison, with hash-gated references."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from analyze_wide_camera_reference_quality import (
    collect_frames, load_rgb, luma, luma_ssim, edge_strength, rgb_mae, rgb_psnr,
)

BASE = Path('D:/SMAA-Research-Data/AutoBench')
SCENES = {
    'bistro': ('20260828_072817', '20260827_014143'),
    'minecraft': ('20260828_073715', '20260827_014612'),
}
WINDOWS = {'central_motion': (150, 330), 'transition': (410, 440),
           'late_still': (440, 480)}
CG_WINDOWS = {'central_motion': 'central_motion_00150_00329',
              'transition': 'transition_00410_00439'}
METRICS = ('rgb_mae', 'psnr_db', 'luma_ssim', 'edge_reference_ratio',
           'temporal_delta_residual', 'luma_delta1', 'luma_delta2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(receipt, scene):
    records = [r for r in receipt if r['scene'] == scene]
    assert len(records) == 2 and len({r['mode'] for r in records}) == 2
    assert len({r['executable_sha256'] for r in records}) == 1
    roots = {r['mode']: Path(r['report']).parent for r in records}
    paths = {}
    for mode, key in [('O-T2X-R', 'standard'), ('ABL-Standard-EdgeMask-R', 'masked')]:
        report = Path(next(r['report'] for r in records if r['mode'] == mode))
        body = report.read_text(encoding='utf-8-sig')
        for text in (f'Scene:           {scene}', 'capture [0, 479]',
                     'flythrough-wide-yaw-360', '60 frames at the first captured pose'):
            assert text in body, (report, text)
        paths[key], size = collect_frames(roots[mode]/mode.replace('-', '_'), 480, 0)
        assert size == (1920, 1017)
    control, reference = [BASE/p for p in SCENES[scene]]
    old, _ = collect_frames(control/'O_T2X_R', 480, 0)
    mismatches = sum(sha(a) != sha(b) for a, b in zip(paths['standard'], old))
    assert mismatches == 0, (scene, 'baseline/reference bridge failed', mismatches)
    paths['o1x'], _ = collect_frames(control/'O_1X', 480, 0)
    paths['reference'], _ = collect_frames(reference/'SS_Reference', 480, 0)
    body = next(reference.glob('*_results.csv')).read_text(encoding='utf-8-sig')
    assert '2x linear resolution, 3x3 within-frame subpixel grid, 8x MSAA' in body
    return paths, {'standard_hash_bridge_frames': 480, 'mismatches': mismatches,
                   'archived_control_root': str(control), 'reference_root': str(reference),
                   'capture_records': records}


def media(scene, paths, output):
    output.mkdir(parents=True, exist_ok=True)
    labels = [('reference', 'SS spatial reference'), ('standard', 'Standard T2X-R'),
              ('masked', 'Standard EdgeMask-R')]
    for frame in (240, 419, 420, 479):
        sheet = Image.new('RGB', (1920, 742), '#14171c')
        draw = ImageDraw.Draw(sheet)
        ref = load_rgb(paths['reference'][frame])
        for col, (key, label) in enumerate(labels):
            im = load_rgb(paths[key][frame])
            sheet.paste(Image.fromarray(im).resize((640,339)), (640*col, 28))
            diff = np.clip(np.abs(im.astype(np.int16)-ref)*8,0,255).astype(np.uint8)
            sheet.paste(Image.fromarray(diff).resize((640,339)), (640*col,395))
            draw.text((640*col+10,8), f'{scene} frame {frame} | {label}', fill='white')
            draw.text((640*col+10,375), 'Absolute RGB reference difference x8', fill='white')
        sheet.save(output/f'frame_{frame:03d}_comparison.png')
    # Fixed screen-space ROI, chosen before looking at the new metrics.
    crop = (800, 500, 1280, 860) if scene == 'bistro' else (720, 330, 1200, 690)
    for window, (start, count) in {'motion': (240,30), 'transition': (410,30), 'late_still': (450,20)}.items():
        frames = []
        for i in range(start, start+count):
            canvas = Image.new('RGB', (1440,388), '#14171c')
            d = ImageDraw.Draw(canvas)
            for col, (key, label) in enumerate(labels):
                im = Image.open(paths[key][i]).convert('RGB').crop(crop)
                canvas.paste(im, (480*col,28))
                d.text((480*col+8,8), f'{label} | frame {i} | 3x slower', fill='white')
            frames.append(canvas)
        target=output/f'{window}_crop_3x_slow.gif'
        frames[0].save(target, save_all=True, append_images=frames[1:], duration=50, loop=0, disposal=2)
        with Image.open(target) as gif:
            assert gif.n_frames == count
    return {'roi_xyxy': crop, 'playback': '20 FPS, 3x slower than recorded 60 Hz; GIF only for viewing'}


def analyze(scene, paths, provenance, output):
    rows = []
    previous = {}
    previous2 = {}
    hashes = {w: {k: hashlib.sha256() for k in paths} for w in CG_WINDOWS}
    for frame in range(480):
        images = {k: load_rgb(v[frame]) for k, v in paths.items()}
        ref = images['reference']
        refedge = edge_strength(ref) if frame % 4 == 0 else None
        for w in CG_WINDOWS:
            if WINDOWS[w][0] <= frame < WINDOWS[w][1]:
                for key, im in images.items():
                    hashes[w][key].update(frame.to_bytes(8,'little'))
                    hashes[w][key].update(im.tobytes())
        for key in ('standard','masked','o1x'):
            im = images[key]
            lum = luma(im)
            row={'scene':scene,'frame':frame,'mode':key, 'rgb_mae':rgb_mae(im,ref),
                 'psnr_db':rgb_psnr(im,ref),
                 'luma_ssim':luma_ssim(im,ref) if frame % 8 == 0 else None,
                 'edge_reference_ratio':edge_strength(im)/refedge if refedge else None,
                 'temporal_delta_residual':None,'luma_delta1':None,'luma_delta2':None}
            if previous:
                dt=im.astype(np.int16)-previous[key]
                dr=ref.astype(np.int16)-previous['reference']
                row['temporal_delta_residual']=float(np.abs(dt-dr).mean())
                row['luma_delta1']=float(np.abs(lum-luma(previous[key])).mean())
            if previous2:
                row['luma_delta2']=float(np.abs(lum-2*luma(previous[key])+luma(previous2[key])).mean())
            rows.append(row)
        previous2, previous = previous, images
        if frame % 120 == 119:
            print(f'{scene}: {frame+1}/480 frames analyzed',flush=True)
    windows = {}
    for w,(start,end) in WINDOWS.items():
        modes={}
        for mode in ('standard','masked','o1x'):
            selected=[r for r in rows if r['mode']==mode and start<=r['frame']<end]
            modes[mode]={m:float(np.mean([r[m] for r in selected if r[m] is not None])) for m in METRICS}
        windows[w]={'range_half_open':[start,end],'modes':modes,
                    'masked_minus_standard_percent':{m:(modes['masked'][m]/modes['standard'][m]-1)*100
                        if abs(modes['standard'][m])>1e-12 else None for m in METRICS}}
    digest_values={w:{k:h.hexdigest() for k,h in kv.items()} for w,kv in hashes.items()}
    # Reuse official Standard scores only after exact decoded-pixel hash verification.
    cached={}
    for w,folder in CG_WINDOWS.items():
        path=BASE/'20260828_FinalIntegratedEightCase/CGVQM'/scene.title()/folder/'O_T2X_R/CGVQM-Results.json'
        d=json.loads(path.read_text())
        assert d['test_sequence']['pixel_sha256']==digest_values[w]['standard']
        assert d['reference_sequence']['pixel_sha256']==digest_values[w]['reference']
        assert d['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
        assert d['runtime']['device']=='cuda' and d['configuration']['models']==['2']
        assert d['test_round_trip']['mismatched_values']==d['reference_round_trip']['mismatched_values']==0
        cached[w]={'source':str(path),'json_sha256':sha(path),
                   'score':d['results']['CGVQM-2']['score_higher_is_better']}
    return rows, {'provenance':provenance,'windows':windows,'pixel_hashes':digest_values,
                  'standard_cgvqm_reused':cached,'media':media(scene,paths,output/scene)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,default=Path('tmp/standard-edge-mask-quality-runs.json'))
    p.add_argument('--scene',choices=tuple(SCENES),required=True)
    p.add_argument('--output',type=Path,default=BASE/'20260917_StandardEdgeMaskQuality')
    args=p.parse_args()
    records=json.loads(args.receipt.read_text(encoding='utf-8-sig'))
    paths,provenance=inputs(records,args.scene)
    print(f'{args.scene}: baseline hash bridge PASS 480/480',flush=True)
    args.output.mkdir(parents=True,exist_ok=True)
    rows,summary=analyze(args.scene,paths,provenance,args.output)
    with (args.output/f'{args.scene}_per_frame.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    (args.output/f'{args.scene}_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'PASS: {args.scene} full quality analysis',flush=True)


if __name__=='__main__':
    main()
