"""Summarize paired measurements without promoting spatial proxies to quality truth."""
import json
from pathlib import Path
from analyze_edge_persistence_gpu import ROOT,DOC,A,B,C
LABEL={A:'기존 ⑥: 현재 edge',B:'새 구현: 직전 raw edge 유지',C:'원본 ④: SMAA T2X-R'}
def read(name):return json.loads((DOC/name).read_text(encoding='utf8'))
def cgvqm_section():
    if not all((DOC/f'{s}-cgvqm.json').exists() for s in ['bistro','minecraft']):
        return ['','CGVQM은 아직 두 장면 모두의 결과가 완성되지 않았다. RGB MAE/PSNR과 직접 프레임 검사를 별도로 참고한다.','']
    out=['','### CGVQM-2 추가 품질 측정','',
         '2026-10-01 후속 평가. 새 GPU 구현은 이동 f60~179, 정지 전환 f160~219를 두 장면에서 새로 평가했다(4회). 기존 ⑥과 원본 ④의 8개 점수는 현재 캡처와 참조의 RGB stream hash가 이전 평가 입력과 정확히 같음을 확인한 뒤 재사용했다. 대조군을 새로 평가했다고 표현하지 않는다.','',
         'IntelLabs/CGVQM commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`, model 2, CUDA, patch scale 4, mean pooling, 60 fps. FFV1 변환 후 RGB 불일치 0. 점수는 높을수록 좋지만, 고해상도 **공간** 참조에 대한 보조 지표이며 절대 고스팅 점수가 아니다.','',
         '| 장면 / 구간 | 기존 ⑥ | 새 GPU | 원본 ④ | 새−기존 ⑥ | 새−원본 ④ |',
         '|---|---:|---:|---:|---:|---:|']
    for scene in ['bistro','minecraft']:
        d=read(f'{scene}-cgvqm.json');assert d['validation']=='PASS'
        for w,label in [('moving','이동 f60~179'),('transition','정지 전환 f160~219')]:
            r=d['results'][w];s=r['scores']
            out.append(f"| {scene} / {label} | {s[A]:.6f} | {s[B]:.6f} | {s[C]:.6f} | {s[B]-s[A]:+.6f} | {s[B]-s[C]:+.6f} |")
    out+=['','차이는 점수 단위이며 품질 향상률(%)이 아니다. 정지 전환 CGVQM 구간은 위 MAE 표의 짧은 전환 구간(f178~185)과 다르다. 전체 평균 점수와 무관하게 Minecraft f132/f135/f137의 남은 선 단절을 품질 실패로 기록한다. 두 selective 방식의 Pattern Off와 원본의 Pattern On 차이도 포함되어 있다.','',
          '평가 명령, 입력/참조 hash, 재사용 기록과 공식 소스 hash는 `bistro-cgvqm.json`, `minecraft-cgvqm.json`에 보존했다. 재현 도구는 `Tools/SMAA/evaluate_edge_persistence_cgvqm.py`다.','']
    return out

