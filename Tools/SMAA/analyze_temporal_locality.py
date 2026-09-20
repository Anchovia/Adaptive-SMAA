"""Validate synthetic output identity and report timestamp controls, not hardware counters."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from analyze_temporal_execution import performance

MODES=['O-T2X-R','ABL-Contrast-All-R','ABL-Contrast-001-R',
       'DIAG-Stripe1-Branch-R','DIAG-Stripe32-Branch-R',
       'DIAG-Stripe1-Flatten-R','DIAG-Stripe32-Flatten-R']

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rgb(p):
    with Image.open(p) as im: return np.array(im.convert('RGB'))

def capture(folder, prior):
    names=MODES+['DBG-CurrentSpatial-R','DBG-ContrastMask-001-R']
    paths={n:sorted((folder/n).glob('frame_*.png')) for n in names}
    assert all([p.name for p in seq]==[f'frame_{i:05}.png' for i in range(240)] for seq in paths.values())
    bridges={n:0 for n in ['O-T2X-R','ABL-Contrast-001-R','DBG-ContrastMask-001-R']}
    # The prior dependency capture has these three formal controls; current-spatial
    # is validated per pixel below using the initial capture separately if supplied.
    mismatch={n:0 for n in MODES[3:]}
    pair_mismatch={'1':0,'32':0}; selected=[]; all_mismatch=0
    manifests=[]
    for i in range(240):
        hashes={n:digest(paths[n][i]) for n in names}
        manifests.append(hashes)
        for n in bridges: bridges[n]+=hashes[n]!=digest(prior/n/paths[n][i].name)
        all_mismatch+=hashes['O-T2X-R']!=hashes['ABL-Contrast-All-R']
        current=rgb(paths['DBG-CurrentSpatial-R'][i]);native=rgb(paths['O-T2X-R'][i])
        assert current.shape==native.shape==(1061,1920,3)
        for width,shift in [(1,0),(32,5)]:
            mask=((np.arange(1920,dtype=np.uint32)>>shift)&1)==0
            assert int(mask.sum())==960
            expected=np.where(mask[None,:,None],native,current)
            for style in ('Branch','Flatten'):
                n=f'DIAG-Stripe{width}-{style}-R'
                actual=rgb(paths[n][i]);assert actual.shape==expected.shape
                mismatch[n]+=int(np.any(actual!=expected,axis=2).sum())
            pair_mismatch[str(width)]+=hashes[f'DIAG-Stripe{width}-Branch-R']!=hashes[f'DIAG-Stripe{width}-Flatten-R']
        mask=rgb(paths['DBG-ContrastMask-001-R'][i])
        assert np.all(mask[:,:,0]==mask[:,:,1]) and np.all(mask[:,:,0]==mask[:,:,2])
        assert np.all((mask==0)|(mask==255))
        selected.append(int((mask[:,:,0]==255).sum()))
        if i%60==59: print(f'Validated {i+1}/240 frames',flush=True)
    assert all(v==0 for v in bridges.values()),bridges
    assert all_mismatch==0
    assert all(v==0 for v in mismatch.values()),mismatch
    assert all(v==0 for v in pair_mismatch.values()),pair_mismatch
    return dict(capture=str(folder),prior=str(prior),frames=240,mode_count=len(names),
        prior_hash_mismatch=bridges,all_selected_hash_mismatch=all_mismatch,
        synthetic_wrong_pixels=mismatch,branch_flatten_hash_mismatch=pair_mismatch,
        synthetic_selected_pixels=1018560,synthetic_selected_percent=50,
        contrast_selected_mean=float(np.mean(selected)),contrast_selected_percent=float(np.mean(selected)/2037120*100),
        sequence_sha256={n:hashlib.sha256(''.join(x[n] for x in manifests).encode()).hexdigest() for n in names})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path);p.add_argument('--prior',type=Path)
    p.add_argument('--performance',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    data=capture(a.capture,a.prior) if a.capture else performance(a.performance,MODES)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,indent=2)+'\n')
    print('PASS:',a.output)
