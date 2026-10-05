"""CPU-only trace of saved case11 inputs, selection, history and actual output.

No renderer, CUDA model, new capture or AA parameter change is made. Bilinear
history panels are ideal CPU reconstructions, not exact exported GPU samples.
"""
import argparse
import csv
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from edge_quality_inputs import dds, edges, encoded, linear, ph, rgb, sha
from analyze_edge_bilinear_history_rgb import weight_dds

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'Docs/Edge-Persistence-Resolved-RGB-Feedback'
MODE = 'ABL-ET2X-R-PreviousRawEdge-ResolvedRGB'
CONTROL = 'ABL-ET2X-R-PreviousRawEdge-BilinearRGB'
ROIS = {'minecraft': (956, 524, 1020, 620),
        'bistro': (1230, 582, 1358, 670)}
WINDOWS = {'moving': list(range(126, 139)),
           'transition': list(range(178, 184)), 'still': list(range(190, 196))}
LUMA = np.array([.2126, .7152, .0722], np.float64)
SPEC = 'https://microsoft.github.io/DirectX-Specs/d3d/archive/D3D11_3_FunctionalSpec.htm'


def sample_history(previous, velocity, box):
    """Mirror CLAMP, point alpha and ideal linear RGB filtering in the ROI."""
    h, w = previous.shape[:2]
    x0, y0, x1, y1 = box
    yy, xx = np.mgrid[y0:y1, x0:x1]
    uv = np.stack(((xx.astype(np.float32) + .5) / np.float32(w),
                   (yy.astype(np.float32) + .5) / np.float32(h)), axis=-1)
    coords = (uv - velocity[y0:y1, x0:x1].astype(np.float32)) * np.array([w, h], np.float32)
    ij = np.floor(coords).astype(np.int32)
    xp, yp = ij[:, :, 0].clip(0, w - 1), ij[:, :, 1].clip(0, h - 1)
    point = previous[yp, xp]
    base = np.floor(coords - .5).astype(np.int32)
    fraction = coords - .5 - base.astype(np.float32)
    tap_coords = [((base[:, :, 0] + dx).clip(0, w - 1),
                   (base[:, :, 1] + dy).clip(0, h - 1))
                  for dx, dy in [(0, 0), (1, 0), (0, 1), (1, 1)]]
    taps = [linear(previous[y, x, :3]) for x, y in tap_coords]
    fx, fy = fraction[:, :, 0, None], fraction[:, :, 1, None]
    tap_weights = [(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy]
    history = sum(t * q for t, q in zip(taps, tap_weights))
    fractional = coords - np.floor(coords)
    return dict(coords=coords, point=point, xp=xp, yp=yp,
                history_linear=history, history_rgb=encoded(history),
                span=np.maximum.reduce(taps) - np.minimum.reduce(taps),
                safe=np.all((fractional > .01) & (fractional < .99), axis=2),
                in_bounds=np.all((coords >= 0) & (coords < [w, h]), axis=2),
                tap_coords=tap_coords, tap_weights=tap_weights)


def stage_sheet(scene, frame, box, panels, dest, font):
    scale = 3 if scene == 'minecraft' else 2
    width, height = (box[2] - box[0]) * scale, (box[3] - box[1]) * scale
    sheet = Image.new('RGB', (len(panels) * (width + 8) + 8, height + 62), (18, 20, 23))
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 8), f'{scene} f{frame} / ROI {box} / {scale}x nearest / no tone change / history*=ideal CPU sampler', fill='white', font=font)
    for i, (label, array) in enumerate(panels):
        x = 8 + i * (width + 8)
        draw.text((x, 31), label, fill='white', font=font)
        sheet.paste(Image.fromarray(array).resize((width, height), Image.Resampling.NEAREST), (x, 56))
    path = dest / f'{scene}-stages-f{frame}.png'
    sheet.save(path)
    return dict(path=str(path), sha256=sha(path), frame=frame, roi=list(box),
                scale=scale, filter='nearest', tone_adjustment=False,
                reconstructed_panel='History* CPU', other_panels='actual saved GPU captures')


