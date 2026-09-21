"""Summarize completed speed gates without recomputing image quality."""
import hashlib
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Docs/Temporal-Speed-Limits'
BASE = 'ABL-ScalarPairedDeJitter-001-R'
NATIVE = 'O-T2X-R'
PHASES = ['Capture', 'Smoke', 'ScreenBenchmark', 'GroupCapture',
          'GroupSmoke', 'GroupScreenBenchmark', 'Benchmark']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

records = []
checks = comparisons = 0
lines = ['# Speed-only 측정표', '',
         '전체 AA와 Resolve의 단위는 ms다. 퍼센트는 같은 실행의 비교군 대비다. '
         'Screen의 3회와 최종 확인의 4회는 한 프로세스 안의 교차 반복이며 독립 세션 표본이 아니다.', '']
for scene in ('bistro', 'minecraft'):
    for phase in PHASES:
        p = OUT / f'{scene}-{phase}.json'
        data = json.loads(p.read_text())
        r = data['receipt']
        assert sha(Path(r['report'])) == r['report_sha256'].lower()
        records.append(dict(scene=scene, phase=phase, receipt=r,
                            analysis_sha256=sha(p)))
        if phase.endswith('Capture'):
            assert all(x['match'] for x in data['modes'].values())
            checks += data['pattern_checks']
            comparisons += len(data['modes']) * len(data['indices'])
            continue
        assert data['validation'] == 'PASS'
        if phase.endswith('Smoke'):
            continue
        means = data['means']
        lines += [f'## {scene} / {phase}', '',
                  '| Mode | 전체 AA | Resolve | AA vs 기존 선택 | Resolve vs 기존 선택 | AA vs 원본 |',
                  '|---|---:|---:|---:|---:|---:|']
        for mode, value in means.items():
            aa, resolve = value['SMAA']['mean_ms'], value['Resolve']['mean_ms']
            def delta(metric, ref):
                return 100 * (value[metric]['mean_ms'] / means[ref][metric]['mean_ms'] - 1)
            lines.append(f"| {mode} | {aa:.9f} | {resolve:.9f} | {delta('SMAA', BASE):+.3f}% | {delta('Resolve', BASE):+.3f}% | {delta('SMAA', NATIVE):+.3f}% |")
        lines.append('')
        if phase != 'Benchmark':
            continue
        lines += ['### 최종 반복 차이와 실행 순서', '',
                  '| 비교 | 지표 | 평균 차이 µs | 느린 반복 | 정순 차이 µs | 역순 차이 µs | 차이의 표준편차 µs |',
                  '|---|---|---:|---:|---:|---:|---:|']
        for mode in means:
            if mode == NATIVE:
                continue
            for ref in (BASE, NATIVE):
                if mode == ref:
                    continue
                for metric in ('SMAA', 'Resolve', 'Spatial', 'WholeFrame'):
                    a, b = means[mode][metric]['runs'], means[ref][metric]['runs']
                    ds = [1000 * (x - y) for x, y in zip(a, b)]
                    lines.append(f'| {mode} − {ref} | {metric} | {st.mean(ds):+.6f} | {sum(x>0 for x in ds)}/{len(ds)} | {st.mean(ds[::2]):+.6f} | {st.mean(ds[1::2]):+.6f} | {st.stdev(ds):.6f} |')
        lines += ['', '각 run의 median, p95/p99, Wall FPS와 1% low는 같은 이름의 JSON에 저장했다.', '']

assert len(records) == 14
assert checks == 7200 and comparisons == 1590
lines += ['## 검증과 출처', '',
          f'패턴 검사 {checks}개, PNG 비교 {comparisons}개에서 불일치 0. 각 mode의 전체 240 frame 중 53개를 저장한 제한된 정확성 검사다.', '',
          '| 장면 | 단계 | AutoBench ID | 실행파일 SHA-256 |', '|---|---|---|---|']
for item in records:
    r = item['receipt']
    lines.append(f"| {item['scene']} | {item['phase']} | {Path(r['report']).parent.name} | `{r['executable_sha256']}` |")
(OUT / 'tables.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
(OUT / 'results.json').write_text(json.dumps(dict(
    validation='PASS', rendered_pattern_checks=checks, sampled_png_comparisons=comparisons,
    png_mismatch=0, runs=records), indent=2) + '\n', encoding='utf-8')
print(f'PASS: {len(records)} completed runs, {checks} pattern checks, {comparisons} PNG comparisons')
