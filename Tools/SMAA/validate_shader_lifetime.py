"""Validate completed lifetime reports and pixel-exact seven-mode capture bridges."""
import argparse, hashlib, json
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def report(path):
    text=path.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[s for s in text.splitlines() if s.startswith('pending-owner-release,')]
    assert len(rows)==32
    assert [int(s.split(',')[1]) for s in rows]==list(range(32))
    for name in ['material-publish-after-initialization','six-stage-shared-and-auto-factories','real-ps-cs-immediate-release-and-reload']:
        assert name+', PASS' in text
    return dict(path=str(path),sha256=sha(path),pending_release_checks=32)

def bridge(new,prior):
    modes=['O-T2X-R','ABL-Contrast-001-R','ABL-Structured-001-R','ABL-LoadCurrent-001-R',
           'ABL-LoadCurrentVelocity-001-R','DBG-ContrastMask-001-R','DBG-LoadContrastMask-001-R']
    expected=[f'frame_{i:05d}.png' for i in range(240)]
    hashes={}; mismatches={}
    for mode in modes:
        a=sorted((new/mode).glob('frame_*.png'));b=sorted((prior/mode).glob('frame_*.png'))
        assert [p.name for p in a]==[p.name for p in b]==expected
        ha=[sha(p) for p in a];hb=[sha(p) for p in b]
        mismatches[mode]=sum(x!=y for x,y in zip(ha,hb))
        hashes[mode]=hashlib.sha256(''.join(ha).encode()).hexdigest()
    assert not any(mismatches.values()),mismatches
    return dict(source=str(new),prior=str(prior),frames_per_mode=240,
        hash_mismatches=mismatches,sequence_sha256=hashes)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,action='append',default=[])
    p.add_argument('--capture',type=Path);p.add_argument('--prior',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result={'reports':[report(r) for r in a.report]}
    if a.capture:result['capture']=bridge(a.capture,a.prior)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS:',a.output)
