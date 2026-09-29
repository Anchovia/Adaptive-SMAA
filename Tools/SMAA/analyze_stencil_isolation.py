"""Spatial stencil lifecycle control; no needless MRT in the full-screen control."""
import argparse,hashlib,json,statistics as st
from pathlib import Path
import numpy as np
from analyze_first_edge_stencil import R,read_report,sha,edge,coverage
def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);p.add_argument('--phase',choices=['Capture','Benchmark'],required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    D=R/'Docs/Spatial-First-Edge-Stencil';rows=read_report(a.report)
    FULL='DIAG-Spatial-ExactStencil-FullTemporal-PatternOff-R';SEL='ABL-Spatial-FirstEdge-Stencil-PatternOff-R';REP=SEL+'-Repeat'
    audit=json.loads((D/'source-audit.json').read_text());assert audit['executable_sha256']==sha(R/'Projects/CMAA2/CMAA2.exe')
    out=dict(scene=a.scene,phase=a.phase,report=str(a.report),report_sha256=sha(a.report),executable_sha256=audit['executable_sha256'],source_audit_sha256=sha(D/'source-audit.json'),
             scope='Both paths clear and use exact spatial stencil; only selective path pays retained-output MRT stores. Pattern Off, native temporal math.')
    if a.phase=='Capture':
        prior=json.loads((D/f'{a.scene}-capture.json').read_text());assert prior['validation']=='PASS' and sum(prior['mismatches'].values())==0
        previous=Path(prior['capture']);cap=Path(next(r[1] for r in rows if r[0]=='capture_root'))
        hashes={m:{} for m in [FULL,SEL,REP]};current={m:{} for m in [FULL,SEL]};execution={m:{} for m in [FULL,SEL]}
        for r in rows:
            if r[0]=='final_hash':hashes[r[1]][int(r[2])]=r[3]
            if r[0]=='current_hash':current[r[1]][int(r[2])]=r[3]
            if r[0]=='execution':assert r[-1]=='PASS';execution[r[1]][int(r[2])]=(int(r[3]),int(r[4]))
        for d in [*hashes.values(),*current.values(),*execution.values()]:assert sorted(d)==list(range(240))
        checks=[r for r in rows if r[0]=='mode_check'];assert len(checks)==720 and all(r[-1]=='PASS' for r in checks)
        mismatch=dict(full_output_frames=0,selective_output_frames=0,current_frames=0,edge_frames=0,coverage_pixels=0,execution_frames=0,repeat_frames=0)
        for i in range(240):
            f=f'frame_{i:05d}'
            for m in [FULL,SEL]:assert hashes[m][i]==sha(cap/m/(f+'.png'))
            mismatch['full_output_frames']+=int(hashes[FULL][i]!=sha(previous/'ABL-Spatial-FullTemporal-PatternOff-R'/(f+'.png')))
            mismatch['selective_output_frames']+=int(hashes[SEL][i]!=sha(previous/SEL/(f+'.png')))
            mismatch['current_frames']+=int(not(current[FULL][i]==current[SEL][i]==sha(cap/SEL/(f+'-current.png'))==sha(previous/SEL/(f+'-current.png'))))
            mismatch['edge_frames']+=int(sha(cap/SEL/(f+'-edge.rg8'))!=sha(previous/SEL/(f+'-edge.rg8')))
            mask=edge(cap/SEL/(f+'-edge.rg8'));cov=coverage(cap/SEL/(f+'-coverage.dds'));count=int(mask.sum())
            mismatch['coverage_pixels']+=int(np.count_nonzero(mask!=cov))
            mismatch['execution_frames']+=int(execution[SEL][i]!=(count,count) or execution[FULL][i]!=(1920*1061,1920*1061))
            mismatch['repeat_frames']+=int(hashes[SEL][i]!=hashes[REP][i])
        out.update(validation='PASS' if sum(mismatch.values())==0 else 'FAIL',capture=str(cap),prior_capture=str(previous),prior_validation_sha256=sha(D/f'{a.scene}-capture.json'),mismatches=mismatch,frames=240)
    else:
        gate=json.loads((D/f'{a.scene}-isolation-capture.json').read_text());assert gate['validation']=='PASS' and gate['executable_sha256']==audit['executable_sha256']
        timing={m:{} for m in [FULL,SEL]}
        for r in rows:
            if r[0]=='timing':
                _,m,run,k,n,mean,p95,p99,median,std=r;assert int(n)==4800
                timing[m].setdefault(k,[]).append(dict(run=int(run),mean_ms=float(mean),p95_ms=float(p95),p99_ms=float(p99)))
        for m in timing:
            assert set(timing[m])=={'SF_CameraVelocity','SF_Spatial','SF_Resolve','SMAA','WholeFrame','WallFrame'}
            for v in timing[m].values():assert sorted(x['run'] for x in v)==list(range(4))
        means={m:{k:st.mean(x['mean_ms'] for x in v) for k,v in d.items()} for m,d in timing.items()}
        delta={k:dict(delta_ms=means[SEL][k]-means[FULL][k],delta_percent=(means[SEL][k]/means[FULL][k]-1)*100,paired_percent=[(x['mean_ms']/y['mean_ms']-1)*100 for x,y in zip(timing[SEL][k],timing[FULL][k])]) for k in means[FULL]}
        out.update(validation='PASS',means_ms=means,comparisons=delta,timing=timing,repeats=4,frames_per_run=4800)
    (D/f'{a.scene}-isolation-{a.phase.lower()}.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='timing'},indent=2));assert out['validation']=='PASS',out
if __name__=='__main__':main()
