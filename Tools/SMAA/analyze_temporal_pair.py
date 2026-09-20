"""Validate independent process pairs; frames are not independent replicates."""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics as st
from datetime import datetime
from pathlib import Path

A = 'O-T2X-R'
B = 'ABL-ScalarWeight-001-R'
METRICS = ['SMAA', 'Spatial', 'Resolve', 'WholeFrame', 'WallFrame']
# NIST table, cumulative 0.975, df=5; rounded to the published precision.
T95_DF5 = 2.571


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_run(receipt):
    path = Path(receipt['report'])
    text = path.read_text(encoding='utf-8-sig')
    assert digest(path) == receipt['report_sha256'].lower(), path
    required = ['Aggregate: PASS', 'API:  DirectX11', '1920 x 1061',
                'NVIDIA GeForce RTX 3060 Ti', 'Vsync:        OFF', 'Warmup: 300',
                'Repeats: 1', 'Purpose: paired GPU performance; no PNG or candidate readback',
                'Common preconditioning: O-T2X-R', f"Scene: {receipt['scene']}",
                f"Independent process pair order: {receipt['order']}"]
    assert all(s in text for s in required) and 'Aggregate: FAIL' not in text, path
    frames = 4800 if receipt['phase'] == 'Benchmark' else 240
    assert f'Frames: {frames}\n' in text
    elapsed = re.findall(r'Focused preconditioning elapsed seconds: ([\d.]+)', text)
    assert len(elapsed) == 1 and 30 <= float(elapsed[0]) < 60
    rows = []
    distributions = []
    for line in text.splitlines():
        v = [s.strip() for s in next(csv.reader([line]))]
        if v and v[0] == 'timing':
            rows.append(dict(mode=v[1], run=int(v[2]), metric=v[3], samples=int(v[4]),
                             mean_ms=float(v[5]), p95_ms=float(v[6]), threshold=float(v[7])))
        if v and v[0] == 'distribution':
            distributions.append(dict(mode=v[1], run=int(v[2]), metric=v[3], samples=int(v[4]),
                median_ms=float(v[5]), sample_std_ms=float(v[6]), p99_ms=float(v[7]),
                wall_fps=float(v[8]), wall_1pct_low_fps=float(v[9])))
    expected_order = [A, B] if receipt['order'] == 'AB' else [B, A]
    expected = [(mode, metric) for mode in expected_order for metric in METRICS]
    for collection in (rows, distributions):
        assert [(r['mode'], r['metric']) for r in collection] == expected
        assert all(r['samples'] == frames and r['run'] == 0 for r in collection)
    for r, d in zip(rows, distributions):
        assert r['threshold'] == (0 if r['mode'] == A else .01)
        assert all(math.isfinite(r[k]) and r[k] > 0 for k in ('mean_ms', 'p95_ms'))
        assert all(math.isfinite(d[k]) and d[k] >= 0 for k in
                   ('median_ms', 'sample_std_ms', 'p99_ms', 'wall_fps', 'wall_1pct_low_fps'))
        assert d['median_ms'] <= r['p95_ms'] <= d['p99_ms']
        if r['metric'] == 'WallFrame':
            assert abs(d['wall_fps'] - 1000/r['mean_ms']) < .001
        else:
            assert d['wall_fps'] == d['wall_1pct_low_fps'] == 0
    return dict(receipt=receipt, preconditioning_seconds=float(elapsed[0]),
                rows=rows, distributions=distributions)


def summary(runs, metric):
    pairs = []
    for run in runs:
        values = {r['mode']: r['mean_ms'] for r in run['rows'] if r['metric'] == metric}
        a, b = values[A], values[B]
        pairs.append(dict(index=run['receipt']['pair_index'], order=run['receipt']['order'],
                          original_ms=a, scalar_ms=b, delta_ms=b-a, delta_percent=(b/a-1)*100))
    differences = [p['delta_ms'] for p in pairs]
    mean = st.mean(differences)
    sd = st.stdev(differences)
    half = T95_DF5 * sd / math.sqrt(6)
    a = st.mean(p['original_ms'] for p in pairs)
    b = st.mean(p['scalar_ms'] for p in pairs)
    return dict(original_mean_ms=a, scalar_mean_ms=b, ratio_of_means_percent=(b/a-1)*100,
                mean_pair_percent=st.mean(p['delta_percent'] for p in pairs),
                mean_delta_ms=mean, paired_std_ms=sd, paired_t95_ms=[mean-half, mean+half],
                slower_pairs=sum(d > 0 for d in differences), pairs=pairs,
                order_mean_delta_ms={o: st.mean(p['delta_ms'] for p in pairs if p['order'] == o)
                                     for o in ('AB', 'BA')})


