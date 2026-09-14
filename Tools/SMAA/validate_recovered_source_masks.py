"""Same-frame noncandidate preservation and old/new candidate set comparison."""
import argparse,json,re
from pathlib import Path
import numpy as np
from PIL import Image

def collect(root):
    paths=sorted(Path(root).rglob('*.png'))
    indices=[tuple(map(int,re.search(r'_profile_(\d+)_frame_(\d+)\.png$',p.name).groups())) for p in paths]
    assert indices==[(i,i) for i in range(len(paths))]
    return paths
def read(p):return np.asarray(Image.open(p).convert('RGB'))
def main():
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    runs={x['label']:x for x in json.loads(a.manifest.read_text(encoding='utf-8-sig'))};result={}
    for scene in ['bistro','minecraft']:
        masks=[collect(runs[f'{scene}-mask-{i}']['report']) for i in range(2)]
        controls=collect(runs[f'{scene}-spatial-control']['report'])
        finals=[collect(runs[f'{scene}-profile-{i}']['report']) for i in range(4)]
        n=len(masks[0]);assert n==len(masks[1]) and 0<n<=len(controls)
        totals=np.zeros(6,dtype=np.int64);mismatches=np.zeros(4,dtype=np.int64)
        for frame in range(n):
            raw=[read(m[frame]) for m in masks]
            assert all(np.all((v==0)|(v==255)) for v in raw)
            assert all(np.array_equal(v[:,:,0],v[:,:,1]) and np.array_equal(v[:,:,1],v[:,:,2]) for v in raw)
            old,new=[v[:,:,0]>0 for v in raw];spatial=read(controls[frame])
            totals+=np.array([old.sum(),new.sum(),(old&new).sum(),(old|new).sum(),(new&~old).sum(),(old&~new).sum()])
            for i in range(4):
                image=read(finals[i][frame]);mask=new if i&1 else old
                mismatches[i]+=np.count_nonzero(np.any(image!=spatial,axis=-1)&~mask)
        assert not mismatches.any(),(scene,mismatches)
        result[scene]={'frames':n,'noncandidate_spatial_mismatch_pixels':mismatches.tolist(),
            'mean_document_candidates':float(totals[0]/n),'mean_source_candidates':float(totals[1]/n),
            'candidate_set_jaccard':float(totals[2]/max(totals[3],1)),
            'source_added_per_frame':float(totals[4]/n),'source_removed_per_frame':float(totals[5]/n),
            'mask_reports':[runs[f'{scene}-mask-{i}']['report'] for i in range(2)]}
        print(scene,result[scene],flush=True)
    a.output.write_text(json.dumps({'passed':True,'scenes':result},indent=2))
if __name__=='__main__':main()
