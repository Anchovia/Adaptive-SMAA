"""Visualize verified temporal execution coverage, not history contribution."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from analyze_native_first_pass_edges import (
    ROOT, DOC, MEDIA_REF, IDS, CASES, LABELS, FONT, BOLD, SMALL,
    blob, coverage, dump, edge, gif, git_json, rgb_hash, sha,
)

TOTAL = 1920 * 1061
OUTDOC = DOC / 'Temporal-Coverage'


def rows(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and 'FAIL' not in text, path
    return [[s.strip() for s in r if s.strip()] for r in csv.reader(text.splitlines()) if r]


def execution(report, mode, frame):
    matches = [r for r in report if r[:3] == ['execution', mode, str(frame)]]
    assert len(matches) == 1 and matches[0][-1] == 'PASS', (mode, frame)
    return tuple(map(int, matches[0][3:5]))


def render(masks, counts, clip, frame):
    out = Image.new('L', (1152, 1026), 0)
    d = ImageDraw.Draw(out)
    d.text((12, 6), clip['title'] + ' · Temporal 실행 범위', font=BOLD, fill=255)
    phase = '정지' if frame >= 180 else '이동'
    d.text((12, 44), f"흰색 = 실행 / 검정 = 생략 · 2배 확대 · {clip['fps']/60:g}배속 · f{frame:03d} · {phase}", font=FONT, fill=220)
    for i, case in enumerate(CASES):
        x, y = (i % 2) * 576, 82 + (i // 2) * 448
        d.text((x + 12, y + 4), LABELS[case], font=FONT, fill=255)
        origin = 'GPU 실행 마스크' if case in (5, 6) else '실행 검증에 따른 범위 표시'
        d.text((x + 12, y + 33), f'{origin} · 전체 화면의 {100*counts[case]/TOTAL:.2f}%', font=SMALL, fill=220)
        crop = masks[case].resize((576, 384), Image.Resampling.NEAREST)
        out.paste(crop, (x, y + 64))
    d.text((12, 990), '계산 실행 위치만 표시 · history 혼합량 / 실제 색상 변화량을 뜻하지 않음', font=SMALL, fill=220)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene', choices=('bistro', 'minecraft'), required=True)
    p.add_argument('--output', type=Path, default=ROOT / 'Projects/CMAA2/Captures/temporal-coverage-20260930')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    OUTDOC.mkdir(parents=True, exist_ok=True)
    previous = json.loads((DOC / f'{a.scene}-analysis.json').read_text(encoding='utf-8'))
    assert previous['validation'] == 'PASS'
    old_frames = {f['frame']:f for f in previous['frames']}
    receipt = json.loads((DOC / f'{a.scene}-run.json').read_text(encoding='utf-8-sig'))
    assert sha(receipt['report']) == receipt['report_sha256'].lower()
    native_rows = rows(receipt['report'])
    native_capture = Path(previous['native_capture'])
    summary = git_json(MEDIA_REF, 'Docs/Six-Case-Stencil-Lifecycle/summary.json')
    media = git_json(MEDIA_REF, 'Docs/Six-Case-Stencil-Lifecycle/media.json')
    branches = {b['case']:b for b in summary['branches']}
    configs = {c:git_json(MEDIA_REF, f'Docs/Six-Case-Stencil-Lifecycle/case{c}/case.json') for c in CASES}
    expected = {c:git_json(branches[c]['commit'], f'Docs/Stencil-Lifecycle-Refresh/{a.scene}-rgb-hashes.json')[configs[c]['target']] for c in CASES}
    sources = {c:Path(git_json(MEDIA_REF, f'Docs/Six-Case-Stencil-Lifecycle/case{c}/{a.scene}-prior.json')['target_capture']) for c in (5, 6)}
    source_reports = {c:ROOT / 'Projects/CMAA2/AutoBench' / sources[c].parent.name / (sources[c].parent.name + '_results.csv') for c in (5, 6)}
    historical_rows = {c:rows(source_reports[c]) for c in (5, 6)}
    for c in (5, 6):
        saved_capture = Path(next(r[1] for r in historical_rows[c] if r[0] == 'capture_root'))
        assert saved_capture == sources[c].parent
    selected_clips = [e['clip'] for e in media['clips'] if e['clip']['scene'] == a.scene and e['clip']['id'] in IDS]
    used = sorted({f for clip in selected_clips for f in range(clip['start'], clip['end'])})
    masks_by_frame, frame_records = {}, []
    for f in used:
        check = [r for r in native_rows if r[:3] == ['mode_check', 'O-1X', str(f)]]
        assert len(check) == 1 and check[0][3:] == ['TemporalOff', 'PASS']
        assert execution(historical_rows[6], 'O-T2X-R', f) == (TOTAL, TOTAL)
        # Uniform controls are explicitly constructed from verified mode/draw data.
        # Neither control is mislabeled as a saved pixel-level GPU coverage dump.
        masks = {2:np.zeros((1061, 1920), dtype=bool), 4:np.ones((1061, 1920), dtype=bool)}
        hashes, rgb = {}, {}
        for c in CASES:
            folder = native_capture / configs[c]['target'] if c in (2, 4) else sources[c]
            rgb[c] = rgb_hash(folder / f'frame_{f:05d}.png')
            assert rgb[c] == expected[c][f], (c, f, 'corrected baseline RGB bridge')
            if c in (5, 6):
                path = folder / f'frame_{f:05d}-coverage.dds'
                masks[c] = coverage(path)
                hashes[c] = sha(path)
                rg, rg_hash = edge(folder / f'frame_{f:05d}-edge.rg8')
                assert rg_hash == old_frames[f]['rg8_sha256'][str(c)]
                assert np.array_equal(masks[c], rg)
                assert execution(historical_rows[c], folder.name, f) == (int(masks[c].sum()),) * 2
            if c == 4:
                # Bridge the full-screen GPU execution evidence to the latest control.
                old_hash = [r for r in historical_rows[6] if r[:3] == ['final_hash', 'O-T2X-R', str(f)]]
                assert len(old_hash) == 1 and old_hash[0][3] == sha(folder / f'frame_{f:05d}.png')
        assert np.array_equal(masks[5], masks[6])
        counts = {c:int(masks[c].sum()) for c in CASES}
        frame_records.append(dict(frame=f, execution_pixels=counts, gpu_coverage_dds_sha256=hashes,
                                  corrected_rgb_sha256=rgb, selective_equal=True, selective_equal_first_edge=True))
        frame_clips = [clip for clip in selected_clips if clip['start'] <= f < clip['end']]
        assert len(frame_clips) == 1, 'Overlapping clips need separate crops'
        x0, y0, x1, y1 = frame_clips[0]['roi']
        masks_by_frame[f] = ({c:Image.fromarray(masks[c][y0:y1, x0:x1]).convert('L') for c in CASES}, counts)
    print(a.scene, len(used), 'frames: coverage, execution counts and corrected RGB verified', flush=True)
    results = []
    for clip in selected_clips:
        frames = [render(*masks_by_frame[f], clip, f) for f in range(clip['start'], clip['end'])]
        result = gif(a.output / (clip['id'] + '-temporal-coverage.gif'), frames, clip['fps'])
        preview = a.output / (clip['id'] + '-preview.png')
        frames[len(frames)//2].save(preview)
        included = [r for r in frame_records if clip['start'] <= r['frame'] < clip['end']]
        ratio = {c:float(np.mean([r['execution_pixels'][c] for r in included])) / TOTAL * 100 for c in CASES}
        results.append(dict(clip=clip, temporal_coverage=result, preview=str(preview.resolve()), mean_full_screen_execution_percent=ratio))
    shader_path = 'Projects/CMAA2/SMAA/FirstEdgeStencil.hlsl'
    witness = blob(MEDIA_REF, shader_path)
    assert b'FirstEdgeStencilCoveragePS' in witness and b'coverage = 1.0;' in witness
    out = dict(validation='PASS', scene=a.scene, evidence_commit=MEDIA_REF,
        native_edge_validation_commit='c26850d', corrected_branch_pins={c:branches[c] for c in CASES},
        source_reports={c:dict(path=str(path), sha256=sha(path)) for c, path in source_reports.items()},
        native_report=dict(path=receipt['report'], sha256=sha(receipt['report'])),
        coverage_witness=dict(commit=MEDIA_REF, path=shader_path, sha256=hashlib.sha256(witness).hexdigest()),
        masks={2:'Constructed black: TemporalOff verified per frame; no temporal pass.',
               4:'Constructed white: native full-screen resolve; per-frame PSInvocations and SamplesPassed equal width*height, RGB hash bridged to corrected control. Not a saved GPU coverage image.',
               5:'Saved GPU MRT execution witness, written 1 only where temporal resolve passed early stencil; identical to stored first-pass RG>0.',
               6:'Saved GPU MRT execution witness, written 1 only where temporal resolve passed early stencil; identical to stored first-pass RG>0.'},
        frames=frame_records, clips=results,
        interpretation='Execution coverage only. White does not imply nonzero history weight or nonzero final-current RGB difference. No new GPU run, timing, quality score, AA algorithm, jitter, or dilation change.')
    dump(OUTDOC / f'{a.scene}.json', out)
    print(a.scene, 'PASS: decoded GIF pixels and timing exact;', [(r['clip']['id'], r['mean_full_screen_execution_percent'][5]) for r in results], flush=True)


if __name__ == '__main__':
    main()
