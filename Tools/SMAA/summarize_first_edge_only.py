"""Insert measured timing tables in the Korean report without hand-copying values."""
import json

from analyze_first_edge_only import D, FULL, DETECT, SEL


def main():
    scenes = ['bistro', 'minecraft']
    perf = {s:json.loads((D/f'{s}-benchmark-performance.json').read_text()) for s in scenes}
    assert all(p['validation']=='PASS' and p['repeats']==4 and p['frames_per_repeat']==4800 for p in perf.values())
    text = '''## 성능

RTX 3060 Ti / DX11 / 1920×1061 / Ultra / 숨김 창. 각 명령을 독립 프로세스로 실행했고
장면별 smoke 후 30초 precondition, 조건별 300프레임 warm-up, 4,800프레임×4회로 측정했다.
세 조건의 순서는 정방향/역방향으로 교차했다. PNG·DDS·RG8 저장과 이미지·마스크 readback은
껐다. 계측용 GPU timestamp query의 결과 읽기는 유지했다.
240프레임 카메라 경로를 20회 반복하므로 경로 끝에서 시작으로 되돌아가는 경계도 포함된다.
각 조건에 같은 경로를 사용했지만 하나의 연속 4,800프레임 이동 품질 시퀀스는 아니다.

전체 AA scope는 camera velocity + 선택적 edge 검출 + RGB/alpha 준비 + resolve와 주변 GPU
명령을 포함한다. 전체 렌더 프레임 시간이나 FPS가 아니다. 세부 timer 삽입의 영향이 있으므로
이전 브랜치에서 측정한 절대값과 직접 빼지 않는다. ④는 이번 실행의 timing matrix에 없으며,
이 표를 원본 공간 SMAA T2X-R보다 ⑤가 빠르다는 증거로 사용하지 않는다.

단위는 ms, 네 반복 평균이다.

| 장면 | 구성 | Camera velocity | Edge 검출 | 입력 준비 | Resolve | 전체 AA scope |
|---|---|---:|---:|---:|---:|---:|
'''
    names = {FULL:'③ 전체 화면 temporal', DETECT:'검출 + 전체 화면 temporal', SEL:'⑤ 검출 + edge temporal'}
    for scene in scenes:
        for mode in [FULL,DETECT,SEL]:
            mm=perf[scene]['metrics'][mode]
            values=[f"{mm[k]['mean_ms']:.6f}" if k in mm else '—' for k in ['FE_CameraVelocity','FE_EdgeDetection','FE_Prepare','FE_Resolve','SMAA']]
            text+=f"| {scene.title()} | {names[mode]} | "+' | '.join(values)+' |\n'
    text+='''
검출 비용과 선택 resolve의 효과를 구분하여 다음 차분으로 해석한다.

| 장면 | 검출 추가: 전체 scope 증가 | 같은 검출 조건에서 선택 resolve 변화 | 같은 검출 조건에서 전체 scope 변화 | ③ 대비 ⑤ 전체 scope 변화 |
|---|---:|---:|---:|---:|
'''
    for scene in scenes:
        cs=perf[scene]['contrasts']
        items=[cs['detect_minus_full']['SMAA'],cs['selective_minus_detect']['FE_Resolve'],
               cs['selective_minus_detect']['SMAA'],cs['selective_minus_full']['SMAA']]
        text+=f"| {scene.title()} | "+' | '.join(f"{x['delta_ms']:+.6f} ({x['percent']:+.2f}%)" for x in items)+' |\n'
    text+='''
4회 반복의 같은 검출 조건 resolve 변화율 범위:

'''
    for scene in scenes:
        pp=perf[scene]['contrasts']['selective_minus_detect']['FE_Resolve']['paired_run_percent']
        text+=f'- {scene.title()}: {min(pp):+.2f}% ~ {max(pp):+.2f}%.\n'
    text+='''
Bistro에서는 선택 resolve가 절약한 시간보다 새로 필요한 edge 검출 비용이 컸다.
Minecraft에서는 같은 검출 조건에서도 선택 resolve 비용이 증가했다. 후보 수 감소만으로
속도 향상을 보장할 수 없으며, 이 결과를 단순히 데이터 전송 또는 분기 divergence 한 가지
원인으로 확정하지 않는다. Nsight의 실제 GPU ISA/warp/메모리 트래픽은 이번에 측정하지 않았다.

반복 산포와 꼬리 지연도 보존했다. 아래 p95/p99는 네 run의 각 percentile을 평균한 값이며
모든 sample을 합친 pooled percentile이 아니다. 모든 수치는 ms다.

| 장면 | 구성 | 전체 평균 ± run-mean 표준편차 | 전체 run p95 평균 | 전체 run p99 평균 | Resolve 평균 ± run-mean 표준편차 |
|---|---|---:|---:|---:|---:|
'''
    for scene in scenes:
        for mode in [FULL,DETECT,SEL]:
            mm=perf[scene]['metrics'][mode];a=mm['SMAA'];r=mm['FE_Resolve']
            text+=f"| {scene.title()} | {names[mode]} | {a['mean_ms']:.6f} ± {a['run_mean_std_ms']:.6f} | {a['mean_run_p95_ms']:.6f} | {a['mean_run_p99_ms']:.6f} | {r['mean_ms']:.6f} ± {r['run_mean_std_ms']:.6f} |\n"
    text+='''
`*-benchmark-timings.csv`는 각 run의 mean/median/p95/p99/sample 표준편차를,
`*-benchmark-performance.json`은 반복별 차분과 평균을 담는다. 두 smoke 및 두 benchmark는
모든 metric의 sample 수와 정/역 mode 순서, EXE/report hash, Aggregate PASS를 확인했다.
숨김 창의 비용 분리용 engineering 결과다. WholeFrame/FPS/1% low와 visible 조건의 최종
6구성 비교, matched-quality 성능 우위는 별도 단계로 남아 있다.

'''
    target=D/'results-ko.md'
    old=target.read_text(encoding='utf-8');head=old[:old.index('## 성능\n')];tail=old[old.index('## 재현과 자료\n'):]
    target.write_text(head+text+tail,encoding='utf-8')
    print('PASS: report timing tables generated from validated benchmark summaries')


if __name__=='__main__':main()