def seam_trace(frame, box, arrays, current, previous, coverage, edge, weight, rec,
               previous_coverage, previous_edge, native4):
    """A fixed screen strip proxy, NOT world-space tracking or ground truth."""
    x0, y0, _, _ = box
    lo, hi = 578 - y0, 612 - y0
    left, right = 966 - x0, 984 - x0
    luma = arrays['spatial'][lo:hi, left:right] @ LUMA
    x = 966 + int(np.argmin(luma.mean(axis=0)))
    col = x - x0
    flank_world = [x - 6, x - 5, x - 4, x + 4, x + 5, x + 6]
    flank = np.array(flank_world) - x0
    result = dict(frame=frame, strip=[966, 578, 984, 612],
                  selected_column=x, column_y_half_open=[578, 612],
                  column_rule='lowest mean current-spatial display luma within fixed screen strip',
                  background_columns=flank_world, world_tracking=False,
                  selected_pixels=int(coverage[lo:hi, col].sum()), pixels=hi - lo,
                  raw_edge_pixels=int(edge[lo:hi, col].sum()),
                  history_weight_mean=float(weight[lo:hi, col][coverage[lo:hi, col]].mean()))
    for label, array in arrays.items():
        line = float((array[lo:hi, col] @ LUMA).mean())
        background = float((array[lo:hi, flank] @ LUMA).mean())
        result[label + '_line_luma'] = line
        result[label + '_background_luma'] = background
        result[label + '_contrast'] = background - line
    result['contrast_change_from_spatial_percent'] = 100 * (result['output_contrast'] / result['spatial_contrast'] - 1)
    py, px = 590 - y0, col
    point = dict(pixel=[x, 590], selected=bool(coverage[py, px]),
                 current_raw_edge=bool(edge[py, px]), actual_history_weight=float(weight[py, px]),
                 raw_rgb=arrays['raw'][py, px].tolist(), spatial_rgba=current[py, px].tolist(),
                 ideal_sampled_history_rgb=rec['history_rgb'][py, px].tolist(),
                 actual_output_rgb=arrays['output'][py, px].tolist(),
                 control10_rgb=arrays['control10'][py, px].tolist(),
                 control4_pattern_on_rgb=native4[py, px].tolist(),
                 previous_pixel_coordinate=rec['coords'][py, px].tolist(),
                 point_alpha_rgba=rec['point'][py, px].tolist(), taps=[])
    for (tx, ty), tw in zip(rec['tap_coords'], rec['tap_weights']):
        xx, yy = int(tx[py, px]), int(ty[py, px])
        tap = dict(previous_frame_pixel=[xx, yy], stored_rgba=previous[yy, xx].tolist(),
                   ideal_bilinear_weight=float(tw[py, px, 0]))
        if previous_coverage is not None:
            tap['previous_frame_selected'] = bool(previous_coverage[yy, xx])
            tap['previous_frame_raw_edge'] = bool(np.any(previous_edge[yy, xx] > 0))
        point['taps'].append(tap)
    result['point_trace'] = point
    return result


