"""Report matched-image quality results without reclassifying proxy errors as ghosting truth."""
import csv,json,hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from stencil_quality_common import DOC,OUT,SCENES,LABELS,sha

ORDER=['AA-Off','O-1X','ABL-TemporalOnly-R','O-T2X-R','Raw-Edge-Stencil-Off-R','Spatial-Edge-Stencil-Off-R']
KEYS=['O-1X','O-T2X-R','Spatial-Full-Off-R','Spatial-Edge-Stencil-Off-R']
SHORT={'O-1X':'SMAA 1X','O-T2X-R':'Original T2X-R','Spatial-Full-Off-R':'Full / Pattern Off','Spatial-Edge-Stencil-Off-R':'SMAA + edge / Pattern Off'}
SHORT.update({'ABL-TemporalOnly-R':'Temporal-only / Pattern On','Raw-Full-Off-R':'Raw full / Pattern Off','Raw-Edge-Stencil-Off-R':'Raw edge / Pattern Off'})


def read(scene,kind):
    path=DOC/f'{scene}-{kind}.json';data=json.loads(path.read_text());assert data['validation']=='PASS'
    return data


def main():
    quality={s:read(s,'cgvqm') for s in SCENES}
    metrics={s:read(s,'metrics') for s in SCENES}
    visuals={s:read(s,'visuals') for s in SCENES}
    charts=[];out=OUT/'Summary';out.mkdir(parents=True,exist_ok=True)
    for scene in SCENES:
        with (DOC/f'{scene}-metrics-frames.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
        fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True,constrained_layout=True)
        for mode in KEYS:
            values=[r for r in rows if r['region']=='full' and r['mode']==mode]
            assert len(values)==240
            for ax,col in zip(axes,['rgb_mae','flow_error_residual_10','luma_ssim']):
                y=[float(r[col]) if r[col] else np.nan for r in values]
                ax.plot([int(r['frame']) for r in values],y,label=SHORT[mode],linewidth=1.5)
        for ax in axes:
            ax.axvspan(60,180,color='#aaaaaa',alpha=.15);ax.axvline(180,color='#555555',linestyle='--',linewidth=.8);ax.grid(alpha=.2)
        axes[0].set_ylabel('RGB MAE (0-255)');axes[0].legend(ncol=2,fontsize=9)
        axes[1].set_ylabel('Flow-aligned error change\n(luma 0-255)')
        axes[2].set_ylabel('Luma SSIM');axes[2].set_xlabel('Frame (60 FPS; shaded = camera moving)')
        fig.suptitle(f'{scene}: spatial reference and shared-flow diagnostics (not ghosting ground truth)')
        path=out/f'{scene}-quality-timeline.png';fig.savefig(path,dpi=150);plt.close(fig)
        charts.append(dict(scene=scene,path=str(path),sha256=sha(path)))
    text='''# 첫 edge 선택 구현의 품질 비교

①~⑥과 raw/spatial full-screen Pattern-Off 대조군을 같은 240-frame timeline과
supersample spatial reference로 비교했다. 알고리즘 코드는 변경하지 않았다.
기존 ②·④·⑤·⑥ 및 Off full 점수는 새 캡처와 RGB/index hash가 일치하는 범위에서
재사용했고, 빠져 있던 ①·③의 두 장면×두 구간 CGVQM-2를 새로 계산했다.

## CGVQM-2 전체 비교

높을수록 좋다. 이동=60~179, 전환=160~219, 60 FPS. 점수 하나로 잔상·깜빡임·선명도를
각각 판정하지 않는다. ⑤·⑥은 jitter/sample pattern Off이며 ③·④는 원본 pattern On이다.

| 구성 | Bistro 이동 | Bistro 전환 | Minecraft 이동 | Minecraft 전환 |
|---|---:|---:|---:|---:|
'''
    for mode in ORDER+['Raw-Full-Off-R','Spatial-Full-Off-R']:
        values=[quality[s]['results'][w]['scores'][mode] for s in SCENES for w in ['moving','transition']]
        text+='| '+LABELS[mode]+' | '+' | '.join(f'{v:.4f}' for v in values)+' |\n'
    text+='''
①·③의 품질 평가 누락은 이번에 채웠다. ③의 높은 점수를 공간 AA 생략이 항상
더 좋다는 결론으로 일반화하지 않는다. 이 장면·reference·지표에서 관측한 결과다.

## ⑥과 원본 ④의 차이 분리

원본 paired sample pattern에는 projection jitter와 spatial subsample-index 조합이
함께 포함된다. 아래는 실제 사용한 두 비교의 차이이며, 모든 상황에 독립적으로 적용되는
주효과나 통계적 유의성 주장이 아니다.

| 장면·구간 | ⑥ − 원본④ | Off full − 원본④ | ⑥ − Off full |
|---|---:|---:|---:|
'''
    contrasts=[]
    for s in SCENES:
        for w in ['moving','transition']:
            scores=quality[s]['results'][w]['scores'];native=scores['O-T2X-R'];full=scores['Spatial-Full-Off-R'];selected=scores['Spatial-Edge-Stencil-Off-R']
            d=dict(scene=s,window=w,total=selected-native,pattern_control=full-native,selection_at_pattern_off=selected-full)
            contrasts.append(d);text+=f"| {s} {w} | {d['total']:+.4f} | {d['pattern_control']:+.4f} | {d['selection_at_pattern_off']:+.4f} |\n"
    text+='''
⑥은 Bistro 이동에서 원본과 비슷하고 전환에서 낮았다. Minecraft 이동에서는 높았지만
전환에서는 거의 비슷했다. Minecraft 이동의 큰 차이는 대부분 full-screen 경로에서도
나타난 sample-pattern 변경 차이이며, 모두 edge 선택 효과로 설명할 수 없다.
같은 Off 조건의 edge 선택만 비교하면 Bistro는 낮고 Minecraft는 높아 장면 의존성이 남는다.

공간 AA가 없는 ⑤도 대응 기준선 ③과 비교하고, raw Off full 대조군으로 선택 효과를
따로 본다. 이 비교를 ④ 대비의 공간+temporal 최종 품질로 바꾸어 해석하지 않는다.

| 장면·구간 | ⑤ − ③ | Raw Off full − ③ | ⑤ − Raw Off full |
|---|---:|---:|---:|
'''
    raw_contrasts=[]
    for s in SCENES:
        for w in ['moving','transition']:
            scores=quality[s]['results'][w]['scores'];native=scores['ABL-TemporalOnly-R'];full=scores['Raw-Full-Off-R'];selected=scores['Raw-Edge-Stencil-Off-R']
            d=dict(scene=s,window=w,total=selected-native,pattern_control=full-native,selection_at_pattern_off=selected-full)
            raw_contrasts.append(d);text+=f"| {s} {w} | {d['total']:+.4f} | {d['pattern_control']:+.4f} | {d['selection_at_pattern_off']:+.4f} |\n"
    text+='''

## 전체 화면 참조 오차와 시간 변화

MAE는 낮을수록, SSIM은 높을수록 reference에 가깝다. Flow 잔차가 낮다는 것은
공통 SS-Reference flow로 정렬한 오류의 시간 변화가 작다는 뜻이다. 일정하게 유지되는
오류도 이 지표에서는 작을 수 있으므로 절대 고스팅 양이나 전체 품질 점수로 쓰지 않는다.
Reference 자체의 warp 잔차와 flow 유효 비율은 JSON에 함께 기록했다.

| 장면·구간 | 구성 | RGB MAE | PSNR dB | SSIM | Flow 오류 변화 |
|---|---|---:|---:|---:|---:|
'''
    for s in SCENES:
        for w in ['moving','transition']:
            for mode in ['O-1X','ABL-TemporalOnly-R','Raw-Full-Off-R','Raw-Edge-Stencil-Off-R','O-T2X-R','Spatial-Full-Off-R','Spatial-Edge-Stencil-Off-R']:
                v=metrics[s]['summary']['full'][mode][w]
                text+=f"| {s} {w} | {SHORT[mode]} | {v['rgb_mae']:.4f} | {v['psnr_db']:.3f} | {v['luma_ssim']:.6f} | {v['flow_error_residual_10']:.4f} |\n"
    text+='''
### 정렬 지표의 적용 범위

이동 구간의 flow 유효 비율과 reference 자체의 재투영 잔차다. 유효하지 않은 위치를
제외하므로 이 지표만으로 새로 드러난 영역의 품질을 판정하지 않는다. 0.5/1/2 px는
forward/backward consistency 허용값이며, 아래 잔차 차이는 ⑥ − ④다.

| 장면 | 유효 비율(1 px) | Reference warp 잔차 | 차이(0.5 px) | 차이(1 px) | 차이(2 px) |
|---|---:|---:|---:|---:|---:|
'''
    for s in SCENES:
        v=metrics[s]['summary']['full']['Spatial-Edge-Stencil-Off-R']['moving']
        n=metrics[s]['summary']['full']['O-T2X-R']['moving']
        ds=[v['flow_error_residual_'+k]-n['flow_error_residual_'+k] for k in ['05','10','20']]
        text+=f"| {s} | {v['flow_valid_10']*100:.3f}% | {v['reference_warp_residual']:.4f} | "+' | '.join(f'{d:+.4f}' for d in ds)+' |\n'
    text+='''
### 선택·비선택 영역

⑥의 실제 첫 패스 RG edge mask를 공통 영역 구분에 사용한 이동 구간 평균이다.
다른 mode의 RGB 오차도 같은 mask에서 평가했으며, 이 mask가 원본 ④의 jitter On
edge mask라는 뜻은 아니다. 선택 전환은 같은 화면 좌표의 이전/현재 mask 차이다.
움직이는 동일 표면의 후보 유지율이나 GPU helper invocation 비율로 해석하지 않는다.

| 장면 | 선택 비율 | 선택 전환 비율 | 영역 | ④ RGB MAE | Off full RGB MAE | ⑥ RGB MAE |
|---|---:|---:|---|---:|---:|---:|
'''
    for s in SCENES:
        values=[metrics[s]['summary']['full'][m]['moving'] for m in ['O-T2X-R','Spatial-Full-Off-R','Spatial-Edge-Stencil-Off-R']]
        selected=values[-1]
        for region,col in [('선택','selected_rgb_mae'),('비선택','nonselected_rgb_mae'),('선택 전환','toggled_rgb_mae')]:
            text+=f"| {s} | {selected['selected_fraction']*100:.3f}% | {selected['selection_toggled_fraction']*100:.3f}% | {region} | "+' | '.join(f'{v[col]:.4f}' for v in values)+' |\n'
    text+='''
## 얇은 구조·가려짐 경계 ROI

아래는 이동 구간의 ⑥ − ④ 차이다. 오차 차이가 음수면 reference에 더 가깝다.
Gradient 오차도 reference와의 차이이며, gradient가 강한 것 자체를 품질 향상으로
취급하지 않는다. 화면 고정 ROI이고 object tracking이나 정확한 disocclusion mask는 아니다.

| 장면·ROI | RGB MAE 차이 | SSIM 차이 | Gradient 오차 차이 | Flow 오류 변화 차이 |
|---|---:|---:|---:|---:|
'''
    roi_deltas=[]
    for s in SCENES:
        for region in metrics[s]['rois']:
            native=metrics[s]['summary'][region]['O-T2X-R']['moving'];selected=metrics[s]['summary'][region]['Spatial-Edge-Stencil-Off-R']['moving']
            d={k:selected[k]-native[k] for k in ['rgb_mae','luma_ssim','gradient_mae','flow_error_residual_10']}
            roi_deltas.append(dict(scene=s,roi=region,deltas=d))
            text+=f"| {s} {region} | {d['rgb_mae']:+.4f} | {d['luma_ssim']:+.6f} | {d['gradient_mae']:+.4f} | {d['flow_error_residual_10']:+.4f} |\n"
    text+='''
## 정지 안정화

Frame 180 이후 각 mode 자신의 후기 정지 frame 239와 영구적으로 일치하기까지 걸린
프레임 수다. 관측된 마지막 40개 frame 전체의 일치를 요구하며, 마지막 한 frame의
자기 일치만으로 안정화됐다고 판정하지 않는다. `미확인`은 이 byte-exact 기준의
지속 안정화가 확인되지 않았다는 뜻이며 변화 크기는 별도로 확인해야 한다.
자체적으로 안정된 결과가 reference에 더 정확하다는 뜻은 아니다.

| 장면 | ① | ② | ③ | ④ | ⑤ | ⑥ |
|---|---:|---:|---:|---:|---:|---:|
'''
    for s in SCENES:text+='| '+s+' | '+' | '.join(str(metrics[s]['settling_frames_after_180']['full'][m]) if metrics[s]['settling_frames_after_180']['full'][m] is not None else '미확인' for m in ORDER)+' |\n'
    text+='''
## 결과 해석

두 장면에서 ⑤·⑥은 frame 181부터 후기 정지 결과와 일치했고, ④는 frame 182부터
일치했다. 마지막 40-frame의 실제 RGB 변화는 모든 mode에서 0이었다. 이번 캡처에서
⑤·⑥의 지속적인 정지 떨림은 확인되지 않았다. 지터를 끈 영상이 안정적이라는 사실과
원본 T2X의 시간적 supersampling에 의한 세부 복원 품질이 같은지는 별개의 문제다.

같은 Off 조건에서 선택 처리로 바꾸면 전체 화면의 평균 RGB 오차는 줄었지만,
MSE에 기반한 PSNR은 두 장면 모두 낮아졌다. 일부 큰 오차와 시간적 안정화를
평균 RGB 오차 하나로 설명할 수 없다. 이동 구간의 flow 정렬 오류 변화는 다음과 같다.

| 장면 | Off full | ⑥ 선택 처리 | 선택으로 인한 변화 |
|---|---:|---:|---:|
'''
    for s in SCENES:
        full=metrics[s]['summary']['full']['Spatial-Full-Off-R']['moving']['flow_error_residual_10']
        selected=metrics[s]['summary']['full']['Spatial-Edge-Stencil-Off-R']['moving']['flow_error_residual_10']
        text+=f'| {s} | {full:.4f} | {selected:.4f} | {(selected/full-1)*100:+.2f}% |\n'
    text+='''
즉 원본 ④와 비교한 시간 변화 감소를 모두 선택 처리의 이점으로 설명하면 안 된다.
같은 Off full에 대해서는 이 보조 지표가 오히려 증가했다. 고스팅을 줄이는 동시에
깜빡임까지 일관되게 줄였다고 결론내릴 근거는 아직 부족하다.

이동 중 고정 ROI에서도 차이가 난다. Bistro 의자 다리의 RGB MAE는 ④ 대비 조금
줄었지만 창살의 MAE·SSIM은 나빠졌다. Minecraft의 세 ROI는 ④ 대비 MAE·SSIM이
개선됐으나, 이 비교에는 pattern 변경이 함께 들어 있다. Frame 110 확대와
179~182 연속 PNG로 구조 차이를 확인했으며, MP4/GIF는 동기화된 육안 비교 자료다.
주관적 사용자 평가나 독립 물체의 잔상 길이 측정을 완료한 것으로 표시하지 않는다.
'''
    text+='''
## 비교 자료와 해석 범위

각 장면에 6-case overview, reference/1X/④/⑥ 확대, ④/Off full/⑥ 분리 비교,
앞쪽 경계 확대 MP4를 만들었다. 60 FPS와 전체 frame 수 및 PTS 간격을 decode해 검증했다.
느린 GIF와 이동/정지 전환의 원본 크기 연속 PNG도 제공한다. Bistro 확대 영상만 표시용
밝기 3배를 사용하며 모든 정량 수치는 변경하지 않은 PNG에서 계산했다.

'''
    for s in SCENES:
        folder=OUT/s/'Playback'
        text+=f'- {s}: `{folder}`\n'
    text+='\n시간별 그래프: `'+str(out)+'`.\n'
    text+='''
같은 pattern/spatial 조건의 성능 실험에서 ⑥의 전체 AA 시간은 Bistro 15.10%, Minecraft
3.73% 감소했다. 품질은 위와 같이 장면·구간에 따라 달라져 전반적인 품질 우위로
결론내리지 않는다. 이 수치를 jitter On 원본 대비의 순수 temporal 선택 효과로 바꾸어
설명하지 않는다. 성능 원자료는 `53ff61d:Docs/Spatial-First-Edge-Stencil`에 있다.

이번 캡처는 camera-motion 장면이다. 빠르게 움직이는 독립 물체, 크게 새로 드러나는
표면, 정확한 잔상 길이·유지 시간의 object-tracked ground truth는 미검증이다.
Flow가 유효하지 않은 위치를 확정 disocclusion으로 부르지 않으며, 속도나 CGVQM
하나만으로 global ghosting이 해소됐다고 결론내리지 않는다.

[평가 방법과 사전 ROI](method.md), `*-cgvqm.json`, `*-metrics.json`, `*-metrics-frames.csv`,
`*-visuals.json`에 설정·입력 hash·원시 산출물 위치·세부 수치를 보존했다.
`*-sources.json`은 재사용한 고정 commit/path/SHA-256을 기록한다.
'''
    (DOC/'report.md').write_text(text,encoding='utf-8')
    result=dict(validation='PASS',quality_contrasts=contrasts,raw_quality_contrasts=raw_contrasts,roi_deltas=roi_deltas,charts=charts,
                inputs={f'{s}-{k}.json':sha(DOC/f'{s}-{k}.json') for s in SCENES for k in ['cgvqm','metrics','visuals']},
                scope='Completed existing-camera-path quality assessment, not independent-object/disocclusion ground truth or final paper-wide comparison.')
    (DOC/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: quality report and reference/flow timeline charts generated')


if __name__=='__main__':main()
