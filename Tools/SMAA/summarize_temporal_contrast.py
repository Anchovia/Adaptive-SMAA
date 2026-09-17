"""Publish only complete clean-process contrast gates and their limitations."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
records=json.loads((root/'tmp/temporal-contrast-runs.json').read_text(encoding='utf-8-sig'))
result={'classification':'Initial engineering gate, not final eight-case or full-reference quality ranking',
        'baseline_commit':'88893dae85b3018c6db5de0d43c683b0e37536bf',
        'implementation_commit':'1efc5d31964a463e6b659cf7b934d1d0f5212dfe',
        'records':records,'scenes':{}}
for scene in ('bistro','minecraft'):
    base=root/'Projects/CMAA2/AutoBench/ContrastAnalysis'/scene
    q=json.loads((base/'quality.json').read_text());p=json.loads((base/'performance.json').read_text())
    assert all(v==0 for v in q['checks'].values())
    assert q['shape']==[1061,1920,3]
    assert q['modes']['O-T2X-R']['late_still_unique_png']==1
    for mode in ('ABL-Contrast-0005-R','ABL-Contrast-001-R','ABL-Contrast-002-R'):
        assert q['modes'][mode]['late_still_unique_png']==2
        assert q['modes'][mode]['two_frame_equal_of_38']==38
    for phase,source in [('Capture',root/q['source']),('Benchmark',root/p['source'])]:
        record=next(r for r in reversed(records) if r['scene']==scene and r['phase']==phase)
        path=Path(record['report'])
        assert path.exists() and 'Aggregate: PASS' in path.read_text(encoding='utf-8-sig')
        assert '1920 x 1061' in path.read_text(encoding='utf-8-sig')
        assert (path.parent if phase=='Capture' else path).resolve()==source.resolve()
    result['scenes'][scene]={'quality':q,'performance':p}
perf_hashes={r['executable_sha256'].lower() for r in records if r['phase']=='Benchmark'}
assert len(perf_hashes)==1
dest=root/'Docs/Temporal-Contrast-Initial';dest.mkdir(parents=True,exist_ok=True)
(dest/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Current-color contrast T2X: initial results','',
    '원본 T2X-R에서 현재 색상만으로 대비를 근사해 history 접근 전에 처리 여부를 결정한 실험이다.',
    '설계·실행 도구·실패 수정 사항은 [구현 문서](../SMAA-Temporal-Contrast-Experiment-ko.md)를 따른다.','',
    '후속 CGVQM·기준 영상 오차와 세 threshold의 실제 선택 수는 [정량 품질 결과](../Temporal-Contrast-Quality/report.md)에 별도로 기록했다.','',
    '이번 구현은 현재 색상의 공간 대비 근사로 velocity/history 읽기를 생략한다. ',
    '시험한 0.005/0.01/0.02에서 전체 SMAA 시간은 Bistro에서 2.53~4.41% 감소하고 Minecraft에서 1.21~2.27% 증가했다.',
    '추가 edge texture와 pass 없이 구현했지만, 시험한 threshold 모두 정지 후 2-frame 교대 변화를 남겼다. ',
    '따라서 속도 결과와 별개로 품질 유지 조건은 아직 통과하지 못했다.','',
    '## 검증 범위','',
    '- RTX 3060 Ti, DirectX 11, Original SMAA Ultra, camera reprojection On, paired jitter 유지.',
    '- 1920×1061, hidden window, VSync Off. 각 장면의 두 방식은 같은 바이너리와 카메라 경로를 사용했다.',
    '- 두 장면 × 9 mode × 240 PNG를 검사했다. 원본 반복 및 All/None 경계 출력이 일치했고, threshold 0.01의 선택/생략 pixel 의미 검증도 통과했다.',
    '- 기존 native shader 8종의 DXBC가 원본 기준점과 같다. 추가 edge texture/list/pass 없음.',
    '- 성능: 설정별 300 warm-up + 4,800 frame × 3회, 정방향/역방향/정방향. 캡처·영상 분석과 분리.',
    '- 아래 변화율은 해당 장면의 동일 실행 native control 대비다. 이전 branch의 절댓값과 비교하지 않는다.','',
    '## 전체 SMAA와 resolve 시간','',
    '| Scene | Mode | SMAA ms | SMAA 변화 | Resolve ms | Resolve 변화 |',
    '|---|---|---:|---:|---:|---:|']
for scene,data in result['scenes'].items():
    for mode in ('O-T2X-R','ABL-Contrast-All-R','ABL-Contrast-0005-R','ABL-Contrast-001-R','ABL-Contrast-002-R','ABL-Contrast-None-R'):
        m=data['performance']['modes'][mode];a,b=m['SMAA'],m['Resolve']
        lines.append(f"| {scene} | {mode} | {a['mean_ms']:.6f} | {a['percent_vs_native']:+.3f}% | {b['mean_ms']:.6f} | {b['percent_vs_native']:+.3f}% |")
lines+=['','## 반복 분산과 공간 처리 control','','run 평균 3개의 표본 표준편차다. 별도 통계적 유의성 검정을 주장하지 않는다.','',
    '| Scene | Mode | SMAA run SD ms | Spatial ms | Spatial 변화 |',
    '|---|---|---:|---:|---:|']
for scene,data in result['scenes'].items():
    for mode,m in data['performance']['modes'].items():
        lines.append(f"| {scene} | {mode} | {m['SMAA']['run_std_ms']:.6f} | {m['Spatial']['mean_ms']:.6f} | {m['Spatial']['percent_vs_native']:+.3f}% |")
lines+=['','## 정지 후 안정성과 선택 비율','',
    '후기 정지 frame 200~239의 화면 luma Δ1이며 단위는 0~255 brightness level이다. 낮은 시간 변화만으로 전반적 품질 우위를 단정하지 않는다.','',
    '| Scene | Mode | 후기 정지 luma Δ1 | 서로 다른 출력 수 | 2-frame 간격 일치 / 38 |',
    '|---|---|---:|---:|---:|']
for scene,data in result['scenes'].items():
    for mode,m in data['quality']['modes'].items():
        lines.append(f"| {scene} | {mode} | {m['late_still_luma_delta1']:.6f} | {m['late_still_unique_png']} | {m['two_frame_equal_of_38']} |")
for scene,data in result['scenes'].items():
    c=data['quality']['coverage_at_threshold_001']
    lines+=['',f"- {scene}, threshold 0.01: 평균 {100*c['mean']:.3f}%, 범위 {100*c['min']:.3f}~{100*c['max']:.3f}% 선택."]
lines+=['','## 해석과 제한','',
    '- 두 장면의 native와 All control은 후기 정지에 안정됐다. 시험한 세 대비 threshold는 두 출력이 번갈아 나오는 변화를 남겼다. 현재 구현을 품질 유지가 입증된 최종 개선안으로 채택하지 않는다.',
    '- GPU 선택률은 threshold 0.01만 별도 mask로 측정했다. 다른 threshold의 선택률을 역산하지 않는다.',
    '- 동일한 절대 linear-luma threshold도 장면의 밝기·질감에 따라 선택률이 크게 달라진다.',
    '- 속도는 표의 실제 측정치로 판단한다. static 교대 변화는 확인됐지만 absolute ghosting, reference 품질, 사용자 지각 임계값은 측정하지 않았다.',
    '- 카메라 경로는 초기 baseline의 flythrough를 두 장면에 공통 적용했다. Bistro는 어두운 외부 장면, Minecraft는 근거리 구조물과 텍스처가 포함된 경로다. 대표적인 모든 게임 장면으로 일반화하지 않는다.',
    '- raw PNG/CSV는 실행별 AutoBench 폴더에, 분석 CSV와 3배 느린 후기 정지 GIF는 `Projects/CMAA2/AutoBench/ContrastAnalysis/<scene>`에 보존했다.',
    '- 최초 jitter 불일치 캡처와 종료 실패 process는 정상 실행으로 세지 않는다. Minecraft 정상 재실행 PNG 2160개와 cached 분석 입력의 완전 일치를 확인한 뒤 계산 결과만 재사용했다.',
    '- 이 실험은 최종 8-case 설정이나 기존 Adaptive/ET2X 결과를 변경하지 않는다.','']
lines+=['## Threshold 0.01의 속도 해석','']
for scene,data in result['scenes'].items():
    modes=data['performance']['modes'];native=modes['O-T2X-R'];selected=modes['ABL-Contrast-001-R']
    lines.append(f"- {scene}: resolve {native['Resolve']['mean_ms']:.6f} → {selected['Resolve']['mean_ms']:.6f} ms "
                 f"({selected['Resolve']['percent_vs_native']:+.3f}%), 전체 SMAA {native['SMAA']['mean_ms']:.6f} → "
                 f"{selected['SMAA']['mean_ms']:.6f} ms ({selected['SMAA']['percent_vs_native']:+.3f}%).")
lines+=['',
    '전체 SMAA에는 공간 처리와 공통 부대 비용이 남으므로 resolve 절감률을 전체 AA 절감률로 표현하지 않는다. ',
    '모두 선택하는 All control은 추가 대비 판단을 포함한 실험 경로의 오버헤드를 보여준다. ',
    '선택률만으로 속도를 예측하지 않고, 장면별 측정치와 반복 분산을 함께 해석한다.',
    'Bistro 첫 native run의 spatial 시간은 후속 run보다 낮았다. 모든 run을 포함해 보고했으며 ',
    '관측된 시간 차이를 통계적 유의성이나 모든 GPU에서의 개선으로 일반화하지 않는다.','',
    '후속 검토에서는 global jitter를 유지한 픽셀에서 temporal 결합을 생략하는 영향과 ',
    '대비 판정 자체의 프레임별 변화 영향을 분리해야 한다. 현재 데이터만으로 두 원인의 기여도를 단정하지 않는다.','']
(dest/'report.md').write_text('\n'.join(line.rstrip() for line in lines),encoding='utf-8')
print('PASS: publish complete two-scene contrast gate')
