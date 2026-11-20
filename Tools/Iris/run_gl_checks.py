"""Check the Iris pack with the installed OpenGL driver through iris_gl_harness.exe (no Minecraft).

1. Compile and link all 70 option combinations (AA_MODE x DEBUG_VIEW x TIERS_AT_MAX).
2. Run frames cropped from CMAA2 demo screenshots (no AA) with a synthetic flat depth and camera:
   static        modes 1..6: selected modes equal SMAA 1X of the same family in every frame
   pan x / pan y integer camera moves (2 px per frame): with exact reprojection the history is the
                 previous output at the same content, so selected modes equal SMAA 1X away from borders;
                 a wrong velocity sign or history buffer shows up as a difference
   pan 1.5 px    non-integer move: reports the difference from SMAA 1X (history is filtered)
   hand          pan 1.5 px with a hand rectangle (depthtex1 < depthtex2): no history inside it
   tiers         TIERS_AT_MAX makes Adaptive modes equal to Original modes
The frame's top row is the top of the screen (uploaded bottom row first, as OpenGL stores it).

usage: python run_gl_checks.py <pack build dir> <harness exe> <work dir> <json out> <scene=png> [...]
"""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iris_expand import PROGRAMS, expand, variants  # noqa: E402

W, H, NEAR, FAR, FOV, Z = 1600, 1000, 0.05, 1024.0, 70.0, 10.0


def write_program_dir(shaders, options, target):
    target.mkdir(parents=True, exist_ok=True)
    for program in PROGRAMS:
        for ext in ('vsh', 'fsh'):
            (target / f'{program}.{ext}').write_text(expand(shaders, shaders / f'{program}.{ext}', options), encoding='ascii', newline='\n')
    for name in ('AreaTex', 'SearchTex'):
        rgba = np.asarray(Image.open(shaders / 'textures' / f'{name}.png').convert('RGBA'))
        (target / f'{name}.rgba').write_bytes(rgba.tobytes())


def run(harness, program_dir, scenario_text, out):
    out.mkdir(parents=True, exist_ok=True)
    scenario = out / 'scenario.txt'
    scenario.write_text(scenario_text, encoding='ascii')
    result = subprocess.run([str(harness), str(program_dir), str(scenario), str(out)], capture_output=True, text=True, timeout=600)
    log = (out / 'gl_log.txt').read_text(errors='replace') if (out / 'gl_log.txt').exists() else ''
    return result.returncode, log + result.stderr


def perspective():
    f = 1.0 / math.tan(math.radians(FOV) / 2)
    p = np.zeros((4, 4))
    p[0, 0], p[1, 1] = f / (W / H), f
    p[2, 2], p[2, 3], p[3, 2] = (FAR + NEAR) / (NEAR - FAR), 2 * FAR * NEAR / (NEAR - FAR), -1.0
    return p


def mat_line(name, m):
    return f'mat {name} ' + ' '.join(f'{v:.9g}' for v in m.T.flatten()) + '\n'  # column-major


def camera_uniforms(position, previous, first):
    p = perspective()
    lines = mat_line('gbufferProjectionInverse', np.linalg.inv(p)) + mat_line('gbufferModelViewInverse', np.eye(4))
    lines += mat_line('gbufferPreviousModelView', np.zeros((4, 4)) if first else np.eye(4))
    lines += mat_line('gbufferPreviousProjection', np.zeros((4, 4)) if first else p)
    for name, value in (('cameraPosition', position), ('previousCameraPosition', previous)):
        i = np.floor(value).astype(int)
        lines += f'ivec3 {name}Int {i[0]} {i[1]} {i[2]}\n' + 'vec3 {}Fract {:.9g} {:.9g} {:.9g}\n'.format(name, *(np.asarray(value) - i))
    return lines


def plane_depth():
    clip = perspective() @ np.array([0, 0, -Z, 1.0])
    return 0.5 * clip[2] / clip[3] + 0.5


def pixel_step():
    # World units of camera motion that move the plane at distance Z by one pixel.
    p = perspective()
    return (2 * Z / (p[0, 0] * W), 2 * Z / (p[1, 1] * H))


