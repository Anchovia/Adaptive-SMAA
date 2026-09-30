"""Validate same-output controls and paired cost decomposition (no quality claim)."""
import argparse,csv,hashlib,json,statistics
from pathlib import Path
from PIL import Image
import numpy as np
from analyze_first_edge_stencil import coverage

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-Persistence-Cost-Audit'
MODES=['A-CurrentEdge-Stencil','S-StorageOnly-Stencil','K-ConstantDepth-Stencil',
       'D-CurrentEdge-Depth','P-UnionPrep-Stencil','B-PreviousRawEdge-Depth',
       'L-PreviousRawEdge-ConservativeDepth','E-PreviousRawEdge-FirstStencil','O-T2X-R']
OLD={'bistro':Path('D:/SMAAResearchCaptures/edge-persistence-gpu-20261001/capture/bistro/20261001_013254'),
     'minecraft':Path('D:/SMAAResearchCaptures/edge-persistence-gpu-20261001/capture/minecraft/20261001_013740')}
def pixel_hash(p):
    with Image.open(p) as im:
        assert im.size==(1920,1061),(p,im.size)
        return hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scene',choices=list(OLD),required=True)
    ap.add_argument('--phase',choices=['Test','Capture','Smoke','Benchmark'],required=True)
    args=ap.parse_args();records=json.loads((ROOT/'tmp/edge-persistence-cost-audit-runs.json').read_text(encoding='utf-8-sig'))
    record=[r for r in records if r['phase']==args.phase and r['scene']==args.scene][-1]
    report=Path(record['report']);raw=report.read_text();assert 'Aggregate: PASS' in raw and 'FAIL' not in raw
    rows=[[c.strip() for c in r] for r in csv.reader(raw.splitlines())]
    result={'receipt':record,'classification':'controlled-cost-audit; not new quality measurement'}
    if args.phase in ('Test','Capture'):
        base=Path(next(r[1] for r in rows if r and r[0]=='capture_root'))
        n=6 if args.phase=='Test' else 240; hashes={}
        capture_modes=MODES if args.phase=='Test' else [MODES[i] for i in [0,5,7,8]]
        for mode in capture_modes:
            files=sorted((base/mode).glob('frame_[0-9][0-9][0-9][0-9][0-9].png'))
            assert len(files)==n,(mode,len(files));hashes[mode]=[pixel_hash(p) for p in files]
        comparisons={}
        for mode in MODES[1:5]:
            if mode in hashes:comparisons[mode+' vs A']=sum(a!=b for a,b in zip(hashes[mode],hashes[MODES[0]]))
        if MODES[6] in hashes:comparisons['L vs B']=sum(a!=b for a,b in zip(hashes[MODES[6]],hashes[MODES[5]]))
        comparisons['E vs B']=sum(a!=b for a,b in zip(hashes[MODES[7]],hashes[MODES[5]]))
        for mode,old in [(MODES[0],'ABL-Spatial-FirstEdge-Stencil-PatternOff-R'),(MODES[5],'ABL-Spatial-PreviousRawEdge-Depth-PatternOff-R'),(MODES[8],'O-T2X-R')]:
            oldh=[pixel_hash(OLD[args.scene]/old/f'frame_{i:05d}.png') for i in range(n)]
            comparisons[mode+' vs preserved original']=sum(a!=b for a,b in zip(hashes[mode],oldh))
        assert all(v==0 for v in comparisons.values()),comparisons
        traces=[r for r in rows if r and r[0]=='trace'];assert traces and all(r[5]=='PASS' for r in traces)
        trace_by_mode={m:{int(r[2]):r for r in traces if r[1]==m} for m in [MODES[0],MODES[5],MODES[7]]}
        trace_checks=[]
        for i,r in trace_by_mode[MODES[7]].items():
            stem=f'frame_{i:05d}';bdir=base/MODES[5];edir=base/MODES[7];adir=base/MODES[0]
            bmask=coverage(bdir/(stem+'-coverage.dds'));emask=coverage(edir/(stem+'-coverage.dds'))
            assert np.array_equal(bmask,emask),(i,'coverage mismatch')
            passing=int(emask.sum());assert passing==int(r[4]) and passing==int(trace_by_mode[MODES[5]][i][4])
            assert passing<=int(r[3])<1920*1061,(i,'early rejection not verified',r)
            for suffix in ['-edge.rg8','-current.dds']:
                assert (edir/(stem+suffix)).read_bytes()==(bdir/(stem+suffix)).read_bytes(),(i,suffix)
                assert (edir/(stem+suffix)).read_bytes()==(adir/(stem+suffix)).read_bytes(),(i,suffix,'baseline')
            with Image.open(edir/(stem+'.png')) as im:final=np.asarray(im.convert('RGB'))
            with Image.open(edir/(stem+'-current.png')) as im:current=np.asarray(im.convert('RGB'))
            assert not np.any(final[~emask]!=current[~emask]),(i,'nonselected changed')
            trace_checks.append(dict(frame=i,passing_samples=passing,baseline_samples=int(trace_by_mode[MODES[0]][i][4]),fix_ps_invocations=int(r[3]),old_depth_ps_invocations=int(trace_by_mode[MODES[5]][i][3])))
        checks=[r for r in rows if r and r[0]=='mode_check'];assert len(checks)==n*len(capture_modes)
        result.update(capture_root=str(base),frames_per_mode=n,compared_modes=capture_modes,mismatched_frames=comparisons,trace_count=len(traces),selection_validation=trace_checks,output_hashes=hashes)
    else:
        runs={m:{} for m in MODES};seen=set();count=1 if args.phase=='Smoke' else 3;n=240 if count==1 else 4800
        for r in rows:
            if not r or r[0]!='timing':continue
            _,mode,run,metric,samples,mean,*_=r
            assert mode in MODES and int(samples)==n
            key=(mode,int(run),metric);assert key not in seen and int(run) in range(count);seen.add(key)
            runs[mode].setdefault(metric,[]).append(float(mean))
        for mode,metrics in runs.items():
            assert len(metrics)==6,(mode,metrics)
            assert all(len(v)==count for v in metrics.values()),mode
        means={m:{k:statistics.mean(v) for k,v in metrics.items()} for m,metrics in runs.items()}
        pairs={}
        for a,b in [('S-StorageOnly-Stencil','A-CurrentEdge-Stencil'),('K-ConstantDepth-Stencil','S-StorageOnly-Stencil'),('D-CurrentEdge-Depth','K-ConstantDepth-Stencil'),('P-UnionPrep-Stencil','K-ConstantDepth-Stencil'),('B-PreviousRawEdge-Depth','P-UnionPrep-Stencil'),('L-PreviousRawEdge-ConservativeDepth','B-PreviousRawEdge-Depth')]:
            pairs[a+' minus '+b]={k:means[a][k]-means[b][k] for k in means[a]}
        comparisons={}
        for baseline in [MODES[0],MODES[5],'O-T2X-R']:
            comparisons[baseline]={}
            for mode in MODES:
                comparisons[baseline][mode]={}
                for metric in means[mode]:
                    percentages=[100*(a/b-1) for a,b in zip(runs[mode][metric],runs[baseline][metric])]
                    comparisons[baseline][mode][metric]=dict(delta_ms=means[mode][metric]-means[baseline][metric],percent=100*(means[mode][metric]/means[baseline][metric]-1),paired_run_percent=percentages)
        result.update(runs=runs,means=means,differences_ms=pairs,comparisons=comparisons)
        for mode in MODES:
            v=means[mode];print(mode, 'AA %.6f spatial %.6f temporal %.6f native %+.2f%%'%(v['SMAA'],v['SF_Spatial'],v['SR_Resolve'],100*(v['SMAA']/means['O-T2X-R']['SMAA']-1)))
    DOC.mkdir(exist_ok=True);out=DOC/(args.scene+'-'+args.phase.lower()+'.json');out.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',args.scene,args.phase,str(out))
if __name__=='__main__':main()
