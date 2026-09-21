import json,statistics as st
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Docs/Temporal-Selection-Validity'
data=json.loads((OUT/'offline.json').read_text());rows=data['rows']
summary=[]
keys=sorted({(r['scene'],r['basis'],r['split'],r['window'],r['selector'],r['threshold'] or 0) for r in rows})
metrics=('selected_percent','switch_percent','rgb_mae','native_rgb_mae','rgb_step','reference_delta_residual','oracle_rgb_mae')
for key in keys:
 rs=[r for r in rows if (r['scene'],r['basis'],r['split'],r['window'],r['selector'],r['threshold'] or 0)==key]
 summary.append(dict(zip(('scene','basis','split','window','selector','threshold'),key),**{m:st.mean(r[m] for r in rs) for m in metrics}))
(OUT/'offline-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['# Offline proxy 전체 비교표','','현재/결합 출력 PNG에서 얻은 근사이며 GPU mask·실측 성능이 아니다. 개발·검증 pose를 분리했고 각 장면을 따로 보고한다.','']
for scene in ('bistro','minecraft'):
 for basis in ('native','paired'):
  for split in ('development','validation'):
   lines += [f'## {scene} / {basis} / {split}','','| 조건 | threshold | 이동 MAE (원본 차이) | 정지 RGB 변화 | 선택 % (이동/정지) | 정지 mask 변경 % |','|---|---:|---:|---:|---:|---:|']
   for sel,t in sorted({(r['selector'],r['threshold'] or 0) for r in rows}):
    part=[r for r in summary if r['scene']==scene and r['basis']==basis and r['split']==split and r['selector']==sel and r['threshold']==t]
    move=next(r for r in part if r['window']=='moving');still=next(r for r in part if r['window']=='still')
    lines.append(f"| {sel} | {t:g} | {move['rgb_mae']:.6f} ({move['rgb_mae']-move['native_rgb_mae']:+.6f}) | {still['rgb_step']:.6f} | {move['selected_percent']:.3f}/{still['selected_percent']:.3f} | {still['switch_percent']:.4f} |")
   lines.append('')
(OUT/'offline-tables.md').write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
for scene in ('bistro','minecraft'):
 for basis in ('native','paired'):
  for sel,t in [('gradient-001',.01),('absolute-large',.00025),('absolute-large',.0005),('absolute-large',.001),('absolute-small',.016),('relative-large',.01)]:
   part=[r for r in summary if r['scene']==scene and r['basis']==basis and r['split']=='validation' and r['selector']==sel and r['threshold']==t]
   print(scene,basis,sel,t,{r['window']:{m:round(r[m],6) for m in ('rgb_mae','rgb_step','selected_percent','switch_percent')} for r in part})
