"""Shared fixed-screen-strip output contrast; not temporal ground truth or tracking."""
import csv,json
from pathlib import Path
import numpy as np
from analyze_case13_quality import DOC,MODES,load,weight
from edge_quality_inputs import rgb,dds

def main():
    evidence=load(DOC/'minecraft-capture.json');cap=Path(evidence['capture_root'])
    rows=[];luma=np.array([.2126,.7152,.0722],np.float32)
    for frame in range(126,139):
        current=dds(cap/MODES[3]/f'frame_{frame:05d}-current.dds')
        x=int(np.argmin((current[578:612,966:984,:3].astype(np.float32)@luma).mean(axis=0)))+966
        def contrast(a):
            lum=a[578:612,x-3:x+4,:3].astype(np.float32)@luma
            return float((.5*(lum[:,0]+lum[:,6])-lum[:,3]).mean())
        for case,mode in zip([4,10,11,13],MODES):
            out=rgb(cap/mode/f'frame_{frame:05d}.png');coverage=wf=None
            if case!=4:
                coverage=dds(cap/mode/f'frame_{frame:05d}-coverage.dds')>0
                wf=weight(cap/mode/f'frame_{frame:05d}-weight.dds')
            rows.append(dict(frame=frame,case=case,mode=mode,column=x,
                spatial_contrast=contrast(current),output_contrast=contrast(out),
                selected_line_pixels=None if coverage is None else int(coverage[578:612,x].sum()),
                mean_line_history_weight=None if wf is None else float(wf[578:612,x].mean())))
    with (DOC/'minecraft-line-contrast.csv').open('w',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[]
    for case in [4,10,11,13]:
        v=np.array([r['output_contrast'] for r in rows if r['case']==case])
        summary.append(dict(case=case,mean_contrast=float(v.mean()),min=float(v.min()),
            max=float(v.max()),std=float(v.std()),adjacent_difference=float(np.abs(np.diff(v)).mean())))
    result=dict(classification='Shared fixed screen strip; encoded luma contrast only. Not object tracking, reference ground truth, or standalone quality score.',
        strip=dict(x_search=[966,983],y=[578,611],column='minimum mean CURRENT SPATIAL luma; shared across output modes',background='column +-3'),
        frames=[126,138],rows=rows,summary=summary)
    (DOC/'minecraft-line-contrast.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS actual-output strip',json.dumps(summary))

if __name__=='__main__':main()
