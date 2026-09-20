"""Same-output warp execution gate. Mask coverage is from the diagnostic PS."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from analyze_temporal_execution import performance,rgb,digest
MODES=['ABL-Contrast-001-R','O-T2X-R','ABL-NvWarp-001-R','ABL-ScalarWeight-001-R']
def capture(folder,prior):
    names=MODES+['DBG-ContrastMask-001-R','DBG-NvWarpMask-001-R']
    seq={n:sorted((folder/n).glob('frame_*.png')) for n in names}
    assert all([p.name for p in s]==[f'frame_{i:05}.png' for i in range(240)] for s in seq.values())
    bridges={n:0 for n in ('O-T2X-R','ABL-Contrast-001-R','ABL-ScalarWeight-001-R','DBG-ContrastMask-001-R')}
    matches={n:0 for n in ('ABL-NvWarp-001-R','ABL-ScalarWeight-001-R')}
    hashes={n:[] for n in names};coverage=[]
    for i in range(240):
        h={n:digest(seq[n][i]) for n in names}
        for n in names:hashes[n].append(h[n])
        for n in bridges:bridges[n]+=h[n]!=digest(prior/n/seq[n][i].name)
        for n in matches:matches[n]+=h[n]!=h['ABL-Contrast-001-R']
        mask=rgb(seq['DBG-ContrastMask-001-R'][i]);warp=rgb(seq['DBG-NvWarpMask-001-R'][i])
        assert mask.shape==warp.shape==(1061,1920,3)
        assert np.all((mask==0)|(mask==255)) and np.all((warp==0)|(warp==255))
        assert np.array_equal(mask[:,:,0],warp[:,:,0]),'Pixel selection changed'
        assert np.all(warp[:,:,1]>=warp[:,:,0]) and np.all(warp[:,:,2]==0)
        coverage.append(dict(frame=i,selected=int((mask[:,:,0]==255).sum()),vote_covered=int((warp[:,:,1]==255).sum())))
        if i%60==59:print(f'Validated {i+1}/240',flush=True)
    assert not any(bridges.values()),bridges
    assert not any(matches.values()),matches
    return dict(capture=str(folder),prior=str(prior),frames=240,modes=6,prior_hash_mismatches=bridges,
        output_hash_mismatches=matches,selected_percent=float(np.mean([x['selected'] for x in coverage])/2037120*100),
        diagnostic_vote_coverage_percent=float(np.mean([x['vote_covered'] for x in coverage])/2037120*100),
        coverage_note='Actual NvAny result in separate diagnostic PS, not a timing-run hardware counter or guaranteed resolve lane mapping.',
        coverage=coverage,sequence_sha256={n:hashlib.sha256(''.join(h).encode()).hexdigest() for n,h in hashes.items()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path);p.add_argument('--prior',type=Path)
    p.add_argument('--performance',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.capture:d=capture(a.capture,a.prior)
    else:
        text=a.performance.read_text(encoding='utf-8-sig')
        assert 'NVAPI VOTE_ANY supported: 1' in text and 'Focused preconditioning elapsed seconds:' in text
        d=performance(a.performance,MODES,repeats=5);d.pop('distributions',None)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n')
    print('PASS:',a.output)
