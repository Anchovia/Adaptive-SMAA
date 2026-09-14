"""Verify source execution relocation without treating candidate list order as semantic.

GPU snapshot reports validate mask/list sets, bounds and actual dispatch args.
Dynamic PNGs validate selected masks and final byte-exact output independently.
"""
import argparse,csv,hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image

def images(root):
    paths=sorted(Path(root).rglob('*.png'))
    result={}
    for p in paths:
        match=re.search(r'_profile_(\d+)_frame_(\d+)\.png$',p.name)
        assert match,p
        key=tuple(map(int,match.groups()));assert key not in result
        result[key]=hashlib.sha256(p.read_bytes()).hexdigest()
    assert result and list(result)==[(i,i) for i in range(len(result))],root
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    runs=json.loads(a.manifest.read_text(encoding='utf-8-sig'));by={x['label']:x for x in runs}
    results=[]
    for kind in ('ShortQuality','Quality','Masks'):
        for scene in ('bistro','minecraft'):
            keys=[f'{scene}-{kind}-source-{i}' for i in (0,1)]
            if not all(k in by for k in keys):continue
            seq=[images(by[k]['report']) for k in keys]
            assert seq[0].keys()==seq[1].keys()
            mismatch=sum(seq[0][k]!=seq[1][k] for k in seq[0]);assert mismatch==0,(keys,mismatch)
            row=dict(scene=scene,kind=kind,frames=len(seq[0]),png_sha256_mismatch=mismatch,runs=[by[k] for k in keys])
            if kind=='Quality':
                priorID={'bistro':'20260914_142836','minecraft':'20260914_143331'}[scene]
                prior=Path(by[keys[0]]['report']).parent/priorID
                previous=images(prior);assert previous==seq[1],(scene,'prior source changed')
                row.update(prior_source_report=str(prior),prior_source_png_sha256_mismatch=0)
            results.append(row)
    snap=by['snapshot'];reports=list(Path(snap['report']).glob('*_results.csv'));assert len(reports)==1
    text=reports[0].read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[]
    for row in csv.reader(text.splitlines()):
        row=[x.strip() for x in row]
        if len(row)>11 and row[0] in ('Bistro','Minecraft'):
            assert row[11]=='PASS'
            values=list(map(int,row[2:11]));count,process,base,groups,*errors=values
            assert count==process and count<=base and groups==(count+63)//64 and not any(errors)
            rows.append(dict(scene=row[0],execution=row[1],candidates=count,base=base,groups=groups))
    assert len(rows)==14
    assert results,'No completed dynamic pairs'
    preservation=[]
    for scene in ('bistro','minecraft'):
        keys=[f'{scene}-Masks-source-1',f'{scene}-ShortQuality-source-1',f'{scene}-ShortQuality-O-1X']
        if not all(k in by for k in keys):continue
        seq=[sorted(Path(by[k]['report']).rglob('*.png')) for k in keys]
        assert len(seq[0])==len(seq[1])==len(seq[2])>0
        mismatch=0
        for paths in zip(*seq):
            mask,final,spatial=[np.asarray(Image.open(p).convert('RGB')) for p in paths]
            assert np.all((mask==0)|(mask==255))
            assert np.array_equal(mask[:,:,0],mask[:,:,1]) and np.array_equal(mask[:,:,0],mask[:,:,2])
            mismatch+=int(np.count_nonzero(np.any(final!=spatial,axis=-1)&(mask[:,:,0]==0)))
        assert mismatch==0
        preservation.append(dict(scene=scene,frames=len(seq[0]),noncandidate_spatial_mismatch_pixels=mismatch))
    output=dict(validation='PASS',classification='Execution relocation correctness, not quality or speed',dynamic_pairs=results,snapshot=snap,snapshot_rows=rows,noncandidate_preservation=preservation)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(output,indent=2))
    print(json.dumps(dict(validation='PASS',snapshot_steps=len(rows),dynamic_pairs=[{k:r[k] for k in ('scene','kind','frames','png_sha256_mismatch')} for r in results])))
if __name__=='__main__':main()