def analyze_scene(scene, dest, font):
    receipt_path = DOC / f'{scene}-capture.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
    assert receipt['validation'] == 'PASS'
    report = Path(receipt['receipt']['report'])
    assert sha(report).upper() == receipt['receipt']['report_sha256'].upper()
    report_text = report.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in report_text and 'FAIL' not in report_text
    capture = Path(receipt['capture_root']).resolve()
    folder = capture / MODE
    box = ROIS[scene]
    x0, y0, x1, y1 = box
    roi = np.s_[y0:y1, x0:x1]
    rows, manifests, sheets, seams = [], [], [], []
    still_output, still_control = [], []
    for window, frames in WINDOWS.items():
        for frame in frames:
            prefix = folder / f'frame_{frame:05d}'
            suffixes = ['-raw.dds', '-current.dds', '-previous.dds', '-next-history.dds',
                        '-velocity.dds', '-edge.rg8', '-coverage.dds', '-weight.dds', '.png']
            paths = {suffix: Path(str(prefix) + suffix) for suffix in suffixes}
            native_path = capture / 'O-T2X-R' / f'frame_{frame:05d}.png'
            control_path = capture / CONTROL / f'frame_{frame:05d}.png'
            current = dds(paths['-current.dds'])
            raw = dds(paths['-raw.dds'])[roi][:, :, :3]
            previous = dds(paths['-previous.dds'])
            following = dds(paths['-next-history.dds'])
            velocity = dds(paths['-velocity.dds'])
            coverage = dds(paths['-coverage.dds'])[roi] > 0
            edge = np.any(edges(paths['-edge.rg8'])[roi] > 0, axis=2)
            weight = weight_dds(paths['-weight.dds'])[roi]
            output = rgb(paths['.png'])
            native = rgb(native_path)
            control = rgb(control_path)[roi]
            assert current.shape[:2] == previous.shape[:2] == output.shape[:2] == velocity.shape[:2] == (1061, 1920)
            rec = sample_history(previous, velocity, box)
            current = current[roi]
            out = output[roi]
            assert np.isfinite(weight).all() and ((weight >= 0) & (weight <= .5)).all()
            assert np.isfinite(rec['history_linear']).all()
            assert (weight[~coverage] == 0).all()
            nonselected_mismatch = int(np.any(out[~coverage] != current[:, :, :3][~coverage], axis=1).sum())
            feedback_mismatch = int(np.any(following[roi][:, :, :3] != out, axis=2).sum())
            alpha_mismatch = int((following[roi][:, :, 3] != current[:, :, 3]).sum())
            lc = linear(current[:, :, :3])
            mix = lc + (rec['history_linear'] - lc) * weight[:, :, None]
            prediction = encoded(mix)
            prediction[~coverage] = current[:, :, :3][~coverage]
            ca = current[:, :, 3].astype(np.float32) / 255
            pa = rec['point'][:, :, 3].astype(np.float32) / 255
            delta = (ca.astype(np.float64) ** 2 - (pa * pa).astype(np.float64)).astype(np.float32)
            calc_weight = .5 * np.clip(1 - np.sqrt(np.abs(delta) / 5) * 30, 0, 1)
            safe = coverage & rec['safe']
            assert safe.any()
            weight_error = float(np.abs(calc_weight[safe] - weight[safe]).max())
            # Conservative diagnostic envelope used by the preceding bilinear RGB gate.
            # Includes >=8-bit fractional addressing, filter/color conversion and UNORM.
            envelope = weight[:, :, None] * (rec['span'] / 128 + 1 / 255) + .5 / 255
            low = encoded(mix - envelope).astype(np.int16) - 1
            high = encoded(mix + envelope).astype(np.int16) + 1
            inside = (out.astype(np.int16) >= low) & (out.astype(np.int16) <= high)
            failures = int((~inside[safe]).sum())
            error = np.abs(out.astype(np.int16) - prediction.astype(np.int16))
            prior_prefix = folder / f'frame_{frame - 1:05d}'
            prior_edge_path = Path(str(prior_prefix) + '-edge.rg8')
            prior_coverage_path = Path(str(prior_prefix) + '-coverage.dds')
            prior_history_path = Path(str(prior_prefix) + '-next-history.dds')
            previous_edge = previous_coverage = None
            selection_mismatch = chain_mismatch = None
            if prior_edge_path.exists():
                previous_edge = edges(prior_edge_path)
                previous_coverage = dds(prior_coverage_path) > 0
                previous_hit = np.any(previous_edge[rec['yp'], rec['xp']] > 0, axis=2) & rec['in_bounds']
                expected = edge | previous_hit
                selection_mismatch = int((coverage[rec['safe']] != expected[rec['safe']]).sum())
            if prior_history_path.exists():
                chain_mismatch = int(np.any(dds(prior_history_path)[roi] != previous[roi], axis=2).sum())
            row = dict(scene=scene, window=window, frame=frame, roi=list(box),
                       roi_pixels=int(coverage.size), selected_pixels=int(coverage.sum()),
                       current_raw_edge_pixels=int(edge.sum()), previous_only_pixels=int((coverage & ~edge).sum()),
                       selected_zero_weight_pixels=int((coverage & (weight == 0)).sum()),
                       selected_weight_mean=float(weight[coverage].mean()),
                       selected_weight_min=float(weight[coverage].min()), selected_weight_max=float(weight[coverage].max()),
                       output_changed_from_spatial_pixels=int(np.any(out != current[:, :, :3], axis=2).sum()),
                       nonselected_mismatch_pixels=nonselected_mismatch, feedback_rgb_mismatch_pixels=feedback_mismatch,
                       feedback_alpha_mismatch_pixels=alpha_mismatch, chain_mismatch_pixels=chain_mismatch,
                       safe_selection_union_mismatch_pixels=selection_mismatch,
                       safe_sample_pixels=int(safe.sum()), safe_weight_max_error=weight_error,
                       ideal_rgb_max_error_levels=int(error[safe].max()),
                       ideal_rgb_mae_levels=float(error[safe].mean()), diagnostic_envelope_failure_channels=failures)
            assert nonselected_mismatch == feedback_mismatch == alpha_mismatch == failures == 0
            assert weight_error < 3e-6
            assert selection_mismatch in (0, None) and chain_mismatch in (0, None)
            rows.append(row)
            if window == 'still':
                still_output.append(ph(output)); still_control.append(ph(native))
            paths['control4'] = native_path
            paths['control10'] = control_path
            for label, path in [('previous_raw_edge', prior_edge_path), ('previous_coverage', prior_coverage_path), ('previous_feedback', prior_history_path)]:
                if path.exists(): paths[label] = path
            manifests.append(dict(scene=scene, frame=frame, files={k: dict(path=str(p), sha256=sha(p)) for k, p in paths.items()}))
            arrays = dict(raw=raw, spatial=current[:, :, :3], history_ideal=rec['history_rgb'],
                          output=out, control10=control)
            if scene == 'minecraft' and 128 <= frame <= 133:
                seams.append(seam_trace(frame, box, arrays, current, previous, coverage,
                                        edge, weight, rec, previous_coverage, previous_edge, native[roi]))
            panels = [('4 / Pattern ON', native[roi]), ('11 Raw', raw), ('11 Spatial', arrays['spatial']),
                      ('History* CPU', rec['history_rgb']), ('Actual selection', np.repeat((coverage * 255).astype(np.uint8)[:, :, None], 3, axis=2)),
                      ('11 Final', out)]
            sheets.append(stage_sheet(scene, frame, box, panels, dest, font))
    assert len(set(still_output)) == len(set(still_control)) == 1
    return dict(scene=scene, capture_root=str(capture), receipt_sha256=sha(receipt_path),
                report_sha256=sha(report), frames=rows, seam_trace=seams,
                source_manifest=manifests, sheets=sheets, stable_still_full_rgb=True)


