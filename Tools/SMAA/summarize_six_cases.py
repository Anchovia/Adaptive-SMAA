"""Summarize completed independent cases; never invent unmeasured cells or pool runs."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Docs/Six-Case-Comparison'
SCENES = ['bistro', 'minecraft']
SEL = {5: 'ABL-FirstEdge-TemporalOnly-PatternOff-R', 6: 'ABL-Spatial-FirstEdge-PatternOff-R'}
ON = {5: 'ABL-FirstEdge-TemporalOnly-R', 6: 'ABL-SpatialFirstEdge-T2X-R'}
REVS = {'B': 'e14f122', 'T': 'e2bbf87', 'P5': '2e3ac6c', 'P6': '556f226', 'F5': 'a848c71'}
DIRS = {'B': 'Docs/Baseline-Restart', 'T': 'Docs/Temporal-Only-Control',
        'P5': 'Docs/First-Edge-Pattern-Off', 'P6': 'Docs/Spatial-First-Edge-Pattern-Off',
        'F5': 'Docs/First-Edge-Temporal-Only'}
SOURCES = []


def read(group, name):
    rev = subprocess.check_output(['git', 'rev-parse', REVS[group]], cwd=ROOT).decode().strip()
    path = DIRS[group] + '/' + name
    raw = subprocess.check_output(['git', 'show', rev + ':' + path], cwd=ROOT)
    value = json.loads(raw)
    assert value['validation'] == 'PASS', (group, name)
    SOURCES.append(dict(group=group, commit=rev, path=path, sha256=hashlib.sha256(raw).hexdigest(),
                        url=f'https://github.com/Anchovia/Adaptive-SMAA/blob/{rev}/{path}'))
    return value


def extract():
    baseline = read('B', 'performance.json')
    temporal = read('T', 'performance.json')
    cases = [dict(id=i, name=name, spatial=spatial, temporal=taa, jitter=jitter, scenes={})
             for i, name, spatial, taa, jitter in [
                 (1, 'AA-Off', '없음', '없음', 'Off'),
                 (2, 'SMAA 1X', '원본 SMAA', '없음', 'Off'),
                 (3, 'Temporal-only', '없음', '전체 화면', 'On'),
                 (4, '원본 SMAA T2X-R', '원본 SMAA', '전체 화면', 'On'),
                 (5, 'Edge-selective temporal-only', '없음', '첫 패스 edge', 'Off'),
                 (6, 'SMAA + edge-selective temporal', '원본 SMAA', '첫 패스 edge', 'Off')]]
    diagnostics, comparisons = [], []
    for scene in SCENES:
        bc = read('B', scene + '-capture.json')
        tc = read('T', scene + '-capture.json')
        bq = read('B', scene + '-cgvqm.json')
        p = {i: read(f'P{i}', scene + '-benchmark.json') for i in [5, 6]}
        c = {i: read(f'P{i}', scene + '-capture.json') for i in [5, 6]}
        q = {i: read(f'P{i}', scene + '-cgvqm.json') for i in [5, 6]}
        temporal_scopes = read('F5', scene + '-benchmark-performance.json')
        assert temporal_scopes['repeats'] == 4 and temporal_scopes['frames_per_repeat'] == 4800
        for i in [5, 6]:
            assert p[i]['repeats'] == 4 and p[i]['sample_frames_per_run'] == 4800
            assert sum(c[i]['mismatches'].values()) == 0
        for case in cases:
            i = case['id']
            value = dict(aa_ms=None, run_mean_std_ms=None, timing_group=None,
                         resolve_ms=None, resolve_group=None, resolve_run_mean_std_ms=None,
                         moving_cgvqm2=None, transition_cgvqm2=None, static_step={})
            if i == 2:
                record = baseline['scenes'][scene]['modes']['O-1X']['SMAA']
                value.update(aa_ms=record['mean_ms'], run_mean_std_ms=record['run_mean_std_ms'], timing_group='B')
            elif i == 3:
                record = temporal['scenes'][scene]['modes']['ABL-TemporalOnly-R']
                value.update(aa_ms=record['mean_ms'], run_mean_std_ms=record['run_mean_std_ms'], timing_group='T')
                resolve = temporal_scopes['metrics']['ABL-TemporalOnly-R']['FE_Resolve']
                value.update(resolve_ms=resolve['mean_ms'], resolve_group='F5',
                             resolve_run_mean_std_ms=resolve['run_mean_std_ms'])
            elif i >= 4:
                group = 5 if i == 5 else 6
                mode = SEL[i] if i in SEL else 'O-T2X-R'
                value.update(aa_ms=p[group]['means_ms'][mode]['SMAA'],
                             run_mean_std_ms=p[group]['run_mean_std_ms'][mode]['SMAA'], timing_group=f'P{group}')
                metric = 'FE_Resolve' if group == 5 else 'SF_Resolve'
                value.update(resolve_ms=p[group]['means_ms'][mode][metric], resolve_group=f'P{group}',
                             resolve_run_mean_std_ms=p[group]['run_mean_std_ms'][mode][metric])
            for window in ['initial_still', 'late_still']:
                if i in [1, 2, 4]:
                    m = {1: 'AA-Off', 2: 'O-1X', 4: 'O-T2X-R'}[i]
                    s = bc['static'][window][m]
                    step, unique = s['rgb_step'], s['unique_rgb_frames']
                elif i == 3:
                    s = tc['static'][window]['ABL-TemporalOnly-R']
                    step, unique = s['mean_rgb_step'], s['unique_rgb_frames']
                else:
                    s = c[i]['windows'][window]
                    step, unique = s['rgb_step'][SEL[i]], s['unique_rgb_frames'][SEL[i]]
                assert step == 0 and unique == 1
                value['static_step'][window] = step
            for window in ['moving', 'transition']:
                base = bq['results'][window]
                if i in [2, 4]:
                    value[window + '_cgvqm2'] = base['smaa_1x_score' if i == 2 else 't2x_r_score']
                elif i in [5, 6]:
                    result = q[i]['results'][window]
                    assert result['scores']['O-T2X-R'] == base['t2x_r_score']
                    ref = base['one_x_record']
                    rec = result['records'][SEL[i]]
                    for key in ['pixel_sha256', 'frame_count', 'first_index', 'last_index', 'width', 'height']:
                        assert rec['reference_sequence'][key] == ref['reference_sequence'][key], (scene, window, key)
                    assert rec['configuration'] == ref['configuration']
                    assert rec['official_cgvqm']['commit'] == ref['official_cgvqm']['commit']
                    assert rec['test_round_trip']['mismatched_values'] == 0
                    value[window + '_cgvqm2'] = result['scores'][SEL[i]]
            if i in [5, 6]:
                value['selected_screen_percent'] = c[i]['windows']['all']['selected_percent_mean']
            case['scenes'][scene] = value
        for i in [5, 6]:
            diagnostics.append(dict(id=i, scene=scene, jitter='On', timing_group=f'P{i}',
                aa_ms=p[i]['means_ms'][ON[i]]['SMAA'],
                late_static_step=c[i]['windows']['late_still']['rgb_step'][ON[i]],
                cgvqm2=None))
            for name in (['selection_pattern_off'] if i == 5 else ['off_selective_vs_native_on', 'selection_pattern_off']):
                metrics = p[i]['comparisons'][name]
                resolve = 'FE_Resolve' if i == 5 else 'SF_Resolve'
                comparisons.append(dict(id=i, scene=scene, contrast=name, timing_group=f'P{i}',
                    aa_delta_percent=metrics['SMAA']['delta_percent'],
                    resolve_delta_percent=metrics[resolve]['delta_percent'],
                    aa_paired_percent_by_run=metrics['SMAA']['paired_percent_by_run']))
    relative = []
    for scene in SCENES:
        reference = cases[3]['scenes'][scene]
        for case in cases:
            value = case['scenes'][scene]
            for metric, group_key in [('aa_ms', 'timing_group'), ('resolve_ms', 'resolve_group')]:
                measured, base = value[metric], reference[metric]
                ratio = None if measured is None else measured / base * 100
                classification = ('not-executed' if measured is None else 'baseline' if case['id'] == 4
                                  else 'same-run-paired' if value[group_key] == 'P6' else 'cross-run-arithmetic-reference')
                relative.append(dict(id=case['id'], scene=scene, metric=metric, time_ms=measured,
                    source_group=value[group_key], baseline_id=4, baseline_group='P6', baseline_ms=base,
                    baseline_percent=ratio, delta_percent=None if ratio is None else ratio - 100,
                    classification=classification))
    for row in comparisons:
        if row['id'] == 6 and row['contrast'] == 'off_selective_vs_native_on':
            for key, metric in [('aa_delta_percent', 'aa_ms'), ('resolve_delta_percent', 'resolve_ms')]:
                ratio = next(r for r in relative if r['id'] == 6 and r['scene'] == row['scene'] and r['metric'] == metric)
                assert abs(ratio['delta_percent'] - row[key]) < 1e-10
    return dict(classification='existing-results-summary-not-unified-six-case-benchmark',
                validation='PASS', cases=cases, jitter_on_diagnostics=diagnostics,
                paired_comparisons=comparisons, baseline_relative=relative, sources=SOURCES)


def fmt(value, precision=4):
    return '미측정' if value is None else f'{value:.{precision}f}'


def write_relative_report(data):
    cases = data['cases']
    lines = ['# 원본 SMAA T2X-R 대비: 전체 AA와 temporal resolve', '',
        '기준선은 ④ 원본 SMAA T2X-R이다. 기존 6구성 표의 전체 AA 시간을 유지하고, P6 실행의 원본 시간을 고정 분모로 사용한다. ⑤·⑥은 지터 Off, ③·④는 On이다. 새 GPU 실행 없이 기존 자료를 정규화했다.', '',
        '**†는 서로 다른 실행의 시간으로 계산한 산술 참고값이다.** 동일 조건에서 입증한 속도 개선율로 쓰지 않는다. ④↔⑥은 같은 P6 실행의 짝 비교다. ②·③·⑤는 공간/temporal 처리 구성 자체도 원본과 다르다.', '',
        '계산: 기준선 비율 = 해당 시간 ÷ 원본 시간 × 100. 변화율 = 기준선 비율 − 100. 100%보다 작으면 측정된 시간이 작고, 변화율의 음수는 감소다. FPS 증가율은 아니다.', '']
    for metric, title in [('aa_ms', '1. 전체 AA GPU 시간'), ('resolve_ms', '2. Temporal resolve GPU 시간만')]:
        lines += ['## ' + title, '']
        if metric == 'aa_ms':
            lines += ['공간 SMAA, camera velocity 생성, 해당 경로의 입력 준비·edge 검출·resolve 등을 포함하는 AA 전체 scope다. 전체 장면 렌더 프레임 시간은 아니다.', '']
        else:
            lines += ['기존 temporal 결합 패스의 GPU timer만 비교한다. Current/velocity/history 읽기와 혼합, 선택 경로에서는 edge 읽기와 분기를 포함한다. **Camera velocity를 만드는 앞선 패스, 공간 SMAA, 입력 준비 비용은 제외**한다.', '']
        lines += ['| 구성 | Bistro ms | 원본 대비 비율 (변화율) | Minecraft ms | 원본 대비 비율 (변화율) |', '|---|---:|---:|---:|---:|']
        for case in cases:
            records = [next(r for r in data['baseline_relative'] if r['id'] == case['id'] and r['scene'] == s and r['metric'] == metric) for s in SCENES]
            mark = ' †' if any(r['classification'] == 'cross-run-arithmetic-reference' for r in records) else ''
            cells = []
            for r in records:
                if r['time_ms'] is None:
                    cells += ['미실행', '—']
                else:
                    cells += [f"{r['time_ms']:.6f}", f"{r['baseline_percent']:.2f}% ({r['delta_percent']:+.2f}%)"]
            lines.append('| ' + chr(0x2460 + case['id'] - 1) + ' ' + case['name'] + mark + ' | ' + ' | '.join(cells) + ' |')
        lines += ['']
    lines += ['①은 AA 패스 자체가 없고, ②는 temporal resolve를 실행하지 않는다. 미실행을 실측 0ms 또는 전체 렌더링 100% 단축으로 해석하지 않는다.', '',
        '③의 전체 AA 시간은 기존 표와 같은 T 실행, resolve 시간은 별도 단계 계측이 있는 F5 실행에서 가져왔다. **두 수치를 서로 빼서 나머지 패스 비용을 역산하지 않는다.** F5의 ③ resolve가 원본과 매우 가까운 것은 관측값이며, Bistro의 -0.04%를 검증된 개선이라고 표현하지 않는다.', '',
        '## 3. 가장 직접적인 비교: ④ 대 ⑥', '',
        '| 장면 | 전체 AA 변화 | Temporal resolve 변화 |', '|---|---:|---:|']
    for scene in SCENES:
        rows = {r['metric']: r for r in data['baseline_relative'] if r['id'] == 6 and r['scene'] == scene}
        lines.append(f"| {scene} | {rows['aa_ms']['delta_percent']:+.2f}% | {rows['resolve_ms']['delta_percent']:+.2f}% |")
    lines += ['', 'Temporal resolve는 전체 AA의 일부이므로, resolve에서 절약한 비율이 전체 AA에 그대로 적용되지는 않는다. ⑥은 공간 SMAA와 velocity 생성 등을 계속 수행한다. Bistro에서는 resolve가 약 0.00564ms 줄어도 전체 AA의 감소는 약 2.37%다. Minecraft에서는 resolve가 늘어 전체 AA도 소폭 증가했다.', '',
        '⑤의 전체 AA 시간이 원본보다 절반 수준인 것은 공간 SMAA를 수행하지 않는 구성 차이도 포함한다. 이를 공간 품질을 유지한 50% 최적화라고 주장하지 않는다. ⑤와 ⑥의 resolve 시간은 각 장면에서 비슷한 범위지만 서로 다른 실행의 결과이므로 작은 차이로 우열을 정하지 않는다.', '',
        '## 4. 출처', '',
        '| 항목 | 자료 | 고정 커밋 |', '|---|---|---|',
        '| ② 전체 AA | B: 원본 기준선 재검증 | `e14f122` |',
        '| ③ 전체 AA | T: Temporal-only 독립 대조 | `e2bbf87` |',
        '| ③ resolve | F5: 첫 edge 실험의 edge 검출 없는 ③ 대조군 | `a848c71` |',
        '| ⑤ 전체/resolve | P5: 지터 Off 실험 | `2e3ac6c` |',
        '| ④·⑥ 전체/resolve | P6: 공간 SMAA 유지 지터 On/Off 실험 | `556f226` |', '',
        'RTX 3060 Ti, DX11, 1920×1061 Ultra, hidden. 각 시간은 4,800프레임×4회 평균이다. 프레임 수명·history reset·timer 구성 차이는 [6개 구성 보고서](report.md)에 명시했다. 반올림 전 시간, 비율, 비교 분류와 입력 hash는 `comparison.json`의 `baseline_relative`와 `sources`에 보존했다.', '']
    (OUT / 'baseline-relative.md').write_text('\n'.join(lines), encoding='utf-8')


def write_report(data):
    cases = data['cases']
    number = {i: chr(0x2460 + i - 1) for i in range(1, 7)}
    label = lambda c: number[c['id']] + ' ' + c['name']
    lines = ['# AA 6개 구성: 시간·품질 비교 정리', '',
        '2026-09-29까지 완료한 독립 실험의 결과를 모았다. 주 표의 ⑤·⑥은 최근 검증을 마친 **지터 Off** 버전이며, 초기 지터 On 버전은 뒤의 별도 표에 보존했다. 기존 결과를 정리한 문서로, 6개를 새로 한 실행에 넣어 측정한 최종 비교 행렬은 아니다.', '',
        '## 1. 무엇을 비교했는가', '',
        '| 구성 | Spatial AA | Temporal 처리 | 지터 |', '|---|---|---|---|']
    for c in cases:
        lines.append(f"| {label(c)} | {c['spatial']} | {c['temporal']} | {c['jitter']} |")
    lines += ['', '③~⑥의 reprojection은 camera/depth 기반이다. Object motion vector까지 검증한 결과가 아니다. ⑤는 공간 혼합을 하지 않지만 선택에 필요한 원본 첫 edge 검출을 실행한다. ⑥은 원본 공간 SMAA 세 패스를 모두 보존한다. ⑤·⑥은 검출된 RG edge를 모두 사용하며, Intel의 non-dominant 제거로 절반을 고른 구현이 아니다.', '',
        '## 2. AA 처리 시간', '',
        '[원본 T2X-R=100% 기준 전체 AA·temporal resolve 비교표](baseline-relative.md)를 별도로 제공한다. 서로 다른 실행의 비율은 산술 참고값으로 명시했다.', '',
        '단위 ms. 표의 값은 **전체 AA GPU scope** 평균 ± 네 반복 평균의 표준편차다. Temporal resolve 단독 시간이나 전체 렌더 프레임 시간이 아니다. 작은 표준편차가 서로 다른 실행·계측 구조 사이의 편향까지 보정해 주지는 않는다.', '',
        '| 구성 | Bistro | Minecraft | 측정 묶음 |', '|---|---:|---:|---|']
    for c in cases:
        if c['id'] == 1:
            lines.append(f'| {label(c)} | AA 패스 미실행 | AA 패스 미실행 | — |')
            continue
        vals = [f"{c['scenes'][s]['aa_ms']:.6f} ± {c['scenes'][s]['run_mean_std_ms']:.6f}" for s in SCENES]
        lines.append(f"| {label(c)} | {vals[0]} | {vals[1]} | {c['scenes']['bistro']['timing_group']} |")
    lines += ['', '**①을 전체 렌더링 0ms로 뜻하는 것이 아니다.** AA 전용 패스를 실행하지 않으며, 다른 구성과 대응하는 전체 프레임 시간은 이 표에 없다.', '',
        'RTX 3060 Ti, DX11, 1920×1061, Ultra, hidden window, VSync Off. 측정 묶음별 clean process, 30초 사전 실행, mode별 300 warmup, 4,800프레임×4회 정·역 순서를 사용했다. B/T는 기존 AA 전체 timer를 쓰며, P5/P6에는 단계별 timer와 프레임 수명 교정·주기별 history reset이 있다. **묶음이 다른 행을 빼서 정확한 속도 향상률을 계산하지 않는다.** 각 묶음의 두 장면도 별도 실행이다.', '',
        '| 묶음 | 사용한 완료 결과 | 고정 커밋 |', '|---|---|---|',
        '| B | 원본 기준선 재검증: ② | `e14f122` |',
        '| T | Temporal-only 독립 대조: ③ | `e2bbf87` |',
        '| P5 | ⑤의 지터 On/Off 대조 | `2e3ac6c` |',
        '| P6 | ④와 ⑥의 지터 On/Off 대조 | `556f226` |', '',
        '③에는 첫 edge 검출이 없고 ⑤에는 그 비용이 포함된다. ③·⑤의 공간 AA 생략으로 줄어든 시간을 원본 SMAA의 동일 품질 최적화 효과로 표현하지 않는다.', '',
        '### 같은 실행에서 확인한 상대 비용', '',
        '음수는 시간 감소, 양수는 증가다. 아래 비교만 대응 실행 안에서 계산했다.', '',
        '| 비교 | 장면 | 전체 AA 변화 | Resolve 변화 |', '|---|---|---:|---:|']
    names = {(5, 'selection_pattern_off'): '⑤ Off 선택 vs edge 검출 포함 Off full',
             (6, 'off_selective_vs_native_on'): '⑥ Off 선택 vs ④ 원본 T2X-R',
             (6, 'selection_pattern_off'): '⑥ Off 선택 vs 공간 SMAA Off full'}
    for row in sorted(data['paired_comparisons'], key=lambda r: (r['id'], r['contrast'], r['scene'])):
        lines.append(f"| {names[row['id'], row['contrast']]} | {row['scene']} | {row['aa_delta_percent']:+.3f}% | {row['resolve_delta_percent']:+.3f}% |")
    lines += ['', '⑤의 이 대조군은 ③이 아니다. ③에는 없는 edge 검출을 full 쪽에도 넣어 선택의 효과만 분리했다. ④→⑥ Off 비교에는 지터 패턴 변경도 포함된다. 순수 edge 선택 효과는 같은 Off full과의 비교에서 판단한다.', '',
        '## 3. 품질: CGVQM-2', '',
        '**높을수록 좋다.** 이동=frame 60~179, 이동 후 정지 전환=160~219. 같은 60 FPS 카메라 경로, 같은 frame index와 supersample spatial reference를 사용했다. 표의 모든 완료 점수는 reference RGB hash·범위·해상도·공식 모델 commit·평가 설정의 일치를 확인했다.', '',
        '| 구성 | Bistro 이동 | Bistro 정지 전환 | Minecraft 이동 | Minecraft 정지 전환 |', '|---|---:|---:|---:|---:|']
    for c in cases:
        values = [fmt(c['scenes'][s][w + '_cgvqm2']) for s in SCENES for w in ['moving', 'transition']]
        lines.append('| ' + label(c) + ' | ' + ' | '.join(values) + ' |')
    lines += ['', '①과 ③은 출력·정지 안정성을 검증했지만 이 두 구간의 CGVQM을 아직 측정하지 않았다. 0점이나 다른 방식의 점수로 채우지 않았다. 과거 지터 On current-spatial 진단 결과를 AA-Off 또는 SMAA 1X 점수로 재사용하지 않았다.', '',
        '공식 CGVQM-2, CUDA, patch scale 4, mean을 사용했다. ⑤·⑥은 메모리 한도 때문에 원래 30프레임 추론 경계를 보존하는 최대 60프레임 단위 실행을 사용했고, 기존 native 점수와 0.00002 이내 일치를 확인했다. FFV1 입력은 RGB 무손실 검증을 통과했다. 참조는 공간 품질 proxy이므로 점수 하나로 고스팅·깜빡임·선명도를 각각 판정하지 않는다.', '',
        '## 4. 정지 떨림과 이전 지터 On 버전', '',
        '①~④와 주 표의 지터 Off ⑤·⑥은 **두 장면 모두** 정지 초반 20~59 및 후반 200~239에서 고유 RGB 프레임 수 1, 인접 RGB 평균 절댓값 차이 0이었다. 이는 검사한 정지 구간의 안정성이다. 공간 계단 현상이 없다는 뜻이나 이동 중 품질 보장이 아니다.', '',
        '이전 지터 On ⑤·⑥은 두 지터 위상이 번갈아 나와 정지 안정성 검사를 통과하지 못했다. 아래 시간은 P5/P6의 On 대조군을 사용해 Off와 같은 실행으로 대응시켰다. CGVQM은 이 On 선택 버전에서 미측정이다.', '',
        '| 이전 구성 | Bistro AA ms | Minecraft AA ms | Bistro 정지 RGB 차이 | Minecraft 정지 RGB 차이 |', '|---|---:|---:|---:|---:|']
    for i in [5, 6]:
        d = {r['scene']: r for r in data['jitter_on_diagnostics'] if r['id'] == i}
        lines.append(f"| {number[i]} 지터 On 선택 | {d['bistro']['aa_ms']:.6f} | {d['minecraft']['aa_ms']:.6f} | {d['bistro']['late_static_step']:.6f} | {d['minecraft']['late_static_step']:.6f} |")
    lines += ['', 'RGB 차이는 0~255 단위의 인접 프레임 평균 절댓값이며 후반 정지 구간 값이다. 이 실패를 일반 AA-Off/1X의 떨림으로 표현하지 않는다.', '',
        '주 표 ⑤·⑥ Off의 화면 전체 대비 평균 선택 비율은 Bistro '
        f"{cases[4]['scenes']['bistro']['selected_screen_percent']:.4f}%, Minecraft {cases[4]['scenes']['minecraft']['selected_screen_percent']:.4f}%다. ⑤와 ⑥의 edge mask는 모든 캡처 프레임에서 일치했다. 검출 edge 중 이 비율만 선택했다는 뜻은 아니다.", '',
        '## 5. 현재 판단과 남은 비교 항목', '',
        '- **정지 안정성:** 지터 Off ⑤·⑥에서 기존 교대 떨림이 해소됐다. ⑥의 공간 AA 보존도 검증됐다.',
        '- **성능:** ⑥은 ④ 대비 Bistro에서 AA 시간 2.37% 감소, Minecraft에서 1.19% 증가했다. 두 장면 모두 빨라진 결과는 아니다.',
        '- **품질:** ⑥의 CGVQM은 ④보다 Minecraft 이동 구간에서 높았고, Bistro 정지 전환에서는 낮았다. 전반적인 품질 우위로 단정하지 않는다.',
        '- **미측정:** ①·③ CGVQM 2장면×2구간, 같은 계측·수명·reset 조건으로 묶은 최종 6구성 성능 행렬이 남아 있다. 전체 프레임 시간/FPS까지 6행 모두 채운 표도 아직 아니다.',
        '- **개별 시각 문제:** 이동 고스팅·가려짐 해제·물체 움직임을 분리한 평가가 필요하다. 정지 RGB 차이와 CGVQM만으로 그 검증을 대신하지 않는다.', '',
        '현재 자료는 구현 의미와 확인된 차이를 정리하는 중간 비교표로 사용한다. 새로운 기능이나 최적화를 추가하기 전에 누락된 비교와 실제 병목의 우선순위를 결정하는 근거다.', '',
        '## 6. 출처와 재현', '',
        '이 보고서는 구현 변경·재빌드·새 GPU 측정 없이 고정 커밋의 PASS JSON을 읽어 생성했다. `comparison.json`에 반올림 전 수치, 측정 묶음, 정지 검사, 짝 비교, 모든 입력의 commit/path/SHA-256을 보존했다. 입력이 누락되거나 참조 조건이 다르면 생성기가 실패한다.', '',
        '```powershell',
        'python Tools/SMAA/summarize_six_cases.py', '```', '',
        '아래 고정 버전 상세 기록에 시각 자료, 실행 실패·재검증 이력 및 한계가 포함되어 있다.', '']
    for group, title in [('B', '①·②·④ 원본 기준선'), ('T', '③ Temporal-only'), ('P5', '⑤ 지터 Off'), ('P6', '⑥ 지터 Off')]:
        rev = next(s['commit'] for s in SOURCES if s['group'] == group)
        lines.append(f'- [{title} 상세 보고서](https://github.com/Anchovia/Adaptive-SMAA/blob/{rev}/{DIRS[group]}/report.md)')
    lines.append('')
    (OUT / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    data = extract()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'comparison.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_report(data)
    write_relative_report(data)
    print('PASS: six-case tables match pinned source JSONs; shared quality references/settings verified')


if __name__ == '__main__':
    main()
