"""Inspect stored, same-draw GPU witnesses without changing case 13 or rendering.

Output images are evidence visualizations. RGB panels are original PNG pixels,
nearest enlarged; mask/weight/delta panels are explicitly diagnostic. Fixed screen
rectangles are not geometry tracking, temporal ground truth, or missed-edge recall.
"""
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from edge_quality_inputs import dds, edges, ph, rgb, sha

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'Docs/Minecraft-Grass-Edge-Coverage-Audit'
EVIDENCE = ROOT / 'Docs/Edge-History-Catmull-Rom-Reconstruction/minecraft-capture.json'
MODE = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB'
BASE = 'O-T2X-R'
ROI = (1420, 590, 1580, 718)
SCALE = 3
# Manually located subregions in f130, not edge masks or tracked objects.
PATCHES = {
    'whole_leaves_crop': ROI,
    'A_grass_top': (1424, 655, 1468, 663),
    'B_grass_front': (1424, 663, 1468, 675),
    'C_leaf_detail': (1482, 596, 1570, 638),
    'D_grass_top_right': (1515, 684, 1556, 697),
}
FONT = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 15)
SMALL = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 12)


def weight(path):
    buf = Path(path).read_bytes()
    h, w = struct.unpack_from('<2I', buf, 12)
    off = 148 if buf[84:88] == b'DX10' else 128
    return np.frombuffer(buf[off:], np.float32).reshape(h, w)


def cut(a, box=None):
    if box is None: box=ROI
    x0, y0, x1, y1 = box
    return a[y0:y1, x0:x1]


def tile(a, scale=3):
    return Image.fromarray(a).resize((a.shape[1]*scale, a.shape[0]*scale), Image.Resampling.NEAREST)


