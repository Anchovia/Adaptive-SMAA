"""Report paired reconstruction separately from luma selection and filter cost."""
import json,hashlib
from decimal import Decimal
from pathlib import Path
from analyze_temporal_paired_dejitter import NATIVE,POINT,LINEAR,SCALAR,SLINEAR,MODES,read_receipt
root=Path(__file__).resolve().parents[2];out=root/'Docs/Temporal-Paired-DeJitter'
manifest=json.loads((root/'tmp/temporal-paired-dejitter-runs.json').read_text(encoding='utf-8-sig'))
assert len(manifest)==8
assert {(r['scene'],r['phase']) for r in manifest}=={(s,p) for s in ('bistro','minecraft') for p in ('StaticCapture','Capture','Smoke','Benchmark')}
for r in manifest:
 report=Path(r['report']);body=report.read_text(encoding='utf-8-sig')
 assert hashlib.sha256(report.read_bytes()).hexdigest()==r['report_sha256'].lower()
 assert 'Aggregate: PASS' in body and 'Aggregate: FAIL' not in body
(out/'run-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
names={NATIVE:'원본 T2X-R',POINT:'History Linear만',SCALAR:'기존 luma 선택',LINEAR:'전체 paired 보정',SLINEAR:'선택적 paired 보정'}
qs={};ps={}
for scene in ('bistro','minecraft'):
 qs[scene]=json.loads((out/f'{scene}-quality.json').read_text())
 ps[scene]=json.loads((out/f'{scene}-performance.json').read_text())
 for phase,d in (('Capture',qs[scene]),('Benchmark',ps[scene])):
  receipt,_,_=read_receipt(root/'tmp/temporal-paired-dejitter-runs.json',scene,phase)
  # PowerShell may drop trailing fractional-second zeros when appending a
  # receipt. Preserve recorded strings; compare timestamps at full precision.
  saved=d['receipt'];assert receipt.keys()==saved.keys()
  for k,v in receipt.items():
   if k.endswith('_utc'):
    other=saved[k]
    assert v.endswith('Z') and other.endswith('Z') and v[:19]==other[:19]
    assert Decimal(v[19:-1] or '0')==Decimal(other[19:-1] or '0')
   else:assert v==saved[k],(scene,phase,k)
 assert qs[scene]['mismatches']==0 and ps[scene]['validation']=='PASS'
groups=json.loads((out/'static-groups.json').read_text())
lines=['# Temporal 패스 내 current/history paired de-jitter 결과','',
 '현재·이전 색상에 각각 해당 프레임의 지터 위치 보정을 적용하고, 전체 화면 결합을 먼저 검증한 뒤 기존 luma 선택을 적용했다. '
 '별도 pass·texture·copy 없이 기존 temporal pixel shader의 current/history sample을 재사용했다. '
 'Original spatial SMAA와 camera/depth reprojection On을 사용한 engineering ablation이며 최종 8-case 또는 공식 TSCMAA 포팅 결과가 아니다.','',
 '브랜치 `experiment/temporal-pass-paired-dejitter`. 전체 화면 정지 gate 커밋 `bebd827`, 선택적 구현·분석 커밋 `90d2326`. '
 '[사전 실험 계획](method.md).','',
 '## 핵심 결과','',
 '| 장면 | 기존 선택: 정지 RGB 변화 | 새 선택: 정지 RGB 변화 | 변화율 | 새 선택 AA 시간: 원본 대비 |',
 '|---|---:|---:|---:|---:|']
for scene,q in qs.items():
 old=q['windows']['late_still'][SCALAR]['rgb_step'];new=q['windows']['late_still'][SLINEAR]['rgb_step']
 cost=ps[scene]['comparisons'][SLINEAR+' minus '+NATIVE]['SMAA']['delta_percent']
 lines.append(f'| {scene} | {old:.6f} | {new:.6f} | {(new/old-1)*100:+.2f}% | {cost:+.3f}% |')
lines+=['','RGB 변화량은 0..255 RGB 단계의 프레임 간 평균 절댓값이며 지각적 개선율이 아니다. '
 '전체 화면 보정과 선택적 보정의 결과를 구분해야 한다. 원본 T2X-R의 후기 정지 변화량은 두 장면 모두 0이다.','',
 '## 구현과 해석','',
 '- 현재는 Linear(UV+j), history는 Linear(UV-motion-j), velocity는 기존 Point(UV)를 읽는다. '
 'j는 현재 subsample index에서 얻으며 history가 유효할 때 직전 spatial frame은 반대 phase다.',
 '- 첫 frame/reset은 같은 draw에서 corrected spatial로 seed한다. 성공한 draw 뒤에만 history/frame index가 진행한다. '
 'history는 계속 raw neighborhood-blended spatial frame이다. 새로운 history feedback 구조를 만들지 않았다.',
 '- 기존 current-only 식의 `(D0(C0)+C1)/2`와 `(D1(C1)+C0)/2` 비대칭을, 정지에서 '
 '`(D0(C0)+D1(C1))/2`의 대칭 결합으로 바꾸는 진단이다. Bilinear reconstruction이 원본 subpixel 세부정보를 완벽히 보존한다는 뜻은 아니다.',
 '- 선택식은 보정 current RGB의 linear luma 미분 `max(abs(ddx_fine(Y)),abs(ddy_fine(Y)))>=.01`이다. '
 '이전 current-only 실험과 mask/current 입력은 동일하며, 최초 원위치 Scalar와는 선택 영역이 다르다.',
 '- Scalar는 history를 읽은 뒤 weight를 0으로 만든다. 선택률은 결합 적용률이며 texture fetch 절감률이 아니다. '
 'R On의 sample 명령 3개/R Off의 2개를 유지하지만 Linear 필터는 더 많은 texel을 참조할 수 있다.',
 '- 필터는 RGBA 모두에 적용되어 velocity-alpha 기반 가중치도 바뀐다. velocity는 원래 UV에서 읽으므로 움직이는 경계의 좌표 정합에는 근사가 남는다. '
 'object-motion 및 previous-depth disocclusion 처리를 추가한 실험이 아니다.','',
 '## 정확성 검증','',
 '- 원본 8 shader variant와 이전 current-only 10 variant 불변. 새 full/Scalar의 R Off/On 컴파일, 샘플 수 및 분기 검사 PASS.',
 '- 전체 화면 선행 정지 검사: 장면당 6 mode×40 frame, 초기 60 warmup 뒤 reset. '
 '두 장면 모두 후기 20장의 paired full RGB 변화량 0, repeat/seed 일치. 기존 대조군 320개 hash 비교와 반복 80개 비교 일치.',
 '- 후속 11 mode×240 frame×2장면의 pattern 5,280개 PASS. 기존 대조군·반복 3,360개, '
 '이전 corrected spatial/mask 재사용 960개, 선행 paired static 80개 hash 비교 일치.',
 '- 선택 픽셀=paired full, 비선택=corrected spatial을 모든 capture frame에서 검사했다. '
 '첫 seed도 일치했다. R Off는 shader compile 범위이며 실제 장면 품질/성능은 camera R On만 측정했다.','',
 '## 품질','',
 '1920×1061, 고정 60Hz, 최초 정지 60 + 이동 120 + 후기 정지 60 frame이다. '
 '기존 동일 pose supersample spatial proxy를 hash bridge로 재사용했다. MAE·PSNR·윤곽/reference와 '
 '시간 변화 잔차는 절대 ghosting ground truth가 아니다. 필터링으로 흐려져 오차가 감소할 수 있으므로 윤곽과 영상을 함께 제공한다.','']
for scene,q in qs.items():
 lines += [f'### {scene}','','| 구간 | 방식 | RGB MAE | PSNR dB | 윤곽/reference | 시간 변화 잔차 |','|---|---|---:|---:|---:|---:|']
 for window,label in (('moving','이동'),('transition','정지 전환'),('late_still','후기 정지')):
  for m in MODES:
   v=q['windows'][window][m]
   lines.append(f"| {label} | {names[m]} | {v['rgb_mae']:.6f} | {v['psnr_db']:.3f} | {v['edge_reference_ratio']:.4f} | {v['reference_delta_residual']:.6f} |")
 lines+=['','| 방식 | 후기 정지 RGB 변화 | RGB 프레임 종류 | 2-frame 간격 불일치 |','|---|---:|---:|---:|']
 for m in MODES:
  v=q['static_hashes']['late_still'][m]
  lines.append(f"| {names[m]} | {q['windows']['late_still'][m]['rgb_step']:.6f} | {v['unique_rgb_frames']} | {v['lag2_mismatches']} |")
 lines+=['','| 구간 | 기존 선택 % | 새 선택 % | 새 선택 픽셀 수(평균) | 선택 변경 % |','|---|---:|---:|---:|---:|']
 for w in ('moving','late_still'):
  v=q['coverage'][w]
  lines.append(f"| {w} | {v['original_selected_percent']:.4f} | {v['selected_percent']:.4f} | {v['selected_pixels']:.1f} | {v['selection_change_percent']:.4f} |")
 lines+=['','| 새 선택의 두 위상 상태 | 화면 % | 기존 선택 영역 내 변화 | 새 선택 영역 내 변화 | 새 전체 변화 기여 |','|---|---:|---:|---:|---:|']
 for row in groups[scene]['groups']:
  a=row[SCALAR];b=row[SLINEAR]
  lines.append(f"| {row['group']} | {row['pixel_percent']:.4f} | {a['conditional_step']:.6f} | {b['conditional_step']:.6f} | {b['full_frame_contribution']:.6f} |")
 lines+=['']
lines+=['## 성능','','RTX 3060 Ti / DX11 / SMAA Ultra / 숨긴 창 / VSync Off. 장면별 독립 process에서 '
 '30초 미측정 예열, mode당 300 frame warmup, 4,800 frame×4회, 정순·역순 각2회. '
 'PNG·readback·pattern 검사를 끄고 영상 분석과 분리했다. 네 반복은 한 process 내부이며 독립4회나 동등성 증명이 아니다. '
 '성능 JSON에 median, p95/p99, 표본·run 표준편차, wall FPS/1% low 및 순서별 차이를 기록했다.','']
for scene,p in ps.items():
 lines += [f'### {scene}','','| 방식 | 전체 AA ms | 원본 대비 | Resolve ms | 원본 대비 | WholeFrame ms |','|---|---:|---:|---:|---:|---:|']
 for m in MODES:
  v=p['means'][m];n=p['means'][NATIVE];aa=v['SMAA']['mean_ms'];rr=v['Resolve']['mean_ms']
  lines.append(f"| {names[m]} | {aa:.6f} | {(aa/n['SMAA']['mean_ms']-1)*100:+.3f}% | {rr:.6f} | {(rr/n['Resolve']['mean_ms']-1)*100:+.3f}% | {v['WholeFrame']['mean_ms']:.6f} |")
 lines+=['','| 비교 | 지표 | 차이 ms | 차이 % | 느린 반복 | 정순 차이 ms | 역순 차이 ms |','|---|---|---:|---:|---:|---:|---:|']
 for c,b in ((LINEAR,POINT),(SLINEAR,LINEAR),(SLINEAR,SCALAR),(SLINEAR,NATIVE)):
  for metric in ('SMAA','Resolve'):
   v=p['comparisons'][c+' minus '+b][metric]
   lines.append(f"| {names[c]} − {names[b]} | {metric} | {v['delta_ms']:+.6f} | {v['delta_percent']:+.3f}% | {v['slower_runs']}/4 | {v['forward_mean_delta_ms']:+.6f} | {v['reverse_mean_delta_ms']:+.6f} |")
 lines+=['']
lines+=['## 판정과 한계','',
 '**이번 선택적 paired 보정은 기본 구현으로 채택하지 않는다.** 전체 화면 보정은 정지 두 위상의 대칭성을 회복했지만, '
 'luma threshold로 결합을 생략하면 비선택 영역과 선택이 전환되는 영역에 떨림이 남는다. '
 '두 위상에서 항상 선택되는 영역의 새 RGB 변화는 0이다. 즉 이번에는 선택 영역의 좌표 비대칭과 생략 기준의 실패를 분리했다.','',
 '이동 구간의 새 선택 RGB MAE는 기존 선택보다 두 장면 모두 낮다. 그러나 원본보다 윤곽 강도가 낮고, '
 '후기 정지 MAE는 원본보다 두 장면 모두 높다. 특히 Minecraft의 후기 정지 MAE는 기존 선택보다도 높아진다. '
 '정지 변화 감소율만으로 종합 품질 향상이나 고스팅 감소를 단정하지 않는다. ','',
 '전체 화면 보정에서 선택적 보정으로 바꾸어도 current/history sample을 모두 실행한다. '
 '비선택 픽셀의 weight를 0으로 만들 뿐 결합 연산 자체가 제거되는 것은 아니다. '
 '색상 재구성·history fetch 비용은 남고 luma 미분/선택 비용이 추가된다. '
 '측정된 변화와 순서별 반복값을 근거로 비용을 판단하며, 별도 GPU 카운터로 내부 병목 비중까지 분해한 결과는 아니다.','',
 '현재만 보정했던 이전 실패를 양쪽 보정으로 해결할 수 있었지만, 이 bilinear 재구성과 고정 luma 선택 조합이 '
 '원본 T2X-R의 속도와 정지 품질을 함께 대체하지는 못했다. 이 결론은 이번 구성에 한정된다. '
 '추가 pass·후보 확장 없이 temporal 패스의 기존 정보로 더 나은 생략 기준을 찾을 수 있는지는 남은 연구 질문이다.','',
 '## 재현 자료','','| 장면 | 캡처 | Benchmark | 실행파일 SHA-256 |','|---|---|---|---|']
for scene,q in qs.items():
 lines.append(f"| {scene} | {Path(q['receipt']['report']).parent.name} | {Path(ps[scene]['receipt']['report']).parent.name} | `{q['receipt']['executable_sha256']}` |")
lines+=['','정확한 인자·report hash는 장면별 JSON의 receipt에 있다. '
 '실행 기록을 누적할 때 PowerShell이 UTC 소수초의 끝자리 0을 제거한 두 필드가 있었으며, '
 '보고서 생성 시 전체 정밀도의 시각 값이 같은지 검사했다. 실행파일·인자·결과 파일 hash는 일치했고 원시 기록은 변경하지 않았다. '
 'AutoBench/PairedDeJitterAnalysis 아래에 원본/full/기존 선택/새 선택의 4열 MP4, GIF 및 연속 프레임 자료를 만들었다. '
 'MP4는 240 frame/60FPS/전체 decode와 PTS를 검사했고 GIF는 고정 palette, 0.5배 재생이다. '
 '화면 고정 ROI의 발표·육안 검토 자료이며 전체 장면 또는 사용자 지각평가를 대신하지 않는다.','']
(out/'report.md').write_text('\n'.join(line.rstrip() for line in lines),encoding='utf-8')
print(out/'report.md')
