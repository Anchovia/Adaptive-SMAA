"""Publish the completed two-scene full-reference contrast evaluation."""
import hashlib
import json
from pathlib import Path

from analyze_temporal_contrast_reference import MODES

root=Path(__file__).resolve().parents[2]
analysis=root/'Projects/CMAA2/AutoBench/ContrastReferenceAnalysis'
receipts=json.loads((root/'tmp/contrast-quality-runs.json').read_text(encoding='utf-8-sig'))
initial=json.loads((root/'Docs/Temporal-Contrast-Initial/results.json').read_text())
result={'classification':'Engineering full-reference evaluation; not final eight-case conclusion',
        'implementation_commit':'82195cf','quality_capture_receipts':receipts,'scenes':{}}
for scene in ('bistro','minecraft'):
    base=analysis/scene
    q=json.loads((base/'reference-quality.json').read_text())
    cg=json.loads((base/'cgvqm-comparison.json').read_text())
    assert q['native_and_mask_bridge']==480 and q['selection_semantics_frames']==720
    assert q['selection_mismatches']==0 and q['frame_count']==240
    for window in ('moving','late_still'):
        native=q['quality'][window][MODES[0]]
        assert all(q['quality'][window][m]['rgb_mae']>native['rgb_mae'] and
                   q['quality'][window][m]['rgb_psnr_db']<native['rgb_psnr_db'] for m in MODES[1:])
    receipt=next(r for r in receipts if r['scene']==scene)
    report=Path(receipt['report'])
    assert report.parent.resolve()==Path(q['quality_capture']).resolve()
    assert hashlib.sha256(report.read_bytes()).hexdigest()==q['quality_report_sha256']
    assert set(cg)=={'moving','transition'}
    for window in cg.values():
        assert set(window)==set(MODES)
        assert len({v['record']['reference_sequence']['pixel_sha256'] for v in window.values()})==1
    playback=json.loads((base/'Playback/manifest.json').read_text())
    assert len(playback['videos'])==2 and len(playback['gifs'])==3
    assert all(v['frames']==240 and v['fps']==60 and v['pts_verified'] for v in playback['videos'])
    for item in playback['videos']+playback['gifs']:
        item['sha256']=hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
    result['scenes'][scene]={'reference':q,'cgvqm':cg,'playback':playback,'performance':initial['scenes'][scene]['performance']['modes']}
dest=root/'Docs/Temporal-Contrast-Quality';dest.mkdir(parents=True,exist_ok=True)
(dest/'results.json').write_text(json.dumps(result,indent=2)+'\n')
all_lower=all(v['minus_native']<0 for scene in result['scenes'].values() for w in scene['cgvqm'].values() for m,v in w.items() if m!=MODES[0])
lines=['# Temporal contrast: 정량 품질 및 실제 선택 픽셀 수','',
       '원본 T2X-R과 현재 색상의 대비만으로 선택하는 세 설정을 동일 시점의 supersample 기준 영상과 비교했다.',
       '세 기준값 모두 두 장면의 이동 및 정지 후기 PSNR/MAE에서 원본보다 불리했다.',
       ('CGVQM-2도 두 장면의 이동 및 정지 전환 구간 모두 원본보다 낮았다.' if all_lower else
        'CGVQM-2의 구간별 차이는 아래 표에 별도로 기록한다. 단일 평균으로 품질 우열을 합치지 않는다.'),
       '이는 기준 영상 일치도와 시간 안정성에 대한 결과다. 고스팅·잔상·블러 각각의 우열을 이 점수만으로 단정하지 않는다.',
       '픽셀 수가 줄었다는 사실만으로 점수 하락이 필연적인 것은 아니며, 잔상 감소와 깜빡임 증가가 함께 발생할 수도 있다.',
       '현재 자료만으로 품질을 유지한 속도 개선이 입증됐다고 볼 수는 없지만, 잔상 감소 여부는 연속 영상에서 별도로 확인해야 한다.','',
       '측정 정의·검증·재현 명령은 [방법 문서](../SMAA-Temporal-Contrast-Quality-Method-ko.md)를 따른다.',
       '연속 영상의 관찰 항목과 판정 범위는 [영상 검토 안내](visual-review.md)에 구분했다.',
       '코드는 camera-motion reprojection을 사용하는 Original SMAA이며 Adaptive나 object-motion 실험이 아니다.','',
       '## 원본 대비 선택 픽셀 수','',
       '원본은 frame당 2,037,120 pixel(1920×1061) 전체에서 temporal resolve를 실행한다.',
       '아래는 240 frame의 GPU mask를 직접 센 평균이다. 분모는 전체 화면이며 edge 수가 아니다.',
       '선택은 history/velocity 접근과 T2X 계산의 실행 여부다. history 가중치가 항상 양수라는 뜻은 아니다.','',
       '| 장면 | 기준값 | 평균 선택 pixel/frame | 최소~최대 | 선택 비율 | 생략 비율 |',
       '|---|---:|---:|---:|---:|---:|']
for scene,d in result['scenes'].items():
    for m,t in zip(MODES[1:],('0.005','0.01','0.02')):
        c=d['reference']['coverage']['all'][m]
        lines.append(f"| {scene} | {t} | {c['mean_pixels']:,.2f} | {c['min_pixels']:,}~{c['max_pixels']:,} | {c['mean_percent']:.3f}% | {c['skipped_percent']:.3f}% |")
lines+=['','## CGVQM-2 영상 품질','',
        '높을수록 좋다. 괄호는 같은 장면·구간 원본 대비 점수 차이이며 백분율이 아니다.',
        '이동은 frame 60~179, 정지 전환은 frame 160~219다. 각 clip은 60 FPS이며 두 구간 일부가 겹친다.','',
        '| 장면 | 구간 | 원본 T2X-R | 0.005 | 0.01 | 0.02 |','|---|---|---:|---:|---:|---:|']