def panels(items, f, columns=3):
    h, w = items[0][2].shape[:2]
    w, h = w*SCALE, h*SCALE
    rows = (len(items)+columns-1)//columns
    sheet = Image.new('RGB', (columns*(w+10)+10, rows*(h+64)+10), '#12151a')
    draw = ImageDraw.Draw(sheet)
    for i, (title, subtitle, arr) in enumerate(items):
        x, y = 10+(i % columns)*(w+10), 10+(i//columns)*(h+64)
        draw.text((x, y), title, fill='white', font=FONT)
        draw.text((x, y+21), f'f{f} | {subtitle}', fill='#cbd3de', font=SMALL)
        sheet.paste(tile(arr,SCALE), (x, y+50))
    return sheet


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    evidence = json.loads(EVIDENCE.read_text(encoding='utf-8-sig'))
    assert evidence['validation'] == 'PASS'
    capture = Path(evidence['capture_root']).resolve()
    available = sorted(int(p.name[6:11]) for p in (capture/MODE).glob('frame_*-weight.dds'))
    rows, witnesses, moving, transition = [], [], [], []
    for f in available:
        prefix = capture/MODE/f'frame_{f:05d}'
        output = rgb(str(prefix)+'.png')
        assert ph(output) == evidence['output_hashes'][MODE][f]
        current = dds(str(prefix)+'-current.dds')[:,:,:3]
        edge = np.any(edges(str(prefix)+'-edge.rg8') > 0, axis=2)
        coverage = dds(str(prefix)+'-coverage.dds') > 0
        weights = weight(str(prefix)+'-weight.dds')
        delta = np.abs(output.astype(np.int16)-current.astype(np.int16))
        changed = np.any(delta > 0, axis=2)
        assert np.all(coverage[edge])
        assert not changed[~coverage].any()
        assert (weights[~coverage] == 0).all()
        assert np.isfinite(weights).all() and (weights >= 0).all() and (weights <= .5).all()
        for name, box in PATCHES.items():
            s, e, w, d, c = [cut(a, box) for a in [coverage, edge, weights, delta, changed]]
            row = dict(frame=f, patch=name, pixels=s.size,
                       current_edge_percent=float(100*e.mean()), selected_percent=float(100*s.mean()),
                       previous_only_percent=float(100*(s & ~e).mean()),
                       mean_selected_weight=float(w[s].mean()) if s.any() else None,
                       zero_weight_selected=int(((w == 0) & s).sum()),
                       selected_changed_percent=float(100*c[s].mean()) if s.any() else None,
                       selected_current_output_rgb_mae=float(d[s].mean()) if s.any() else None,
                       nonselected_changed_pixels=int(c[~s].sum()))
            rows.append(row)
        witnesses.append(dict(frame=f, files={suffix:sha(str(prefix)+suffix) for suffix in
            ['.png','-current.dds','-edge.rg8','-coverage.dds','-weight.dds']}))
        native = rgb(capture/BASE/f'frame_{f:05d}.png')
        assert ph(native) == evidence['output_hashes'][BASE][f]
        color = cut(output).copy()
        selected = cut(coverage)
        overlay = color.copy()
        overlay[selected] = (overlay[selected].astype(np.float32)*.45 + np.array([0,255,210])*.55).astype(np.uint8)
        mask = np.repeat((selected.astype(np.uint8)*255)[:,:,None], 3, axis=2)
        smallitems = [
            ('4 Original T2X-R', 'RGB unchanged; Pattern On', cut(native)),
            ('13 Catmull-Rom', 'RGB unchanged; Pattern Off', color),
            ('13 selected pixels', 'WHITE = actual GPU selection', mask),
        ]
        if 126 <= f <= 138:
            moving.append(panels(smallitems, f))
        if 172 <= f <= 189:
            transition.append(panels(smallitems, f))
        if f in [126,127,128,129,130,131,178,179,180,181,182,183,190,191,192,193,194,195]:
            panels(smallitems, f).save(out/f'grass-compare-f{f:03d}.png')
        if f == 130:
            wimg = np.repeat(np.rint(cut(weights)*510).clip(0,255).astype(np.uint8)[:,:,None],3,axis=2)
            dimg = np.repeat((cut(delta).max(axis=2)*8).clip(0,255).astype(np.uint8)[:,:,None],3,axis=2)
            edgeimg = np.repeat((cut(edge).astype(np.uint8)*255)[:,:,None],3,axis=2)
            panels([
                ('13 actual output', f'RGB unchanged; nearest {SCALE}x',color),
                ('13 current raw edges', 'WHITE = first-pass RG > 0',edgeimg),
                ('13 temporal selection', 'WHITE = GPU coverage witness',mask),
                ('13 selection overlay', 'CYAN = selected; diagnostic',overlay),
                ('13 actual history weight', 'BLACK = 0; WHITE = 0.5',wimg),
                ('13 change from current', 'Max RGB difference x8; diagnostic',dimg),
            ],f).save(out/'grass-diagnostics-f130.png')
            annotation=tile(color,4); draw=ImageDraw.Draw(annotation)
            for name,box in PATCHES.items():
                if name.startswith('whole_') or name in ['U_seam_upper','D_seam_lower']: continue
                a,b,c,d=box
                rect=((a-ROI[0])*4,(b-ROI[1])*4,(c-ROI[0])*4,(d-ROI[1])*4)
                draw.rectangle(rect,outline='#ffcf42',width=2)
                draw.text((rect[0]+2,rect[1]-17),name[:1],font=FONT,fill='#ffcf42')
            annotation.save(out/'grass-patch-locations-f130.png')
            context=Image.fromarray(output); draw=ImageDraw.Draw(context)
            draw.rectangle(ROI,outline='#ffcf42',width=3)
            draw.text((ROI[0],ROI[1]-24),'Audited crop',fill='#ffcf42',font=FONT)
            context.save(out/'grass-full-context-f130.png')
    assert len(moving)==13 and len(transition)==18
    inspected_sheets=[]
    for phase,start in [('move',126),('transition',178),('still',190)]:
        for pair in range(3):
            fs=[start+pair*2,start+pair*2+1]
            ims=[]
            for f in fs:
                with Image.open(out/f'grass-compare-f{f:03d}.png') as im:
                    ims.append(im.convert('RGB'))
            sheet=Image.new('RGB',(ims[0].width,2*ims[0].height),'#12151a')
            for i,im in enumerate(ims): sheet.paste(im,(0,i*im.height))
            path=out/f'grass-{phase}-pair{pair}.png';sheet.save(path)
            inspected_sheets.append(dict(path=str(path),frames=fs,sha256=sha(path)))
    for name, images in [('moving',moving),('transition',transition)]:
        # Frames remain consecutive. 80 ms is 12.5 FPS, not original 60 FPS.
        atlas=Image.new('RGB',(500,220*len(images)))
        for i, im in enumerate(images): atlas.paste(im.resize((500,220)),(0,i*220))
        palette=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        indexed=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in images]
        gif=out/f'grass-{name}-mask.gif'
        indexed[0].save(gif,save_all=True,append_images=indexed[1:],duration=80,loop=0,disposal=2,optimize=False)
        with Image.open(gif) as im:
            assert im.n_frames==len(images)
            for i,expected in enumerate(indexed):
                im.seek(i)
                assert im.info['duration']==80
                assert im.convert('RGB').tobytes()==expected.convert('RGB').tobytes()
    with (DOC/'per-frame.csv').open('w',newline='',encoding='utf-8') as fp:
        wr=csv.DictWriter(fp,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
    result=dict(validation='PASS',branch='experiment/minecraft-grass-edge-coverage-audit',
        code_parent='ebe68da448c79fb468dc55684d744a5eaf854788',
        classification='offline diagnosis of existing case13 GPU witnesses; no new renderer or timing result',
        source=str(EVIDENCE),source_sha256=sha(EVIDENCE),capture_root=str(capture),mode=MODE,control=BASE,
        settings=dict(spatial='Original Ultra',pattern_selected='Off',pattern_control='On',
                      reprojection='camera/depth; no object velocity',history='resolved RGB; spatial alpha',
                      selected_weight='native adaptive 0..0.5'),
        roi=ROI,patches=PATCHES,trace_frames=available,source_witnesses=witnesses,
        f130=[r for r in rows if r['frame']==130],
        invariants=dict(current_raw_edge_selection_mismatch=0,nonselected_output_mismatch=0,
                        nonselected_weight_mismatch=0),
        presentation=dict(output=str(out),rgb_scale=SCALE,filter='nearest',rgb_tone_adjustment=False,
                          gif_fps=12.5,source_fps=60,moving_frames=[126,138],transition_frames=[172,189],
                          gif_decoded_rgb_verified=True),
        inspection_sheets=inspected_sheets,
        media_sha256={p.name:sha(p) for p in out.glob('*') if p.suffix in ['.png','.gif']},
        limitations=['Rectangles are fixed-screen regions, not tracked geometry or edge ground truth',
                     'Coverage is actual GPU selection; nonzero weight does not imply alias-free history',
                     'Current/output RGB delta is an effect witness, not a quality score',
                     'Case4 versus13 differs in sample pattern and history/filter, not coverage alone',
                     'Raw adjacent-frame changes include camera movement; no isolated shimmer/ghosting score'])
    (DOC/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(validation='PASS',trace_frames=len(available),f130=result['f130'],output=str(out)),ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--focus-user-seam',action='store_true')
    args=p.parse_args()
    if args.focus_user_seam:
        DOC=DOC/'User-Specified-Seam'
        ROI=(1450,665,1552,719)
        SCALE=4
        PATCHES={
            'whole_user_crop':ROI,
            'S_seam_strip':(1494,700,1525,705),
            'U_seam_upper':(1494,699,1525,700),
            'D_seam_lower':(1494,705,1525,706),
        }
    main(args.output.resolve())
