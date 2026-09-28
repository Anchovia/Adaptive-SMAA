"""Summarize validated capture provenance and paired temporal-only control timings."""
import csv,json,statistics
from pathlib import Path
from analyze_temporal_only import sha
R=Path(__file__).resolve().parents[2];D=R/'Docs/Temporal-Only-Control'
def main():
    audit=json.loads((D/'source-audit.json').read_text());assert audit['validation']=='PASS'
    qs={s:json.loads((D/f'{s}-capture.json').read_text()) for s in ['bistro','minecraft']}
    receipts=json.loads((R/'tmp/temporal-only-runs.json').read_text(encoding='utf-8-sig'))
    perf={}
    for scene,q in qs.items():
        assert q['validation']=='PASS'
        assert q['receipt']['executable_sha256'].lower()==audit['executable_sha256']
        assert sha(Path(q['receipt']['report']))==q['receipt']['report_sha256'].lower()
        selected=[r for r in receipts if r['scene']==scene and r['phase']=='Benchmark'];assert len(selected)==1;rc=selected[0]
        smokes=[r for r in receipts if r['scene']==scene and r['phase']=='Smoke'];assert len(smokes)==1
        for r in [rc,smokes[0]]:
            p=Path(r['report']);assert sha(p)==r['report_sha256'].lower()
            assert r['executable_sha256'].lower()==audit['executable_sha256']
            assert 'Aggregate: PASS' in p.read_text(encoding='utf-8-sig') and 'FAIL' not in p.read_text(encoding='utf-8-sig')
        text=Path(rc['report']).read_text(encoding='utf-8-sig')
        rows=[[x.strip() for x in r] for r in csv.reader(text.splitlines()) if r and r[0].strip()=='timing'];assert len(rows)==12
        modes={}
        for m in ['O-1X','O-T2X-R','ABL-TemporalOnly-R']:
            group=[r for r in rows if r[1]==m];assert sorted(int(r[2]) for r in group)==list(range(4))
            assert all(r[3]=='SMAA' and int(r[4])==4800 for r in group)
            means=[float(r[5]) for r in group];assert min(means)>0
            modes[m]=dict(mean_ms=statistics.mean(means),run_mean_std_ms=statistics.stdev(means),runs=group)
        perf[scene]=dict(receipt=rc,smoke=smokes[0],modes=modes,
            temporal_only_vs_spatial_t2xr_percent=100*(modes['ABL-TemporalOnly-R']['mean_ms']/modes['O-T2X-R']['mean_ms']-1))
    (D/'performance.json').write_text(json.dumps(dict(validation='PASS',scenes=perf),indent=2)+'\n',encoding='utf-8')
    lines=['# Temporal-only 기준 구성 구현·검증 결과','',
        '**합의한 6개 구성 중 ③ Spatial 보정 없는 전체 화면 temporal control을 독립 구현했다.**',
        '⑤·⑥ edge-selective 구현이나 지터 보정 실험은 이 브랜치에 포함하지 않는다.','',
        '## 브랜치 및 구현 범위','',
        '`experiment/temporal-only-control`은 검증된 공통 기준 `e14f122`에서 직접 분기했다.',
        '구현 커밋: `'+audit['implementation_commit']+'`. 원본 공간/resolve shader와 원본 go/reproject 함수는 동일하다.',
        '원본 재투영·결합 함수를 그대로 사용하면서 spatial 3패스 대신 RGB 보존 및 velocity-alpha 준비 draw를 실행한다.',
        '이 준비 draw는 공간 AA가 아니며 측정 시간에 포함된다. Camera velocity 생성 비용도 포함한다.',
        'Spatial 보정을 제외하므로 이웃 기반 velocity 보정도 제외되며, 현재 위치 velocity로 alpha를 만든다.',
        '전체 화면 T2X projection jitter, point resolve sampling, 가변 weight 0..0.5, 현재 프레임형 history, 첫 프레임 seed는 유지한다.',
        '원본 SMAA T2X-R 전체 재현이 아니라 공간 보정의 효과를 분리하기 위한 진단 구성이다.',
        'R은 camera/depth reprojection이며 object motion 지원을 의미하지 않는다.','',
        '## 출력·입력 검증','',
        'DX11, Ultra, 1920×1061, fixed 60 Hz, 60정지/120이동/60정지의 동일 240-frame 경로다.',
        '장면마다 6개 sequence: AA-Off, O-1X, O-T2X-R, Temporal-only, Temporal-only 반복, native zero-weight 참조.',
        '참조는 원본 neighborhood 함수에 0으로 채운 blend texture를 전달한다. 성능 결과에는 포함하지 않는다.','',
        '| 장면 | 기존 기준선 RGB 불일치 / 720 frame | 반복 불일치 / 240 | 참조 불일치 / 240 | 정지 Temporal-only RGB 종류 |',
        '|---|---:|---:|---:|---:|']
    for s,q in qs.items():lines.append(f"| {s} | {sum(q['baseline_mismatches'].values())} | {q['repeat_mismatches']} | {q['native_zero_weight_reference_mismatches']} | {q['static']['late_still']['ABL-TemporalOnly-R']['unique_rgb_frames']} |")
    lines+=['','각 장면 10개 프레임의 DDS에서 준비 RGB와 원본 입력 RGB의 불일치가 0이다.',
        '준비 RGBA는 원본 zero-weight 참조 및 반복 실행과 모두 정확히 일치했다.',
        'CPU velocity-alpha 수치 진단의 최대 차이는 8-bit alpha 1단계 이내였다. 실제 shader는 bilinear level-zero sampling을 사용하므로',
        '점 중심 CPU 계산과의 마지막 자리 차이는 원본 참조 RGBA 일치와 함께 기록한다.',
        'Frame 0의 최종 출력은 준비 RGB와 일치하여 first-frame seed를 확인했다.',
        '초기 20~59, 후기 200~239에서는 네 실제 비교 구성 모두 RGB 종류 수 1, 인접 변화 0이었다.',
        '이는 두 장면의 해당 정지 조건 결과이며 모든 장면·움직임에 대한 안정성 보장은 아니다.',
        '소스·CPU mode 상태 및 PNG/DDS 검증이며, 모든 draw를 GPU 디버거로 캡처한 검사는 아니다.','',
        '## 처리 시간','',
        'RTX 3060 Ti, hidden window, VSync Off. 캡처·분석과 분리한 clean process에서',
        '30초 precondition, mode별 300 warmup, 4800 frame×4회, 정/역 순서 교대로 측정했다.',
        '기존 SMAA 전체 scope만 사용한다. **Temporal resolve 단독 시간, WholeFrame, 표시 FPS가 아니다.**',
        '같은 실행 안에서 비교했으며 다른 브랜치의 과거 절대 시간과 직접 빼지 않는다.','',
        '| 장면 | SMAA 1X | 원본 SMAA T2X-R | Temporal-only | Temporal-only / 원본 변화 |',
        '|---|---:|---:|---:|---:|']
    for s,p in perf.items():
        m=p['modes'];lines.append(f"| {s} | {m['O-1X']['mean_ms']:.6f} ms | {m['O-T2X-R']['mean_ms']:.6f} ms | {m['ABL-TemporalOnly-R']['mean_ms']:.6f} ms | {p['temporal_only_vs_spatial_t2xr_percent']:+.2f}% |")
    lines+=['','**Temporal-only는 공간 AA를 제거했으므로 낮은 시간 자체를 알고리즘 개선으로 해석하지 않는다.**',
        '정식 6개 구성 품질·속도 결론과 CGVQM 비교는 아직 아니다. 이 단계는 기준 구성의 기능 검증 및 공통 비용 확인이다.',
        '원본 수학을 바꾸지 않기 위해 단계별 timestamp를 이번 기준 구성에는 추가하지 않았다. 후속 6개 구성 비교에서',
        '동일한 별도 계측을 사용해야 resolve/입력 준비/edge 접근 비용을 분리할 수 있다.','',
        '## 검증 도중 도구 수정','',
        '첫 offline 분석은 DDS velocity가 legacy D3DFMT_G16R16F 형식이라 parser가 중단됐다.',
        'DXGI R16G16_FLOAT와 동일한 2채널 half 형식으로 명시적으로 지원한 뒤 원시 캡처 전체를 다시 분석했다.',
        '렌더링 코드나 shader를 바꾸거나 실패 검사를 생략하지 않았다. 유효 실행은 모두 clean exit 및 Aggregate PASS다.','',
        '## 다음 독립 항목','',
        '⑤ spatial 보정 없는 first-edge selective와 ⑥ spatial 3패스를 유지하는 first-edge selective를 각각 독립 브랜치에서 진행한다.',
        '원본 첫 edge RG만 사용하고, 선택되지 않은 픽셀의 temporal 직전 값과 최종 출력을 대응시켜 지터 변동 원인을 확인한다.',
        '현재 Temporal-only 정지 안정성은 selective의 안정성을 보장하지 않는다. Pattern-Off는 별도 ablation이다.',
        '전체 구성과 가정은 [method.md](method.md), 실행·검증 원자료 출처는 각 JSON에 기록했다.']
    (D/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({s:p['modes'] for s,p in perf.items()},indent=2),flush=True)
if __name__=='__main__':main()