def main():
    audit=read('source-audit.json');out=[]
    out += ['# 직전 raw edge 유지: GPU 구현·성능·품질 결과','',
            '브랜치: `experiment/spatial-edge-persistence-depth`. 수정된 ⑥ 기준선 `304f749`에서 직접 분기했다.',
            f"GPU 구현 커밋: `{audit['renderer_commit']}`. 실행 파일 SHA-256: `{audit['executable_sha256']}`.",'',
            '현재 edge와 재투영한 직전 **raw edge**의 합집합에 원본 temporal 계산을 수행했다. 이전 합집합을 재귀적으로 유지하지 않는다. 추가 draw/dispatch나 전체 색상 복사 패스는 없다. 기존 공간 3차 패스에서 선택 영역을 전용 depth에 기록하고, temporal 패스는 early depth test로 선택 영역에서만 실행한다. 두 selective 구현은 Pattern Off, 원본 ④는 paired pattern On이다.','',
            '## 성능','',
            'RTX 3060 Ti, DX11 Release x64, SMAA Ultra, 1920×1061, hidden, VSync Off. 장면별 동일 실행의 세 모드를 순서 교차하여 300 warm-up + 4,800프레임 × 6회 측정했다. PNG·GPU readback·진단 query를 모두 끈 별도 clean process 결과다. 음수는 시간 감소, 양수는 시간 증가다.','',
            '| 장면 | 방식 | 전체 AA ms | 원본 ④ 대비 | spatial+선택 ms | camera ms | temporal ms | temporal 원본 ④ 대비 |',
            '|---|---|---:|---:|---:|---:|---:|---:|']
    perf={};quality={}
    for scene in ['bistro','minecraft']:
        p=read(f'{scene}-benchmark.json');assert p['validation']=='PASS'
        assert p['receipt']['executable_sha256'].lower()==audit['executable_sha256']
        perf[scene]=p
        v=p['modes'];base=v[C]
        for m in [A,B,C]:
            x=v[m];aa=x['SMAA']['mean_ms'];tem=x['SR_Resolve']['mean_ms']
            out += [f"| {scene} | {LABEL[m]} | {aa:.6f} | {(aa/base['SMAA']['mean_ms']-1)*100:+.2f}% | {x['SF_Spatial']['mean_ms']:.6f} | {x['SR_CameraVelocity']['mean_ms']:.6f} | {tem:.6f} | {(tem/base['SR_Resolve']['mean_ms']-1)*100:+.2f}% |"]
    out += ['','### 新 구현과 기존 ⑥의 차이','',
            '| 장면 | 전체 AA 증가 | spatial+선택 증가 | temporal 증가 | spatial 구간 증가 / 전체 AA 증가 |',
            '|---|---:|---:|---:|---:|']
    for scene,p in perf.items():
        a=p['modes'][A];b=p['modes'][B]
        da=b['SMAA']['mean_ms']-a['SMAA']['mean_ms'];ds=b['SF_Spatial']['mean_ms']-a['SF_Spatial']['mean_ms'];dt=b['SR_Resolve']['mean_ms']-a['SR_Resolve']['mean_ms']
        out += [f"| {scene} | {da:+.6f} ms ({da/a['SMAA']['mean_ms']*100:+.2f}%) | {ds:+.6f} ms | {dt:+.6f} ms | {ds/da*100:.1f}% |"]
    out += ['','공간 구간 증가에는 두 edge texture 접근, 현재 point velocity 접근, 재투영·합집합 계산, SV_Depth 기록 및 그에 따른 GPU 실행 특성이 함께 포함된다. 이를 순수 데이터 전송 시간이라고 부르지 않는다. 정확히 어떤 항목이 지배적인지는 별도 profiler/ablation이 필요하다.','',
            '각 run의 mean/median/p95/p99/stddev, wall frame, WholeFrame, 1% low에 대응하는 FPS와 paired 변화율은 장면별 `*-benchmark.json`에 보존했다. 전체 AA만 보고 전체 게임 FPS 향상으로 확대하지 않는다.','',
            '## 품질 및 직접 프레임 검사','',
            'Minecraft f131/f134의 일부 선 단절은 실제 GPU 출력에서 복원됐다. f132/f135처럼 이미 현재 edge로 처리하던 위치는 동일하고, f137에서도 단절이 남는다. 이동 중 선의 출현/소멸 전체가 해결된 것은 아니다. 정지 후 f181부터 추가 후보가 0이 되어 기존 ⑥과 같아진다. Bistro 의자/창문에서도 전반적 품질 개선을 확정할 만큼 차이가 크지는 않다.','',
            '두 장면의 원본 full PNG 및 세 ROI의 6연속 이동·정지전환·정지 프레임을 직접 열어 확인했다. Minecraft는 f136~141까지 추가 검사했다. 구체적 위치와 관찰은 [직접 검사 기록](visual-inspection-ko.md)에 있다.','',
            '아래 MAE는 RGB 0~255 단위의 **공간 고해상도 참조와의 오차**다. 절대 temporal/고스팅 정답이 아니며, 이 표로 원본 ④보다 체감 품질이 좋다고 결론내리지 않는다.','',
            '| 장면 / 구간 | 기존 ⑥ MAE | 새 GPU MAE | 원본 ④ MAE |',
            '|---|---:|---:|---:|']
    for scene in ['bistro','minecraft']:
        q=read(f'{scene}-quality.json');assert q['validation']=='PASS';quality[scene]=q
        assert q['receipt']['executable_sha256'].lower()==audit['executable_sha256']
        for window,label in [('moving','이동 f60~179'),('transition','정지 전환 f178~185'),('late_still','정지 f190~239')]:
            x=q['summary'][window]['full']
            out += [f"| {scene} / {label} | {x[A]['rgb_mae']:.6f} | {x[B]['rgb_mae']:.6f} | {x[C]['rgb_mae']:.6f} |"]
    out += ['','RGB MAE/PSNR, ROI edge strength, frame change 및 reference-delta residual은 장면별 `*-quality.json`에 있다. 수치의 방향이 엇갈리므로 원본 프레임의 구조 보존 문제를 우선한다.']
    out += cgvqm_section()
    out += ['',
            '### 선택 영역','',
            '이동 구간 중 진단한 23프레임의 평균이다. 전체 120 이동 프레임의 전수 통계나 GPU 시간 변화율이 아니다.','',
            '| 장면 | 기존 ⑥ / 전체 픽셀 | 새 GPU / 전체 픽셀 | 선택 픽셀 상대 증가 |',
            '|---|---:|---:|---:|']
    for scene,q in quality.items():
        trace=[x for x in q['traces'] if 60<=x['frame']<=179];assert len(trace)==23
        a=sum(x['current_count'] for x in trace)/23;b=sum(x['union_count'] for x in trace)/23
        out += [f'| {scene} | {100*a/(1920*1061):.3f}% | {100*b/(1920*1061):.3f}% | {(b/a-1)*100:+.2f}% |']
    out += ['','## 검증 범위','',
            '- 기존 ④·⑥ 960프레임: 수정 전 기준선 RGB hash와 모두 일치.',
            '- 현재 edge만 depth로 전달하는 대조 모드 480프레임: 기존 ⑥과 모두 일치.',
            '- 새 구현 반복 480프레임: 진단 On/Off 출력 모두 일치.',
            '- 258개 진단 draw: 실제 temporal coverage와 occlusion sample 수 일치. 현재 edge 보존, 비선택=현재 spatial, 기존 선택 픽셀의 출력 보존 확인.',
            '- 76개 GPU/CPU union 비교: texel 경계에서 0.01 이상 떨어진 영역의 mask mismatch 0, native 혼합 RGB 최대 오차 1 level. 경계 인접 mask 차이는 Bistro 18 pixel-frame, Minecraft 21 pixel-frame으로 별도 기록했다. 모든 픽셀이 CPU와 bit-exact하다고 주장하지 않는다.',
            '- 기존 shader 14 variant DXBC 동일, 새 shader 4 variant FXC 통과, Release 빌드 및 두 장면 Test/Smoke/Benchmark PASS.',
            '- 첫 프레임 reset과 반복 capture는 확인했다. 별도 resize/teleport fixture, object motion 및 이전 depth 기반 disocclusion rejection은 이번 결과의 검증 범위가 아니다.','',
            '## 판단','',
            '한 프레임 전 raw edge를 추가하면 현재 edge 판정에서 누락된 일부 선을 복원할 수 있다. 그러나 이번 구현은 기존 ⑥보다 전체 AA 시간이 늘고, 원본 ④ 대비 전체 AA 시간 우위도 얻지 못했다. 남은 선 소실·단절까지 고려하면 기본 구현으로 채택하거나 속도·품질 동시 개선을 주장할 단계는 아니다. 이 결과는 해당 실행 구조와 두 장면의 실험 결과이며, 아이디어 자체가 모든 구현에서 불가능하다는 결론은 아니다.','',
            '## GPU GIF / 원본 비교 자료','',
            '열 순서: **기존 ⑥ / 직전 raw edge 유지 GPU / 원본 ④ / 고해상도 공간 참조**. selective 두 방식은 Pattern Off, 원본 ④는 Pattern On이다. 10 fps(1/6 속도), 원본 색상, nearest 확대. GIF 색상 양자화와 별개로 무손실 WebP 및 PNG sheet를 함께 보존했다.','']
    for m in read('media.json'):
        def link(p):return Path(p).as_posix()
        out += [f"- {m['name']}: [GIF]({link(m['gif'])}) · [무손실 WebP]({link(m['lossless'])}) · [6연속 PNG]({link(m['sheet'])})"]
    out += ['','재현: `Tools/SMAA/run_edge_persistence.ps1`, `analyze_edge_persistence_gpu.py`, `create_edge_persistence_gpu_media.py`. 정확한 명령·시각·binary/report hash는 장면별 JSON에 있다. 알고리즘·공식 API 근거는 [method.md](method.md)에 정리했다.','']
    (DOC/'results-ko.md').write_text('\n'.join(out).replace('### 新 구현','### 새 구현'),encoding='utf8')
    print('Report written',flush=True)
if __name__=='__main__':main()