def analyze(receipt_path, output, smoke_only=False):
    receipts = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
    assert len({r['report'] for r in receipts}) == len(receipts)
    assert len({r['executable_sha256'] for r in receipts}) == 1
    assert all(r['window'] == 'hidden' for r in receipts)
    for prev, nxt in zip(receipts, receipts[1:]):
        assert datetime.fromisoformat(prev['completed_utc']) <= datetime.fromisoformat(nxt['started_utc'])
    runs = [read_run(r) for r in receipts]
    smokes = [r for r in runs if r['receipt']['phase'] == 'Smoke']
    assert sorted((r['receipt']['scene'], r['receipt']['order']) for r in smokes) == [
        ('bistro', 'AB'), ('bistro', 'BA'), ('minecraft', 'AB'), ('minecraft', 'BA')]
    if smoke_only:
        print('PASS: four smoke runs, orders, sample counts, common preconditioning, one EXE')
        return
    formal = [r for r in runs if r['receipt']['phase'] == 'Benchmark']
    assert len(formal) == 12
    planned = []
    for i in range(6):
        for scene in (['bistro', 'minecraft'] if i % 2 == 0 else ['minecraft', 'bistro']):
            order = ('AB' if i % 2 == 0 else 'BA') if scene == 'bistro' else ('BA' if i % 2 == 0 else 'AB')
            planned.append((scene, i, order))
    assert [(r['receipt']['scene'], r['receipt']['pair_index'], r['receipt']['order']) for r in formal] == planned
    scenes = {}
    for scene in ('bistro', 'minecraft'):
        selected = [r for r in formal if r['receipt']['scene'] == scene]
        scenes[scene] = {metric: summary(selected, metric) for metric in METRICS}
    data = dict(validation='PASS', executable_sha256=receipts[0]['executable_sha256'],
                n_independent_process_pairs_per_scene=6, t_critical=T95_DF5,
                t_source='https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm',
                interval_note='Paired t interval of six process-mean differences, not frame samples. No equivalence claim; session/order dependence and small N limit inference.',
                scenes=scenes, runs=runs)
    output.mkdir(parents=True, exist_ok=True)
    (output/'results.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    lines = ['# 독립 프로세스 짝 비교 결과', '',
             'B−A가 양수면 ScalarWeight가 느리다. 각 장면 6 pair, pair당 4,800 frame×2 mode. 95% 구간은 프로세스 내 평균 차이 6개로 계산했다.', '',
             '| 장면 | 지표 | 원본 ms | Scalar ms | 평균 비율 변화 | B−A ms | paired 95% 구간 ms | 느린 pair |',
             '|---|---|---:|---:|---:|---:|---|---:|']
    for scene, metrics in scenes.items():
        for metric, v in metrics.items():
            lo, hi = v['paired_t95_ms']
            lines.append(f"| {scene} | {metric} | {v['original_mean_ms']:.6f} | {v['scalar_mean_ms']:.6f} | {v['ratio_of_means_percent']:+.3f}% | {v['mean_delta_ms']:+.6f} | [{lo:+.6f}, {hi:+.6f}] | {v['slower_pairs']}/6 |")
    for scene, metrics in scenes.items():
        lines += ['', f'## {scene}: 실행 순서와 개별 SMAA pair', '',
                  '| pair | 순서 | 원본 ms | Scalar ms | B−A ms | 변화 |',
                  '|---:|---|---:|---:|---:|---:|']
        for p in metrics['SMAA']['pairs']:
            lines.append(f"| {p['index']} | {p['order']} | {p['original_ms']:.6f} | {p['scalar_ms']:.6f} | {p['delta_ms']:+.6f} | {p['delta_percent']:+.3f}% |")
        lines += ['', '| 지표 | AB 평균 B−A ms | BA 평균 B−A ms |', '|---|---:|---:|']
        for metric, v in metrics.items():
            lines.append(f"| {metric} | {v['order_mean_delta_ms']['AB']:+.6f} | {v['order_mean_delta_ms']['BA']:+.6f} |")
    lines += ['', '## 검증과 해석 범위', '',
              '4개 smoke 및 12개 benchmark의 PASS, mode 순서, 표본 수, 공통 원본 예열, 실행파일 및 보고서 hash, 순차 실행을 검증했다. 원시 보고서 경로와 SHA-256, 분포 통계는 results.json에 있다.', '',
              '동일 GPU/세션의 순차 측정이며 재시작이 열·클럭 상태의 독립을 보장하지 않는다. 0 포함 구간은 동등성 증명이 아니다. 사전 동등성 허용 폭은 설정하지 않았다. 보조 지표의 다중 비교와 작은 표본에 유의한다. Hidden 실행 결과를 일반 게임 FPS 또는 모든 GPU에 일반화하지 않는다.', '',
              '[측정 전 고정 조건](method.md). [NIST paired CI](https://www.itl.nist.gov/div898/handbook/prc/section3/prc312.htm), [t 임계값 표](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm): df=5, 0.975의 표 값 2.571 사용.', '']
    (output/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(scenes, indent=2))
    print('PASS:', output)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--receipts', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('Docs/Temporal-Contrast-Pair'))
    p.add_argument('--smoke-only', action='store_true')
    args = p.parse_args()
    analyze(args.receipts, args.output, args.smoke_only)
