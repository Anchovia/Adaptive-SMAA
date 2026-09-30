"""Verify actual GPU first-pass RG for cases 2/4/5/6 and create aligned GIFs."""
import argparse
import csv
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT/'Docs/Native-FirstPass-Edge-Visuals'
BASE = '15fb796bac3be602ba88727a4593f9fcc033088d'
MEDIA_REF = '2b3ca2f'
IDS = ('bistro-chairs-moving', 'minecraft-thin-edges-moving', 'bistro-window-stop')
CASES = (2, 4, 5, 6)
LABELS = {2:'② SMAA 1X · 지터 Off', 4:'④ SMAA T2X-R · 지터 On',
          5:'⑤ Edge temporal-only · 지터 Off', 6:'⑥ SMAA + edge temporal · 지터 Off'}
FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 20)
BOLD = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 23)
SMALL = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 17)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blob(ref, path):
    return subprocess.check_output(['git', 'show', ref+':'+path], cwd=ROOT)


def git_json(ref, path):
    return json.loads(blob(ref, path))


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def rgb_hash(path):
    with Image.open(path) as im:
        assert im.mode == 'RGB' and im.size == (1920, 1061), path
        return hashlib.sha256(im.tobytes()).hexdigest()


def edge(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'EDG1' and struct.unpack_from('<2I', b, 4) == (1920, 1061)
    a = np.frombuffer(b[12:], np.uint8).reshape(1061, 1920, 2)
    assert np.isin(a, [0, 255]).all(), path
    return np.any(a > 0, axis=2), hashlib.sha256(b).hexdigest()


def coverage(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'DDS ' and struct.unpack_from('<2I', b, 12) == (1061, 1920)
    offset = 148 if b[84:88] == b'DX10' else 128
    if offset == 148:
        assert struct.unpack_from('<I', b, 128)[0] == 61
    else:
        assert struct.unpack_from('<I', b, 88)[0] == 8
    a = np.frombuffer(b[offset:], np.uint8).reshape(1061, 1920)
    assert np.isin(a, [0, 255]).all()
    return a > 0


def render(masks, clip, frame):
    out = Image.new('L', (1152, 958), 0)
    d = ImageDraw.Draw(out)
    d.text((12, 6), clip['title']+' · 실제 1st-pass edge', font=BOLD, fill=255)
    phase = '정지' if frame >= 180 else '이동'
    d.text((12, 44), f"흰색 = RG>0 · 2배 확대 · {clip['fps']/60:g}배속 · f{frame:03d} · {phase}", font=FONT, fill=220)
    for i, case in enumerate(CASES):
        x, y = (i%2)*576, 82+(i//2)*422
        d.text((x+12, y+6), LABELS[case], font=FONT, fill=255)
        crop = masks[case].crop(clip['roi']).resize((576, 384), Image.Resampling.NEAREST)
        out.paste(crop, (x, y+38))
    d.text((12, 932), 'GPU edge 텍스처 그대로 · ④의 temporal은 전체 화면 적용', font=SMALL, fill=220)
    return out


def gif(path, frames, fps):
    palette = [v for i in range(256) for v in (i, i, i)]
    indexed = []
    for im in frames:
        p = Image.frombytes('P', im.size, im.tobytes())
        p.putpalette(palette)
        indexed.append(p)
    durations = [10*(round((i+1)*100/fps)-round(i*100/fps)) for i in range(len(frames))]
    indexed[0].save(path, save_all=True, append_images=indexed[1:], duration=durations,
                    loop=0, disposal=2, optimize=False)
    with Image.open(path) as im:
        assert im.n_frames == len(frames)
        for i, f in enumerate(frames):
            im.seek(i)
            assert im.info['duration'] == durations[i]
            assert im.convert('L').tobytes() == f.tobytes()
    return dict(path=str(path.resolve()), sha256=sha(path), frames=len(frames),
                duration_ms=sum(durations), grayscale_decoded_exact=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene', choices=('bistro', 'minecraft'), required=True)
    p.add_argument('--output', type=Path, default=ROOT/'Projects/CMAA2/Captures/native-first-pass-edge-20260930')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = json.loads((DOC/f'{args.scene}-run.json').read_text(encoding='utf-8-sig'))
    assert receipt['executable_sha256'].lower() == sha(ROOT/'Projects/CMAA2/CMAA2.exe')
    report = Path(receipt['report'])
    assert sha(report) == receipt['report_sha256'].lower()
    text = report.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows = [[v.strip() for v in r if v.strip()] for r in csv.reader(text.splitlines()) if r]
    capture = Path(next(r[1] for r in rows if r[0] == 'capture_root'))
    checks = [r for r in rows if r[0] == 'mode_check']
    assert len(checks) == 720 and all(r[-1] == 'PASS' for r in checks)
    summary = git_json(MEDIA_REF, 'Docs/Six-Case-Stencil-Lifecycle/summary.json')
    media = git_json(MEDIA_REF, 'Docs/Six-Case-Stencil-Lifecycle/media.json')
    branches = {b['case']:b for b in summary['branches']}
    configs = {c:git_json(MEDIA_REF, f'Docs/Six-Case-Stencil-Lifecycle/case{c}/case.json') for c in CASES}
    expected = {c:git_json(branches[c]['commit'], f'Docs/Stencil-Lifecycle-Refresh/{args.scene}-rgb-hashes.json')[configs[c]['target']] for c in CASES}
    verified_native_rgb = 0
    for mode, case in (('O-1X', 2), ('O-T2X-R', 4), ('O-1X-Repeat', 2)):
        for f in range(240):
            assert rgb_hash(capture/mode/f'frame_{f:05d}.png') == expected[case][f], (mode, f, 'RGB changed')
            verified_native_rgb += 1
    print(args.scene, '720 native final RGB frames unchanged', flush=True)
    historic = {c:Path(git_json(MEDIA_REF, f'Docs/Six-Case-Stencil-Lifecycle/case{c}/{args.scene}-prior.json')['target_capture']) for c in (5, 6)}
    verified_prior = next(s for s in git_json(MEDIA_REF, 'Docs/Six-Case-Stencil-Lifecycle/edge-media.json')['scenes'] if s['scene'] == args.scene)
    prior_hashes = {f['frame']:f['rg8_sha256'] for f in verified_prior['frames']}
    frames, imgs = [], {}
    for f in range(100, 220):
        masks, hashes = {}, {}
        for c in CASES:
            folder = capture/configs[c]['target'] if c in (2, 4) else historic[c]
            masks[c], hashes[c] = edge(folder/f'frame_{f:05d}-edge.rg8')
            if c in (5, 6):
                assert hashes[c] == prior_hashes[f]
                assert rgb_hash(folder/f'frame_{f:05d}.png') == expected[c][f]
                assert np.array_equal(masks[c], coverage(folder/f'frame_{f:05d}-coverage.dds'))
        repeated, repeated_hash = edge(capture/'O-1X-Repeat'/f'frame_{f:05d}-edge.rg8')
        assert repeated_hash == hashes[2] and np.array_equal(repeated, masks[2])
        assert hashes[5] == hashes[6] and np.array_equal(masks[5], masks[6])
        differences = {f'{a}_{b}':int(np.count_nonzero(masks[a] != masks[b]))
                       for a, b in ((2, 5), (2, 6), (5, 6), (2, 4))}
        frames.append(dict(frame=f, rg8_sha256={str(c):hashes[c] for c in CASES},
            edge_count={str(c):int(masks[c].sum()) for c in CASES}, xor_pixel_count=differences,
            rg_exact_2_5=hashes[2] == hashes[5], rg_exact_2_6=hashes[2] == hashes[6]))
        imgs[f] = {c:Image.fromarray(masks[c]).convert('L') for c in CASES}
        if f%30 == 9:
            print(args.scene, f, 'raw edges and coverage verified', flush=True)
    clips = []
    for entry in media['clips']:
        clip = entry['clip']
        if clip['scene'] != args.scene or clip['id'] not in IDS:
            continue
        assert sha(entry['comparison_gif']['path']) == entry['comparison_gif']['sha256']
        rendered = [render(imgs[f], clip, f) for f in range(clip['start'], clip['end'])]
        result = gif(args.output/(clip['id']+'-actual-edges.gif'), rendered, clip['fps'])
        assert result['frames'] == entry['comparison_gif']['frames']
        assert result['duration_ms'] == entry['comparison_gif']['duration_ms']
        rendered[len(rendered)//2].save(args.output/(clip['id']+'-preview.png'))
        clips.append(dict(clip=clip, actual_edges=result, color_six_way=entry['comparison_gif']))
    source_audit = {}
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, 'Projects/CMAA2/SMAA'], cwd=ROOT, text=True).splitlines()
    for name in names:
        if name.endswith(('.hlsl', '.hlsli')) or name.endswith('/SMAA.cpp'):
            assert (ROOT/name).read_bytes().replace(b'\r\n', b'\n') == blob(BASE, name).replace(b'\r\n', b'\n'), name
            source_audit[name] = sha(ROOT/name)
    out = dict(validation='PASS', scene=args.scene, baseline=BASE, historical_media_commit=MEDIA_REF,
        native_capture=str(capture), native_rgb_bridge_frames=verified_native_rgb,
        historical_rgb_bridge_frames=240, historical_coverage_verified_frames=240,
        repeated_native_edge_frames=120, source_algorithm_files_unchanged=source_audit,
        rg_exact_2_5_frames=sum(f['rg_exact_2_5'] for f in frames),
        rg_exact_2_6_frames=sum(f['rg_exact_2_6'] for f in frames),
        mean_2_4_xor_pixels=float(np.mean([f['xor_pixel_count']['2_4'] for f in frames])),
        late_still_unique_edge_hashes={str(c):len({f['rg8_sha256'][str(c)] for f in frames if f['frame'] >= 190}) for c in CASES},
        frames=frames, clips=clips,
        interpretation='Actual first-pass GPU RG only. Display is any(RG>0), no image edge filter, dilation, '
            'or threshold change. Cases 2/5/6 pattern Off; case 4 pattern On. Case 4 runs temporal full screen; '
            'its first-pass spatial edge mask is NOT its temporal coverage. No new timing or quality score.')
    dump(DOC/f'{args.scene}-analysis.json', out)
    print(args.scene, 'PASS:', out['rg_exact_2_5_frames'], '/120 raw RG 2=5;',
          out['rg_exact_2_6_frames'], '/120 raw RG 2=6;', 'late-still unique:', out['late_still_unique_edge_hashes'], flush=True)


if __name__ == '__main__':
    main()