def frames_for(source, shift, count, hand=None, start=(160, 30)):
    """Frames of a camera moving by `shift` = (sx, sy) pixels per frame (screen x right, y up).
    Content moves the opposite way. Returns per-frame (rgba GL-order bytes, depth0, depth1, depth2, cam)."""
    step = pixel_step()
    out = []
    for t in range(count):
        ox = start[0] + t * shift[0]       # the window moves with the camera over the source image
        oy = start[1] - t * shift[1]       # screen up = image row decreasing
        crop = source.crop((int(round(ox)), int(round(oy)), int(round(ox)) + W, int(round(oy)) + H)) if float(ox).is_integer() and float(oy).is_integer() else \
            source.transform((W, H), Image.AFFINE, (1, 0, ox, 0, 1, oy), resample=Image.BILINEAR)
        rgba = np.asarray(crop.convert('RGBA'))[::-1].copy()  # bottom row first
        depth = np.full((H, W), plane_depth(), np.float32)
        depth2 = depth.copy()
        depth1 = depth.copy()
        if hand is not None:
            x0, y0, x1, y1 = hand                              # image coordinates (top-down)
            depth1[H - y1:H - y0, x0:x1] = 0.2                 # GL rows
        cam = np.array([t * shift[0] * step[0], t * shift[1] * step[1], 0.0])
        out.append((rgba, depth1 if hand is not None else depth, depth1, depth2, cam))
    return out


def scenario(frames, work, dump=()):
    text = f'size {W} {H}\nframes {len(frames)}\n'
    for t, (rgba, d0, d1, d2, cam) in enumerate(frames):
        paths = []
        for name, data in (('color', rgba), ('depth0', d0), ('depth1', d1), ('depth2', d2)):
            path = work / f'{name}_{t:03d}.raw'
            path.write_bytes(np.ascontiguousarray(data).tobytes())
            paths.append(str(path))
        previous = frames[t - 1][4] if t > 0 else cam
        text += f'frame {" ".join(paths)} {"dump" if t in dump else "nodump"}\n'
        text += camera_uniforms(cam, previous, t == 0) + f'int frameCounter {t}\nend\n'
    return text


def load_final(out, t):
    return np.frombuffer((out / f'final_{t:03d}.rgba').read_bytes(), np.uint8).reshape(H, W, 4)[::-1, :, :3].astype(int)


def load_buffer(out, n, t):
    return np.frombuffer((out / f'colortex{n}_{t:03d}.f32').read_bytes(), np.float32).reshape(H, W, 4)[::-1]


def compare(a, b, region=None):
    d = np.abs(a - b).max(axis=2)
    if region is not None:
        d = d[region]
    return {'max': int(d.max()), 'pixels_gt0': int((d > 0).sum()), 'pixels_gt8': int((d > 8).sum()), 'pixels': int(d.size)}


