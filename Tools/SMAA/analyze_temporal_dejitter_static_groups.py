"""Locate static two-phase regression without changing the selector or shader."""
import json
from pathlib import Path
import numpy as np
from analyze_temporal_dejitter import rgb, MASK, DMASK, SCALAR, SLINEAR

root=Path(__file__).resolve().parents[2]
out=root/'Docs/Temporal-DeJitter'
result={}
for scene in ('bistro','minecraft'):
    q=json.loads((out/f'{scene}-quality.json').read_text(encoding='utf-8'))
    assert all(v['lag2_mismatches']==0 for v in q['static_hashes']['late_still'].values())
    capture=Path(q['receipt']['report']).parent
    masks={m:[rgb(capture/m/f'frame_{i:05d}.png')[:,:,0]==255 for i in (200,201)] for m in (MASK,DMASK)}
    both_selected=np.logical_and.reduce([*masks[MASK],*masks[DMASK]])
    both_unselected=np.logical_and.reduce([~m for m in (*masks[MASK],*masks[DMASK])])
    groups={'selected_in_both_methods_both_phases':both_selected,
            'unselected_in_both_methods_both_phases':both_unselected,
            'other_selection_changes':~(both_selected|both_unselected)}
    deltas={}
    for mode in (SCALAR,SLINEAR):
        images=[rgb(capture/mode/f'frame_{i:05d}.png').astype(np.int16) for i in (200,201)]
        deltas[mode]=np.abs(images[0]-images[1]).mean(axis=2)
    rows=[]
    for name,mask in groups.items():
        row=dict(group=name,pixel_count=int(mask.sum()),pixel_percent=float(mask.mean()*100))
        for mode,d in deltas.items():
            row[mode]=dict(conditional_rgb_step=float(d[mask].mean()) if mask.any() else 0,
                          full_frame_rgb_step_contribution=float(d[mask].sum()/mask.size))
        rows.append(row)
    for mode,d in deltas.items():
        assert abs(sum(r[mode]['full_frame_rgb_step_contribution'] for r in rows)-float(d.mean()))<1e-12
    result[scene]=dict(frames=[200,201],groups=rows,
        scope='Screen-fixed pixel classes across two measured phases; classification is descriptive, not a new selection rule')
(out/'static-groups.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
