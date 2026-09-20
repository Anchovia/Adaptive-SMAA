"""Compare cost optimizations against the unchanged per-pixel contrast output."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
from analyze_temporal_execution import performance

MODES=['O-T2X-R','ABL-Contrast-001-R','ABL-Flatten-001-R','ABL-ScalarWeight-001-R',
       'ABL-ScalarReassociated-001-R','ABL-BranchReassociated-001-R','ABL-HistoryLoad-001-R',
       'ABL-SelectorAny-001-R','ABL-FixedThreshold-001-R','ABL-ScalarFixedThreshold-001-R']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rgb(p):
    with Image.open(p) as im:return np.array(im.convert('RGB'))
def capture(folder,prior):
    names=MODES+['DBG-ContrastMask-001-R']
    seq={n:sorted((folder/n).glob('frame_*.png')) for n in names}
    assert all([p.name for p in s]==[f'frame_{i:05}.png' for i in range(240)] for s in seq.values())
    bridges={n:0 for n in ['O-T2X-R','ABL-Contrast-001-R','DBG-ContrastMask-001-R']}
    results={n:dict(hash_mismatch_frames=0,changed_pixels=0,max_channel_error=0,absolute_channel_error_sum=0,noncandidate_changed_pixels=0)
             for n in MODES[2:]}
    hashes={n:[] for n in names};selected=[]
    for i in range(240):
        h={n:digest(seq[n][i]) for n in names}
        for n in names:hashes[n].append(h[n])
        for n in bridges:
            bridges[n]+=h[n]!=digest(prior/n/seq[n][i].name)
        mask=rgb(seq['DBG-ContrastMask-001-R'][i])
        assert mask.shape==(1061,1920,3) and np.all((mask==0)|(mask==255))
        selected.append(int((mask[:,:,0]==255).sum()))
        original=rgb(seq['ABL-Contrast-001-R'][i]);assert original.shape==(1061,1920,3)
        for n,s in results.items():
            if h[n]==h['ABL-Contrast-001-R']:continue
            s['hash_mismatch_frames']+=1
            actual=rgb(seq[n][i]);assert actual.shape==original.shape
            delta=np.abs(actual.astype(np.int16)-original.astype(np.int16))
            changed=np.any(delta!=0,axis=2)
            s['changed_pixels']+=int(changed.sum())
            s['noncandidate_changed_pixels']+=int((changed&(mask[:,:,0]==0)).sum())
            s['max_channel_error']=max(s['max_channel_error'],int(delta.max()))
            s['absolute_channel_error_sum']+=int(delta.sum())
        if i%60==59:print(f'Validated {i+1}/240 frames',flush=True)
    assert not any(bridges.values()),bridges
    assert results['ABL-Flatten-001-R']['hash_mismatch_frames']==0
    for s in results.values():
        s['rgb_mae_0_255']=s['absolute_channel_error_sum']/(240*1920*1061*3)
        s['exact_output']=s['changed_pixels']==0
    return dict(capture=str(folder),prior=str(prior),frames=240,mode_count=len(names),
        prior_hash_mismatches=bridges,variants=results,selected_percent=float(np.mean(selected)/2037120*100),
        sequence_sha256={n:hashlib.sha256(''.join(h).encode()).hexdigest() for n,h in hashes.items()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path);p.add_argument('--prior',type=Path)
    p.add_argument('--performance',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();d=capture(a.capture,a.prior) if a.capture else performance(a.performance,MODES)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n')
    print('Completed:',a.output)
    if a.capture:print(json.dumps(d['variants'],indent=2))
