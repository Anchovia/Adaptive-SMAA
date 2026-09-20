"""Exact output/mask gate for direct texel access controls."""
import argparse, json
from pathlib import Path
from analyze_temporal_execution import digest, rgb, performance
import numpy as np

MODES=['O-T2X-R','ABL-Contrast-001-R','ABL-Structured-001-R',
       'ABL-LoadCurrent-001-R','ABL-LoadCurrentVelocity-001-R']

def capture(folder,prior):
    names=MODES+['DBG-ContrastMask-001-R','DBG-LoadContrastMask-001-R']
    paths={n:sorted((folder/n).glob('frame_*.png')) for n in names}
    expected=[f'frame_{i:05d}.png' for i in range(240)]
    assert all([p.name for p in ps]==expected for ps in paths.values())
    bridge={n:0 for n in ['O-T2X-R','ABL-Contrast-001-R','ABL-Structured-001-R','DBG-ContrastMask-001-R']}
    comparisons={'ABL-Structured-001-R':0,'ABL-LoadCurrent-001-R':0,'ABL-LoadCurrentVelocity-001-R':0,'DBG-LoadContrastMask-001-R':0}
    counts=[];hashes=[];boundary_mismatch=0
    for i in range(240):
        h={n:digest(paths[n][i]) for n in names};hashes.append(dict(frame=i,sha256=h))
        for n in bridge:bridge[n]+=h[n]!=digest(prior/n/expected[i])
        for n in comparisons:
            control='DBG-ContrastMask-001-R' if 'Mask' in n else 'ABL-Contrast-001-R'
            comparisons[n]+=h[n]!=h[control]
        mask=rgb(paths['DBG-ContrastMask-001-R'][i]);load=rgb(paths['DBG-LoadContrastMask-001-R'][i])
        assert mask.shape==load.shape==(1061,1920,3)
        assert np.all((mask==0)|(mask==255))
        counts.append(int((mask[:,:,0]==255).sum()))
        boundary_mismatch+=int(np.count_nonzero(mask[-1]!=load[-1]))
        boundary_mismatch+=int(np.count_nonzero(mask[:,-1]!=load[:,-1]))
        if i%60==59:print(f'Validated {i+1}/240',flush=True)
    result=dict(source=str(folder),prior=str(prior),bridge_hash_mismatches=bridge,
        output_hash_mismatches=comparisons,bottom_right_boundary_mismatched_channels=boundary_mismatch,
        mean_selected_pixels=float(np.mean(counts)),selected_percent=float(np.mean(counts)/2037120*100),frame_hashes=hashes)
    assert not any(bridge.values()) and not any(comparisons.values()) and boundary_mismatch==0,(bridge,comparisons,boundary_mismatch)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path);p.add_argument('--prior',type=Path)
    p.add_argument('--performance',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();d=capture(a.capture,a.prior) if a.capture else performance(a.performance,MODES)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n')
    print('PASS:',a.output)