def gallery(results, dest):
    parts = ['<!doctype html><meta charset="utf-8"><title>⑪ 선 소실 원인 추적</title>',
             '<style>body{background:#15171b;color:#eee;font:16px system-ui;margin:24px}a{color:#8fc7ff}img{max-width:100%;image-rendering:pixelated}figure{margin:18px 0}summary{cursor:pointer;padding:12px}p{max-width:1000px;line-height:1.7}</style>',
             '<h1>⑪ 입력 → 선택 → history → 출력 추적</h1>',
             '<p>원본 GPU 캡처의 raw, spatial, 실제 선택 mask와 최종 출력입니다. History*만 저장된 history·velocity로 재구성한 이상적인 CPU bilinear 표본입니다. 원본과 같은 밝기·색상, nearest 확대를 사용했습니다. 새 GPU 실행은 없습니다.</p>',
             '<p>④는 paired pattern On·전체 화면 T2X-R·spatial history입니다. ⑪은 Pattern Off·현재+직전 raw edge 선택·resolved RGB feedback입니다. ④·⑪ 차이를 하나의 요소 효과로 단정하지 않습니다.</p>',
             '<p>무손실 PNG를 기준으로 검사했습니다. Minecraft 129의 선 구간 34픽셀은 모두 선택되고 weight≈0.5였습니다. 현재 선 대비 47.257이 최종 27.098로 감소했습니다. 130에서는 현재 입력부터 대비가 약했습니다. 지표는 특정 화면 좌표 구간의 진단 대용값이며 객체 추적이나 temporal ground truth가 아닙니다.</p>',
             '<p><a href="trace.json">좌표·실제 weight·4 history texel·원본 해시</a> · <a href="frames.csv">프레임별 검증 수치</a></p>']
    for result in results:
        parts.append(f'<h2>{result["scene"]}</h2>')
        for window, frames in WINDOWS.items():
            parts.append(f'<details {"open" if window == "moving" else ""}><summary>{window}: {frames[0]}–{frames[-1]}</summary>')
            for sheet in result['sheets']:
                if sheet['frame'] in frames:
                    path = Path(sheet['path'])
                    parts.append(f'<figure><figcaption>f{sheet["frame"]} · ROI {sheet["roi"]} · {sheet["scale"]}× nearest</figcaption><a href="{html.escape(path.name)}"><img loading="lazy" src="{html.escape(path.name)}"></a></figure>')
            parts.append('</details>')
    (dest / 'comparison.html').write_text('\n'.join(parts), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'Deliverables/SMAA_11_FailureTrace_20261006')
    args = parser.parse_args()
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 13)
    results = [analyze_scene(scene, dest, font) for scene in ['minecraft', 'bistro']]
    rows = [r for s in results for r in s['frames']]
    with (dest / 'frames.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = dict(saved_roi_validation='PASS', quality_gate='NOT_PASSED',
                   new_gpu_execution=False, cgvqm_executed=False, performance_measured=False,
                   frame_count=len(rows), scene_count=len(results),
                   selection_union_frames_checked=sum(r['safe_selection_union_mismatch_pixels'] is not None for r in rows),
                   chain_frames_checked=sum(r['chain_mismatch_pixels'] is not None for r in rows),
                   diagnostic_envelope_failure_channels=sum(r['diagnostic_envelope_failure_channels'] for r in rows),
                   max_ideal_rgb_error_levels=max(r['ideal_rgb_max_error_levels'] for r in rows),
                   max_safe_weight_error=max(r['safe_weight_max_error'] for r in rows),
                   selected_zero_weight_pixels=sum(r['selected_zero_weight_pixels'] for r in rows),
                   nonselected_mismatch_pixels=sum(r['nonselected_mismatch_pixels'] for r in rows),
                   implementation_commit='b793b74',
                   branch='experiment/edge-persistence-resolved-rgb-feedback',
                   sampler_reference=SPEC, reference_sections=['7.18.8', '7.18.16'],
                   limitations=['ROI-only saved diagnostics; not whole-scene causal proof',
                                'CPU ideal bilinear sampling is not bit-exact hardware sampling',
                                'conservative RGB envelope is a diagnostic tolerance, not exact matching',
                                'strip contrast is display-luma and fixed screen coordinates; not object tracking or ground truth',
                                'case4 pattern/sampling/history differ; no single-factor causal attribution'])
    output = dict(summary=summary, scenes=results)
    (dest / 'trace.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    gallery(results, dest)
    doc_record = dict(summary=summary, deliverable=str(dest), frames=rows,
                      seam_trace=results[0]['seam_trace'],
                      source_manifest_sha256=sha(dest / 'trace.json'),
                      source_manifest=str(dest / 'trace.json'))
    (DOC / 'failure-trace.json').write_text(json.dumps(doc_record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    print(str(dest / 'comparison.html'))


if __name__ == '__main__':
    main()