for scene,d in result['scenes'].items():
    for window,label in [('moving','이동'),('transition','이동→정지')]:
        w=d['cgvqm'][window];cells=[f"{w[MODES[0]]['score']:.6f}"]
        cells += [f"{w[m]['score']:.6f} ({w[m]['minus_native']:+.6f})" for m in MODES[1:]]
        lines.append(f"| {scene} | {label} | "+' | '.join(cells)+' |')
lines+=['','## 기준 영상 대비 공간 오차 및 시간 변화','',
        'MAE는 낮을수록, PSNR과 SSIM은 높을수록 좋다. RGB MAE와 PSNR은 모든 frame, SSIM은 10 frame 간격 표본이다.',
        '시간 잔차는 기준 영상의 인접 frame 변화를 뺀 화면 luma 차이이며 순수 ghosting 지표가 아니다.','',
        '| 장면 | 구간 | mode | RGB MAE | PSNR dB | Luma SSIM | 시간 잔차 |',
        '|---|---|---|---:|---:|---:|---:|']
for scene,d in result['scenes'].items():
    for window,label in [('moving','이동'),('late_still','정지 후기')]:
        for m in MODES:
            x=d['reference']['quality'][window][m]
            lines.append(f"| {scene} | {label} | {m} | {x['rgb_mae']:.6f} | {x['rgb_psnr_db']:.6f} | {x['luma_ssim']:.6f} | {x['reference_delta_residual']:.6f} |")
lines+=['','## 기준값 0.01의 속도·품질 절충','',
        '속도는 앞선 별도 4,800 frame×3회 GPU 측정이다. 이번 영상 분석과 동시에 측정하지 않았다.','',
        '| 장면 | 전체 SMAA 시간 변화 | 선택 비율 | 이동 CGVQM 변화 | 정지 전환 CGVQM 변화 |',
        '|---|---:|---:|---:|---:|']
for scene,d in result['scenes'].items():
    m=MODES[2]
    lines.append(f"| {scene} | {d['performance'][m]['SMAA']['percent_vs_native']:+.3f}% | {d['reference']['coverage']['all'][m]['mean_percent']:.3f}% | {d['cgvqm']['moving'][m]['minus_native']:+.6f} | {d['cgvqm']['transition'][m]['minus_native']:+.6f} |")
lines+=['','## 검증과 해석 범위','',
        '- 두 장면에서 기존 native/mask 960장 hash가 일치했고, 세 threshold×240 frame×2장면의 선택/생략 픽셀 불일치가 0이다.',
        '- 새 reference/mask/native 캡처 총 2,400장과 기존 출력이 대응한다. 마스크 포함 관계도 모든 frame에서 통과했다.',
        '- 16개 CGVQM-2 실행에서 입력 RGB FFV1 왕복 불일치 0, 구간별 reference hash 일치를 확인했다.',
        '- RGB reference 자체의 후기 정지 변화는 아래에 별도 기록한다. Native는 정지 후 안정되고 세 대비 설정은 2-frame 교대 변화를 남긴 기존 관측과 일치한다.']
for scene,d in result['scenes'].items():
    q=d['reference'];steps=q.get('reference_late_still_steps',[])
    lines.append(f"- {scene} reference: 후기 PNG hash {q['reference_late_still_unique_png']}종"+
                 (f", 인접 frame 최대 {max(x['max_rgb_step'] for x in steps)} RGB level, 최대 {max(x['changed_channels'] for x in steps)} channel 변경, 평균 RGB 변화 {sum(x['mean_rgb_step'] for x in steps)/len(steps):.10f}." if steps else ', pixel-exact 정지.'))
lines+=['',
        'Bistro에서는 대부분의 픽셀을 생략해 속도를 줄였지만 해당 reference 대비 오차와 시간 변화가 늘었다. ',
        'Minecraft에서는 더 많은 픽셀이 선택돼 절감 효과가 부족했고, 시험한 세 설정의 전체 SMAA 시간이 원본보다 길었다.',
        '판정 비용과 GPU 분기 실행 비용은 이번 품질 지표로 분해하지 않았으므로 선택률만으로 병목 원인을 확정하지 않는다.','',
        '움직이는 비교 MP4와 GIF는 `ContrastReferenceAnalysis/<scene>/Playback`에 저장한다. ',
        '정속 60 FPS 영상과 1:1 crop을 우선 보고, 0.5배속 GIF는 보조로 사용한다. ',
        '잔상, 깜빡임, 선명도를 구분해 보며 수치 열세를 고스팅 악화와 동일시하지 않는다.','',
        '이 결과는 두 장면·이 카메라 경로·세 threshold에 대한 결과다. CGVQM은 지각 품질 예측이며 ',
        'supersample spatial reference에는 MIP/sharpen 튜닝이 포함돼 있다. 절대 ghosting 감소율이나 ',
        '모든 장면에서의 품질 우열을 주장하지 않는다. 선택 기준과 jitter/temporal 결합 생략의 상호작용을 ',
        '후속 실험에서 분리하는 것이 다음 검토 대상이다.','',
        '원시 PNG·CSV·lossless 영상과 비교 이미지는 실행별 AutoBench 및 `ContrastReferenceAnalysis/<scene>`에 보존했다. ',
        'Git에는 재현 도구, 방법 문서 및 구조화한 결과를 저장한다.','']
(dest/'report.md').write_text('\n'.join(x.rstrip() for x in lines),encoding='utf-8')
print('PASS: published two-scene contrast quality and coverage')
