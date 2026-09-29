"""Combine independently validated item 5/6 reports without pooling timing runs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Docs/First-Edge-Pattern-Off'
MODES = {5: 'ABL-FirstEdge-TemporalOnly-PatternOff-R',
         6: 'ABL-Spatial-FirstEdge-PatternOff-R'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--item6-dir', type=Path, required=True)
    args = parser.parse_args()
    assert (args.item6_dir / 'source-commit.txt').read_text().strip() == '556f226'
    data, sources = {}, []
    for item, directory in [(5, OUT), (6, args.item6_dir)]:
        data[item] = {}
        for scene in ['bistro', 'minecraft']:
            data[item][scene] = {}
            for kind in ['capture', 'cgvqm', 'benchmark']:
                p = directory / f'{scene}-{kind}.json'
                raw = p.read_bytes()
                value = json.loads(raw)
                assert value['validation'] == 'PASS'
                data[item][scene][kind] = value
                sources.append(dict(item=item, path=str(p), sha256=hashlib.sha256(raw).hexdigest()))

    lines = ['# ⑤·⑥ 첫 패스 edge 선택: 지터 Off 독립 실험', '',
        '두 구성의 정지 상태 2위상 교대는 해소됐다. 원본 spatial SMAA를 유지한 ⑥의 속도와 이동 품질은 장면별로 달라, 일괄적인 성능·품질 개선으로 결론내리지 않는다.', '',
        '| 구성 | 공간 처리 | temporal 적용 위치 | 비선택 출력 |',
        '|---|---|---|---|',
        '| ⑤ | 첫 edge 검출만 실행, 공간 혼합 없음 | 원본 첫 패스 edge | 지터 없는 raw 현재 RGB |',
        '| ⑥ | 원본 공간 SMAA 세 단계 모두 유지 | 원본 첫 패스 edge | 지터 없는 SMAA 1X 결과 |', '',
        '공통 기준선 `c51ca28`에서 각각 독립 분기했다. ⑤는 `experiment/first-edge-temporal-only-pattern-off`, ⑥은 `experiment/spatial-first-edge-pattern-off`다. 필요한 선행 커밋만 가져왔다. ⑥ 결과의 고정 버전은 `556f226`이다.', '',
        'Projection jitter와 해당 경로의 spatial subsample pattern을 끈 ablation이며 Standard T2X와 같은 표본 패턴은 아니다. Native temporal 계산, camera/depth reprojection, 각 프레임 입력을 저장하는 history는 보존했다. 이번 변경에 새 렌더 패스나 dilation은 없다. 원본 TSCMAA 전체를 재현한 결과가 아니며 기존 8-case 기본값은 바꾸지 않았다.', '',
        '두 장면 각 240프레임에서 선택 출력은 같은 Off full 결과와, 비선택 출력은 현재 입력과 일치했다. ⑤의 현재 RGB는 AA-Off, ⑥은 실제 O-1X와 일치했다. 독립 재실행·기존 On control hash 및 ⑤/⑥ edge mask도 일치했다. 정지 초반 20~59와 후반 200~239 모두 Off의 인접 RGB 차이와 mask 전환은 0이었다. 이동 중 고스팅·깜빡임 전체가 해결됐다는 뜻은 아니다.', '',
        '| 장면 | 전체 화면 대비 선택 비율 |', '|---|---:|']
    for scene in ['bistro', 'minecraft']:
        a, b = (data[i][scene]['capture']['windows']['all']['selected_percent_mean'] for i in [5, 6])
        assert a == b
        lines.append(f'| {scene} | {a:.4f}% |')

    lines += ['', '## 품질', '',
        '공식 CGVQM-2 점수이며 높을수록 좋다. 같은 프레임·supersample spatial reference와 무손실 RGB 입력을 사용했다. 이 reference와 점수는 절대 고스팅 정답이 아니다. 이동은 60~179, 이동 후 정지 전환은 160~219프레임이다.', '',
        '| 장면·구간 | 원본 SMAA T2X-R | ⑤ Off 선택 | ⑥ Off 선택 |', '|---|---:|---:|---:|']
    for scene in ['bistro', 'minecraft']:
        for window in ['moving', 'transition']:
            score = {i: data[i][scene]['cgvqm']['results'][window]['scores'] for i in [5, 6]}
            assert score[5]['O-T2X-R'] == score[6]['O-T2X-R']
            lines.append(f"| {scene} {window} | {score[5]['O-T2X-R']:.4f} | {score[5][MODES[5]]:.4f} | {score[6][MODES[6]]:.4f} |")
    lines += ['', '원본과의 차이는 선택 처리뿐 아니라 표본 패턴 변화도 포함하며, ⑤는 공간 혼합 유무까지 다르다. 순수 선택 효과용 Off full 대조 점수는 각 독립 보고서에 기록했다. 지터를 끈 결과에서는 서로 다른 subpixel 표본을 누적하는 T2X의 이점을 보존하지 못한다.', '',
        '## 성능', '',
        'RTX 3060 Ti, 1920×1061 Ultra, hidden, 300 warmup, 각 구성 4,800프레임×4회 교차 측정이다. 품질 분석과 동시에 실행하지 않았다. 아래 ⑥ 비교는 같은 실행 안의 원본 SMAA T2X-R 기준이며 음수는 시간 감소다.', '',
        '| 장면 | 원본 AA ms | ⑥ Off 선택 AA ms | AA 증감 | resolve 증감 |', '|---|---:|---:|---:|---:|']
    for scene in ['bistro', 'minecraft']:
        b = data[6][scene]['benchmark']
        c = b['comparisons']['off_selective_vs_native_on']
        lines.append(f"| {scene} | {b['means_ms']['O-T2X-R']['SMAA']:.6f} | {b['means_ms'][MODES[6]]['SMAA']:.6f} | {c['SMAA']['delta_percent']:+.3f}% | {c['SF_Resolve']['delta_percent']:+.3f}% |")
    lines += ['', '⑤는 edge 검출을 똑같이 수행하는 temporal-only Off full과 비교한다. 이 대조군의 시간을 원본 spatial SMAA T2X-R 시간으로 해석하지 않는다. ⑤와 ⑥ 사이 절대 시간 차이를 하나의 paired 실험 효과로 계산하지 않는다.', '',
        '| 장면 | ⑤ Off 선택 AA 증감 | ⑤ Off 선택 resolve 증감 |', '|---|---:|---:|']
    for scene in ['bistro', 'minecraft']:
        c = data[5][scene]['benchmark']['comparisons']['selection_pattern_off']
        lines.append(f"| {scene} | {c['SMAA']['delta_percent']:+.3f}% | {c['FE_Resolve']['delta_percent']:+.3f}% |")
    lines += ['', '평균 FPS·1% low, WholeFrame, 반복별 mean과 표준편차·p95/p99는 각 benchmark JSON에 보존했다. AA 일부 구간의 시간 감소를 같은 비율의 전체 FPS 증가로 표현하지 않는다.', '',
        '## 판단과 자료', '',
        '정지 떨림의 원인 분리는 통과했다. ⑥ Bistro는 AA 비용을 줄였지만 Minecraft에서는 소폭 늘었다. Minecraft 이동 품질 점수는 높아졌고, Bistro 정지 전환 품질은 낮아졌다. 따라서 지터 Off를 모든 장면의 최종 해법으로 확정하지 않는다. Object motion, 변형 물체, 가려짐 해제의 품질을 검증한 결과도 아니다.', '',
        '- [⑤ 상세 보고서](report.md)',
        '- [⑥ 상세 보고서: 고정 커밋 556f226](https://github.com/Anchovia/Adaptive-SMAA/blob/556f226/Docs/Spatial-First-Edge-Pattern-Off/report.md)',
        '- `pair-provenance.json`: 두 브랜치 자료의 경로와 SHA-256.',
        '- `validation-notes.json`: 제외한 오프라인 분석과 같은 엄격한 기준으로 재검증한 기록.', '',
        '시각 자료는 이전 On 정지 artifact가 큰 동일 ROI를 골랐다. 전체 장면의 대표 품질 또는 정량평가 입력으로 사용하지 않는다.', '']
    for item, directory in [(5, OUT), (6, args.item6_dir)]:
        visual = json.loads((directory / 'visual-provenance.json').read_text())
        for scene, record in visual.items():
            gif = Path(record['gif']).as_posix()
            mp4 = Path(record['video']).as_posix()
            lines.append(f'- {item}번 {scene}: [정지 On/Off GIF]({gif}), [이동 60 FPS MP4]({mp4})')
    (OUT / 'comparison-5-6.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (OUT / 'pair-provenance.json').write_text(json.dumps(dict(item6_commit='556f226', sources=sources), indent=2) + '\n')
    print('PASS: independent item 5/6 comparison generated')


if __name__ == '__main__':
    main()