def main():
    pack, harness, work, out_json = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    scenes = dict(item.split('=', 1) for item in sys.argv[5:])
    shaders = pack / 'shaders'
    report = {'harness': str(harness), 'size': [W, H], 'compile': {}, 'scenes': {}}

    # 1. Compile and link every option combination with the driver.
    compile_ok = True
    for options in variants():
        key = f"m{options['AA_MODE']}_d{options['DEBUG_VIEW']}_t{int(options['TIERS_AT_MAX'])}"
        pdir = work / 'programs' / key
        write_program_dir(shaders, options, pdir)
        code, log = run(harness, pdir, f'size 64 64\nframes 0\n', work / 'compile' / key)
        ok = code == 0 and 'RESULT OK' in log
        compile_ok &= ok
        report['compile'][key] = {'ok': ok, 'driver_messages': [l for l in log.splitlines() if l.startswith('[') or 'error' in l.lower() or 'warning' in l.lower()]}
    report['compile_all_ok'] = compile_ok
    report['gl'] = [l for l in (work / 'compile' / 'm6_d0_t0' / 'gl_log.txt').read_text().splitlines() if l.startswith('GL_')]
    print('compile', compile_ok)

    def program(mode, tiers=False):
        return work / 'programs' / f'm{mode}_d0_t{int(tiers)}'

    border = np.zeros((H, W), bool)
    border[96:H - 96, 96:W - 96] = True
    for scene, png in scenes.items():
        source = Image.open(png).convert('RGB')
        res = {}
        cases = {'static': ((0, 0), None), 'pan_x2': ((2, 0), None), 'pan_y2': ((0, 2), None), 'pan_x1p5': ((1.5, 0), None),
                 'hand_x1p5': ((1.5, 0), (200, 600, 520, 1000))}
        for case, (shift, hand) in cases.items():
            frames = frames_for(source, shift, 6, hand)
            cdir = work / scene / case
            cdir.mkdir(parents=True, exist_ok=True)
            text = scenario(frames, cdir, dump=(5,))
            plain = text.replace(' dump\n', ' nodump\n')
            outputs = {}
            for mode, tiers in ((1, False), (2, False), (3, False), (4, False), (5, False), (6, False), (2, True), (4, True), (6, True)):
                odir = cdir / f'm{mode}_t{int(tiers)}'
                code, log = run(harness, program(mode, tiers), text if (mode, tiers) == (6, False) else plain, odir)
                if code != 0:
                    raise SystemExit(f'{scene} {case} mode {mode}: harness failed\n{log}')
                outputs[(mode, tiers)] = odir
            row = {'shift_px': list(shift), 'frames': 6}
            for t in range(6):
                f1, f2 = load_final(outputs[(1, False)], t), load_final(outputs[(2, False)], t)
                for mode, base in ((3, f1), (5, f1), (4, f2), (6, f2)):
                    row.setdefault(f'mode{mode}_vs_1x', []).append(compare(load_final(outputs[(mode, False)], t), base, border))
                for mode, base in ((2, 1), (4, 3), (6, 5)):
                    row.setdefault(f'tiers_mode{mode}_vs_mode{base}', []).append(compare(load_final(outputs[(mode, True)], t), load_final(outputs[(base, False)], t)))
            v = load_buffer(outputs[(6, False)], 3, 5)
            step = 1.0 / W, 1.0 / H
            row['velocity_frame5'] = {'expected_uv': [-shift[0] * step[0], -shift[1] * step[1]],
                                      'median_uv': [float(np.median(v[..., 0])), float(np.median(v[..., 1]))],
                                      'max_abs_error_uv': float(max(np.abs(v[..., 0] + shift[0] * step[0]).max() if hand is None else 0, np.abs(v[..., 1] + shift[1] * step[1]).max() if hand is None else 0)),
                                      'usable_ratio': float((v[..., 2] > 0.5).mean())}
            e = load_buffer(outputs[(6, False)], 5, 5)
            row['selected_ratio_frame5'] = float((e[..., 3] > 0.5).mean())
            if hand is not None:
                x0, y0, x1, y1 = hand
                inside = np.zeros((H, W), bool); inside[y0:y1, x0:x1] = True
                row['hand_selected_pixels'] = int(((e[..., 3] > 0.5) & inside).sum())
                row['hand_usable_pixels'] = int(((v[..., 2] > 0.5) & inside).sum())
                row['hand_mode6_vs_1x_inside'] = compare(load_final(outputs[(6, False)], 5), load_final(outputs[(2, False)], 5), inside)
                row['hand_mode6_vs_1x_outside'] = compare(load_final(outputs[(6, False)], 5), load_final(outputs[(2, False)], 5), border & ~inside)
            # Adaptive vs Original SMAA 1X on the first frame, over the pixels SMAA changed.
            src0 = frames[0][0][::-1, :, :3].astype(int)
            f1, f2 = load_final(outputs[(1, False)], 0), load_final(outputs[(2, False)], 0)
            changed = np.any(f1 != src0, axis=2)
            diff = np.abs(f2 - f1).max(axis=2)
            row['adaptive_vs_original_1x_frame0'] = {'smaa_changed_ratio': float(changed.mean()), 'diff_ratio_of_changed': float((diff[changed] > 0).mean()),
                                                     'diff_gt8_ratio_of_changed': float((diff[changed] > 8).mean()), 'max': int(diff.max())}
            for t in (0, 5):
                for key, mode in (('original_1x', (1, False)), ('adaptive_1x', (2, False)), ('final_combo', (6, False))):
                    Image.fromarray(load_final(outputs[mode], t).astype(np.uint8)).save(cdir / f'{key}_f{t}.png')
            Image.fromarray(src0.astype(np.uint8)).save(cdir / 'input_f0.png')
            res[case] = row
            print(scene, case, json.dumps({k: v for k, v in row.items() if not isinstance(v, list)})[:400])
        report['scenes'][scene] = {'source': png, 'source_sha256': hashlib.sha256(Path(png).read_bytes()).hexdigest(), 'cases': res}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
