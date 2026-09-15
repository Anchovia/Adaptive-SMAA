"""Bridge all quality inputs across the material-publication lifetime fix.

PNG byte equality is stronger than the RGB equality required by the prior gate.
Reuse computed quality statistics only after every new input matches the checked
pre-fix capture; do not recompute or silently replace CGVQM scores.
"""
import copy,hashlib,json
from pathlib import Path
from analyze_candidate_selection_gate import ROOT,OUT,HIST,KEYS,paths,read,report,save

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    previous={r['label']:r for r in read(OUT/'pre-publication-fix-runs.json')}
    current={r['label']:r for r in read(OUT/'runs.json')}
    records=[]
    for scene in HIST:
        for mode,count in [('Short',12),('Quality',480)]:
            for key in KEYS:
                label=f'{scene}-{mode}-{key}';old=previous[label];new=current[label]
                for k,v in old['hashes'].items():
                    if k!='CMAA2.exe':assert new['hashes'][k]==v,(label,k)
                assert old['arguments']==new['arguments']
                for r in (old,new):report(r)
                a=paths(old['report'],count);b=paths(new['report'],count);combined=hashlib.sha256()
                for n,(left,right) in enumerate(zip(a,b)):
                    ha,hb=digest(left),digest(right)
                    assert ha==hb,(label,n,'PNG byte bridge failed; keep both files and investigate')
                    combined.update(n.to_bytes(8,'little'));combined.update(bytes.fromhex(ha))
                records.append(dict(label=label,frames=count,png_byte_mismatch=0,sequence_png_sha256=combined.hexdigest(),
                    before=old['report'],after=new['report'],before_exe_sha256=old['hashes']['CMAA2.exe'],after_exe_sha256=new['hashes']['CMAA2.exe']))
                print('PASS:',label,count,flush=True)
    assert len({r['after_exe_sha256'] for r in records})==1
    for key in ('material-publication-1','material-publication-2'):
        t=report(current[key]);assert 'Premature UID visibility, 0,' in t and 'Aggregate: PASS' in t
    result=dict(status='PASS',records=records,full_quality_frames=3840,short_frames=96,
        previous_quality_sha256=digest(OUT/'pre-publication-fix-quality.json'),
        scope='All PNG bytes identical across material publication fix; AA shader sources and capture arguments unchanged.')
    save('publication-bridge.json',result)
    quality=copy.deepcopy(read(OUT/'pre-publication-fix-quality.json'))
    quality['material_publication_fix_bridge']=result
    quality['numerical_metrics_reused_after_png_byte_bridge']=True
    save('quality.json',quality)
    print('PASS: quality evidence revalidated for final executable',flush=True)
if __name__=='__main__':main()
