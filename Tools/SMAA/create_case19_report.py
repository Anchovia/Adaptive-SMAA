"""Create Korean case19 tables from validated paired measurements."""
import argparse, csv, json, math, statistics
from pathlib import Path
from verify_case19_spatial import MODES, CASE18, LAZY, modes_for_receipt

NAMES=dict(zip(MODES,['④ O-T2X-R','⑰ 색 혼합 기준','⑱ O2+O3','⑲ 후보: RGBA8','⑲ 후보: Gather','⑲ 후보: RGBA8+Gather']))
NAMES[LAZY]='⑲ 재검증: 이전 edge 조회 지연'
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def value(a,m,k):return a['absolute'][m][k]['mean']
def paired(a,m,c,k):return a['paired'][f'{m} vs {c}'][k]['percent']
def percent(a,m,c,k):return '—' if m==c else f"{paired(a,m,c,k)['mean']:+.2f}%"
def interval(p):return ' / '.join(f'{v:+.3f}%' for v in p['ci95'])
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--selected',required=True,choices=[CASE18,LAZY]);ap.add_argument('--out',required=True);x=ap.parse_args()
    docs=Path('Docs/Case19-AA-Overhead');bench=read(docs/'benchmark.json');profile=read(docs/'profile.json')
    modes=modes_for_receipt(bench['bistro']['receipt'])
    for scene in ('bistro','minecraft'):
        assert bench[scene]['validation']==profile[scene]['validation']=='PASS'
        assert read(docs/f'verify-lazy-{scene}.json')['validation']=='PASS'
        assert bench[scene]['repeats']==6 and profile[scene]['repeats']==3
    reviewed=read(docs/'research-ledger.json');selected=x.selected
    if selected==LAZY and any(paired(a,LAZY,CASE18,'SMAA')['ci95'][1]>=0 for a in bench.values()):
        raise ValueError('Cannot adopt a candidate without consistent paired AA benefit in both scenes')
    rows=[];performance=[]
    for scene,a in bench.items():
        for m in modes:
            rows.append([scene,NAMES[m],f"{value(a,m,'SMAA'):.6f}",percent(a,m,MODES[0],'SMAA'),
                f"{value(a,m,'SF_Spatial'):.6f}",f"{value(a,m,'SR_Resolve'):.6f}",percent(a,m,MODES[0],'SR_Resolve'),percent(a,m,CASE18,'SMAA')])
            for metric in a['absolute'][m]:
                v=a['absolute'][m][metric]
                performance.append(dict(scene=scene,mode=m,metric=metric,mean_ms=v['mean'],median_ms=v['median'],p95_ms=v['p95'],p99_ms=v['p99'],
                    run_mean_sd_ms=statistics.stdev(v['runs']),vs4_percent='' if m==MODES[0] else paired(a,m,MODES[0],metric)['mean'],
                    vs18_percent='' if m==CASE18 else paired(a,m,CASE18,metric)['mean']))
    with (docs/'performance.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=performance[0].keys());writer.writeheader();writer.writerows(performance)
    detailed=[]
    for scene,a in bench.items():
        for m in modes[3:]:
            p=paired(a,m,CASE18,'SMAA');sp=paired(a,m,CASE18,'SF_Spatial');wf=paired(a,m,CASE18,'WholeFrame')
            detailed.append([scene,NAMES[m],f"{p['mean']:+.3f}%",interval(p),f"{sp['mean']:+.3f}%",interval(sp),f"{wf['mean']:+.3f}%",interval(wf)])
    prof=[]
    edge_deltas=[]
    for scene,a in profile.items():
        for m in modes:
            prof.append([scene,NAMES[m]]+[f'{value(a,m,k):.6f}' for k in ['SP_Prepare','SP_Edge','SP_Weights','SP_Neighborhood','SR_Resolve']])
        edge_deltas.append(f"- {scene}: 조회 지연 후보의 edge가 ⑱보다 {value(a,LAZY,'SP_Edge')-value(a,CASE18,'SP_Edge'):+.6f} ms 증가했다.")
    selected_summary=[]
    for scene,a in bench.items():
        if selected==CASE18:
            selected_summary.append(f"- {scene}: 유지한 ⑱ AA {value(a,CASE18,'SMAA'):.6f} ms, temporal {value(a,CASE18,'SR_Resolve'):.6f} ms; ④ 대비 AA {percent(a,CASE18,MODES[0],'SMAA')}.")
        else:
            selected_summary.append(f"- {scene}: {NAMES[selected]}의 ⑱ 대비 AA {percent(a,selected,CASE18,'SMAA')}, spatial {percent(a,selected,CASE18,'SF_Spatial')}, WholeFrame {percent(a,selected,CASE18,'WholeFrame')}; ④ 대비 AA {percent(a,selected,MODES[0],'SMAA')}.")
    screening=[]
    for scene,a in read(docs/'screening-performance.json').items():
        for m in MODES[3:]:
            p=paired(a,m,CASE18,'SMAA')
            screening.append([scene,NAMES[m],f"{value(a,CASE18,'SMAA'):.6f}",f"{value(a,m,'SMAA'):.6f}",f"{p['mean']:+.3f}%",interval(p)])
    text=f'''# ⑲ AA 오버헤드 추가 최적화 결과 (2026-10-19)

최종 유지/선정 구성은 **{NAMES[selected]}** (`{selected}`)다. {('⑲ 시험 구성을 채택하지 않고 ⑱를 유지한다.' if selected==CASE18 else '⑲ 후보의 이득은 이번 GPU·두 장면의 측정 범위에 한정한다.')} 기존 ⑰·⑱와 final 8-case의 기본 설정은 변경하지 않았다. 이 결과는 이번 네 구성의 비교이며, ⑱가 최적화 한계라는 증거가 아니다.

**후속 감사 정정:** 기존 `Docs/Edge-History-Color-Blend-Optimization/method-ko.md`의 제외 기록에는 이전 edge의 지연 조회를 선행 조회로 바꿔 이미 채택했다고 명시돼 있다. 따라서 ⑲의 `LazyPreviousEdge`는 새로운 유망 기법이 아니라 ⑱ 조건에서 과거 선택을 재확인한 실험으로 분류한다. 이 기록을 최초 후보 선정에 충분히 반영하지 못했다. 아래 원시 수치·RGB hash는 그대로 보존하며 분류와 해석만 정정했다.

{chr(10).join(selected_summary)}

⑲는 사용자가 요청한 독립 브랜치 `experiment/case19-aa-overhead-optimization`이며 의존성은 검증된 ⑱ commit `d5d3a40903da8a41e52ea91eeab2b562faa417b3`다. 다른 미완료 연구를 섞지 않았다. ⑱는 ⑰에 `OPT-NeighborhoodNoDepth+PresentHistory`를 켠 구성이다. ⑲의 모든 새 옵션도 기본 Off다.

## AA·temporal 시간과 ④/⑱ 대비 변화

아래는 후속 후보를 각 장면의 같은 benchmark process에 ④·⑰·⑱와 함께 넣은 결과다. ms는 여섯 run mean의 평균, 변화율은 대응 반복의 control로 나눈 비율의 평균이다. 과거 보고서의 절대 시간을 분모로 쓰지 않았다. 음수는 시간 감소다.

{table(['장면','설정','AA ms','AA vs ④','공간 처리 ms','temporal resolve ms','temporal vs ④','AA vs ⑱'],rows)}

AA는 `SMAA` GPU scope, 공간 처리는 `SF_Spatial`, temporal은 `SR_Resolve`다. camera velocity(`SR_CameraVelocity`)는 별도이며 AA에 포함된다. prepare/edge/weights/neighborhood와 GPU timestamp 범위의 경계 차이 때문에 세부 시간의 합이 AA와 완벽히 같을 필요는 없다. 전체 GPU 프레임과 wall frame은 별도 지표다. 전체 AA 절감률을 FPS 증가율로 읽지 않는다.

## 후속 후보의 ⑱ 대비 반복 변동

{table(['장면','후보','AA 변화','AA paired 95% 하한 / 상한','공간 변화','공간 paired 95% 하한 / 상한','WholeFrame 변화','WholeFrame paired 95% 하한 / 상한'],detailed)}

구간은 대응하는 6개 반복의 Student-t(df=5) 95% 구간이며 다중 비교 보정을 하지 않았다. 구간에 0이 포함되면 이번 반복에서 일관된 개선으로 확정하지 않는다. 여러 후보를 조사한 결과이므로 작은 차이를 보편적인 우위로 확대하지 않는다. p95/p99·run mean SD·wall 시간은 `performance.csv` 및 검증된 전체 `benchmark.json`에 있다.

## 첫 세 후보: 미채택 결과

아래는 앞선 별도 binary/process의 6-mode screening이다. 각 행의 ⑱는 해당 screening process의 control이다. 위 후속 행렬의 절대값과 합쳐 변화율을 계산하지 않았다.

{table(['장면','후보','같은 실행 ⑱ AA ms','후보 AA ms','AA vs ⑱','paired 95% 하한 / 상한'],screening)}

RGBA8·Gather·결합은 두 장면에서 추가 이득을 확정하지 못해 미채택했다. 관련 RGB 검증·GPU fixture·raw report를 보존했으며 실패 결과를 숨기거나 품질 문제로 분류하지 않았다.

## 변경 원리와 자료 검토

논문·학회 발표·공식 문서·제조사 가이드·공개 구현 **{reviewed['reviewed_count']}개**의 관련 본문/소스 구간을 검토했다. 100편 논문 전체를 정독했다는 뜻은 아니다. 중복·접근 실패·충분한 본문이 없는 자료는 완료 수에서 제외했다. 링크·검토 범위·구체적 적용 판단은 `sources-ko.md`와 `research-ledger.json`에 있다.

- **RGBA8**: [SMAA 저자 공식 구현](https://raw.githubusercontent.com/iryoku/smaa/master/Demo/DX10/Code/SMAA.cpp)은 NVIDIA에서 RGBA8 edge target을 선택한다. 이 저장소의 wrapper는 adapterDesc를 전달하지 않아 ④/⑰/⑱에서 RG8을 사용한다. ⑲ 옵션은 raw-edge ping-pong target의 RG 의미를 유지하면서 RGBA8로 바꾼다. 더 넓은 형식이 빠르다는 보장은 없으므로 실측으로 판단했다.
- **Gather**: [Microsoft Gather 계약](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/gather4--sm5---asm-)과 [NVIDIA 가이드](https://developer.nvidia.com/blog/advanced-api-performance-shaders/)를 참고해 첫 luma current/left/top 세 point read를 단일 Gather로 묶었다. quarter-texel 좌표와 `.yxz` swizzle로 같은 texel을 선택하고 기존 threshold/LCA 수식을 유지한다. 최적화 DXBC는 point sample 7개에서 Gather 1개+point sample 4개로 변했다. 기존 velocity sample_l 1개와 previous-edge ld 1개는 그대로다. 명령 수 변화가 GPU 시간 감소를 보장하지는 않는다.
- **이전 edge 조회 지연**: current raw edge가 있으면 `current OR previous`가 이미 true다. current가 없는 픽셀에서만 기존 velocity sample_l와 previous-edge ld를 실행하도록 순서를 바꿨다. previous-only 픽셀도 계속 선택한다. [HLSL 논리식은 단락 평가를 하지 않으므로](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators) 명시적인 branch를 쓰고, 생성된 DXBC에서 두 조회가 분기 안에 있는지 확인했다. `lazy-previous-method-ko.md`에 통제 범위와 가정을 기록했다.
- **통제 범위**: Original 공간 SMAA Ultra, camera/depth 재투영, current∪reprojected previous raw-edge 선택, paired pattern Off, Catmull-Rom 5-fetch RGB, fixed 0.8 weight, encoded-gamma2 blend와 resolved RGB feedback은 유지했다. Adaptive/object-motion/threshold/search length/precision/quality preset은 바꾸지 않았다. Intel 공식 TSCMAA 완전 포팅으로 표현하지 않는다.

stencil/edge/weight clear 생략은 sparse write의 0 보장을 깨뜨리므로 적용하지 않았다. earlydepthstencil 강제는 discard와 stencil 기록 순서를 바꿀 수 있다. compute 전환과 품질 설정 변경은 이번 RGB 보존 최적화에 섞지 않았다. 추가 검토한 [shader-specified stencil reference](https://learn.microsoft.com/en-us/windows/win32/direct3d11/shader-specified-stencil-reference-value)는 optional D3D11.3 기능이다. 기존 `Docs/Edge-History-Color-Blend-Cleanup/audit-ko.md`에는 실험 장치 미지원으로 기록돼 있으므로 현재 바로 적용 가능한 미시험 후보로 분류하지 않는다. ⑲에서 새 support probe를 실행했다는 뜻도 아니다. [AMD/NVIDIA 발표 p46](https://gpuopen.com/download/Practical_DX12_Programming_Model_and_Hardware_Capabilities.pdf)은 depth output에 준하는 비용을 명시한다.

## 별도 pass profile: 남아 있는 공간 비용

아래는 추가 pass timer On인 별도 process의 2,400프레임×3회 진단이다. 본 benchmark와 절대 시간을 섞거나 이 표로 최종 속도 개선율을 계산하지 않는다.

{table(['장면','설정','prepare ms','edge ms','weights ms','neighborhood ms','resolve ms'],prof)}

{chr(10).join(edge_deltas)}

조회 지연 후보의 추가 비용은 주로 edge 단계에서 관찰됐다. 분기로 인한 divergence나 기존 읽기의 latency overlap 감소가 가능한 설명이지만, 이를 특정한 하드웨어 원인으로 확정하지 않는다.

④는 Standard O-T2X-R의 paired sample pattern On이고 선택형은 pattern Off다. 공간 edge population도 달라질 수 있으므로 ④와의 edge/weight 차이 전체를 선택 mask 비용 하나로 단정하지 않는다. ⑱와 ⑲ 사이의 비교는 이 의미를 고정한다.

소스상의 fetch 수는 실제 GPU 시간과 같은 지표가 아니다. RGBA8은 저장 폭이 넓고 Gather는 texture 요청 형태·좌표 산술과 명령 스케줄을 바꾼다. 이들이 이번 차이를 만든 정확한 하드웨어 원인인지는 cache/throughput/occupancy counter를 계측하지 않아 확정하지 않는다. 별도 profile은 비용이 증가하거나 감소한 pass를 찾는 근거까지만 제공한다. 이번 후보가 실패해도 다른 출력 보존 최적화가 불가능하다는 결론은 아니다.

## 출력·구현 검증

- 첫 matrix는 Bistro/Minecraft 각각 6 mode×240프레임, 총 2,880 PNG, 후속 matrix는 각각 4 mode×240프레임, 총 1,920 PNG의 연속 index·1920×1061 RGB·jitter phase·실제 target format·report SHA를 검증했다. 모든 선택형 후보는 같은 실행 ⑱, 보존된 이전 ⑱와 원래 ⑰의 decoded RGB hash에 mismatch 0이다. ④도 원래 ④ hash와 mismatch 0이다.
- GPU 수치 probe: 30개 fixture, 19,730,050 pixel에서 current/left/top point↔Gather와 binary RG edge의 RG8↔RGBA8 보간 결과에 mismatch 0. 1×1, odd size, 1920×1061을 포함한다. fixture 통과를 모든 장면의 영구 동등성 증명으로 표현하지 않는다.
- shader audit: 11개 기존 entry×2해상도에서 옵션 Off의 최적화 DXBC가 ⑱ 소스와 byte 동일하다. debug metadata를 제외한 FXC /O3 /Ges 결과이며 runtime debug blob 전체 동일성을 주장하지 않는다.
- 타이밍 분석기의 9개 검사는 누락·중복·표본 수·실제 format·report 변조·행렬 종류를 검증했고, 기존 color-blend 도구의 18개 검사도 통과했다.
- 화면 f130 및 thin-chair/thin-seam 이동 f124~133, 전환 f178~183, 정지 f230 비교를 직접 확인했다. ⑰/⑱의 얇은 구조 단절·벽 경계 약화는 그대로다. 품질 개선이나 새 CGVQM 결과를 주장하지 않는다. 인증 범위는 화면 RGB이며 중간 alpha/전체 RGBA가 아니다.
- `verify-bistro.json`, `verify-minecraft.json`, `verify-lazy-bistro.json`, `verify-lazy-minecraft.json`, `gpu-probe.json`, `shader-audit.json`, `lazy-shader-audit.json`, `smoke.json`, `lazy-smoke.json`에 원자료 경로·hash·검증 결과를 보존했다. 비교 PNG와 GIF는 별도 inspection 폴더에 있으며 GIF는 palette viewing aid다. GIF 재생을 직접 확인했다고 주장하지 않는다.

## 실행 조건과 재현

RTX 3060 Ti / driver 610.88, Ryzen 5 5600, DX11 Release x64, 1920×1061 hidden/windowed, VSync Off, fixed 60 Hz. still60/move120/still60의 동일 240-frame loop를 사용했다. benchmark는 30초 precondition, mode당 300 warm-up, 4,800 measurement×6, 정/역 순서 교차다. PNG·후보 readback·추가 진단 query·세부 pass timer는 Off이고 필요한 GPU timestamps만 켰다.

명령마다 기존 CMAA2 0개와 GPU P8/util<20% 및 경쟁 GPU 앱을 확인한 뒤 독립 process를 실행했다. 1,200초 wall timeout과 종료 뒤 잔류 0개를 clean runner로 검사했다. 같은 binary smoke를 통과한 뒤에만 benchmark를 실행했다. exe SHA-256은 `{bench['bistro']['receipt']['executable_sha256']}`다. 장면별 head/소스 SHA·실행 전 GPU 상태·시각·전체 report SHA는 각 receipt에 있다. report header/설정과 mode×run×metric×sample 수를 분석기가 재검증했다.

```powershell
Tools/SMAA/run_case19_spatial.ps1 -Variant Lazy -Phase Capture -Scene bistro -Label c19-lazy-a
Tools/SMAA/run_case19_spatial.ps1 -Variant Lazy -Phase Smoke -Scene bistro -Label c19-lazy-smoke-a
Tools/SMAA/run_case19_spatial.ps1 -Variant Lazy -Phase Benchmark -Scene bistro -Label c19-lazy-bench-a
Tools/SMAA/run_case19_spatial.ps1 -Variant Lazy -Phase Profile -Scene bistro -Label c19-lazy-profile-a
```

각 명령은 독립 실행이며 이전 process의 종료·GPU idle 확인 후 다음 명령을 시작한다. Minecraft는 Scene만 바꾼다. raw PNG와 현재 실행 파일·컴파일 cache는 ignored 경로에 남겼다. 초기 screening exe는 후속 빌드로 덮어썼으며 그 SHA·source commit을 기록했다. 저장소에는 raw CSV 사본·receipt·원자료 위치·hash와 분석 결과를 보존한다.
'''
    Path(x.out).write_text(text,encoding='utf-8')
    source_lines=[f"# ⑲ 자료 검토 목록: {reviewed['reviewed_count']}개",'',
        '관련 기술 본문·소스 구간을 검토한 자료 목록이다. 전체 논문 정독 개수가 아니다. 실패·중복·본문 부족 자료는 개수에서 제외했다.','']
    for item in reviewed['reviewed']:
        source_lines.extend([f"{item['id']}. [{item['title']}]({item['url']}) — {item['takeaway']}",''])
    (docs/'sources-ko.md').write_text('\n'.join(source_lines),encoding='utf-8')
    print(f'PASS: report, CSV and {reviewed["reviewed_count"]}-source bibliography')
if __name__=='__main__':main()
