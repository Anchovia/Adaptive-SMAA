"""Fail closed on coverage, execution, native-control, or output mismatch."""
import argparse,csv,hashlib,json,statistics as st,struct
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def image(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(p,im.mode,im.size)
        return np.asarray(im).copy()
def edge(p):
    b=p.read_bytes();assert b[:4]==b'EDG1';w,h=struct.unpack_from('<2I',b,4);assert (w,h)==(1920,1061)
    a=np.frombuffer(b[12:],np.uint8).reshape(h,w,2);assert np.isin(a,[0,255]).all()
    return np.any(a>0,axis=2)
def coverage(p):
    b=p.read_bytes();assert b[:4]==b'DDS ';h,w=struct.unpack_from('<2I',b,12);assert (w,h)==(1920,1061)
    offset=148 if b[84:88]==b'DX10' else 128
    if offset==148:assert struct.unpack_from('<I',b,128)[0]==61 # R8_UNORM
    else:assert struct.unpack_from('<I',b,88)[0]==8
    assert len(b)-offset==w*h
    a=np.frombuffer(b[offset:],np.uint8).reshape(h,w);assert np.isin(a,[0,255]).all()
    return a>0
def read_report(p):
    text=p.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    return [[v.strip() for v in row if v.strip()] for row in csv.reader(text.splitlines()) if row]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scene',required=True,choices=['bistro','minecraft']);ap.add_argument('--report',type=Path,required=True);ap.add_argument('--phase',default='Capture',choices=['Capture','Smoke','Benchmark']);a=ap.parse_args()
    D=R/'Docs/First-Edge-Temporal-Only-Stencil';D.mkdir(parents=True,exist_ok=True)
    FULL='ABL-FirstEdge-TemporalOnly-Full-PatternOff-R';MASK='DIAG-FirstEdge-TemporalOnly-Masked-PatternOff-R';SEL='ABL-FirstEdge-TemporalOnly-Stencil-PatternOff-R';REP=SEL+'-Repeat'
    modes=['O-T2X-R',FULL,MASK,SEL]
    rows=read_report(a.report)
    audit_path=D/'source-audit.json';audit=json.loads(audit_path.read_text())
    assert audit['executable_sha256']==sha(R/'Projects/CMAA2/CMAA2.exe')
    out=dict(scene=a.scene,phase=a.phase,report=str(a.report),report_sha256=sha(a.report),
             source_audit_sha256=sha(audit_path),executable_sha256=audit['executable_sha256'])
    if a.phase!='Capture':
        n=4800 if a.phase=='Benchmark' else 240;nr=4 if a.phase=='Benchmark' else 1
        timing={m:{} for m in modes}
        assert not any(r[0] in ['execution','final_hash','current_hash'] for r in rows)
        for r in rows:
            if r[0]=='timing':
                _,m,run,metric,count,mean,p95,p99,median,std=r
                assert m in modes and int(count)==n
                timing[m].setdefault(metric,[]).append(dict(run=int(run),mean_ms=float(mean),p95_ms=float(p95),p99_ms=float(p99)))
        for m in modes:
            assert set(timing[m])==({'FE_CameraVelocity','FE_Resolve','SMAA','WholeFrame','WallFrame'} | (set() if m=='O-T2X-R' else {'FE_EdgeDetection','FE_Prepare'}))
            for v in timing[m].values():assert sorted(x['run'] for x in v)==list(range(nr))
        means={m:{k:st.mean(x['mean_ms'] for x in v) for k,v in d.items()} for m,d in timing.items()}
        comparisons={control:{k:dict(delta_ms=means[SEL][k]-means[control][k],delta_percent=(means[SEL][k]/means[control][k]-1)*100,paired_percent=[(x['mean_ms']/y['mean_ms']-1)*100 for x,y in zip(timing[SEL][k],timing[control][k])]) for k in means[control]} for control in modes[:-1]}
        out.update(validation='PASS',classification='engineering-timing',frames_per_run=n,repeats=nr,means_ms=means,comparisons=comparisons,timing=timing)
    else:
        cap=Path(next(r[1] for r in rows if r[0]=='capture_root'))
        # The item6 baseline capture includes true AA-Off/1X controls on the same timeline.
        # Earlier item5 captures contain only temporal modes and cannot supply these controls.
        native=R/'Projects/CMAA2/AutoBench'/('20260929_084056' if a.scene=='bistro' else '20260929_084926')
        old=Path('D:/SMAAResearchCaptures/first-edge-pattern-off-20260929/item5')/a.scene/('20260929_112613' if a.scene=='bistro' else '20260929_113212')
        oldsel='ABL-FirstEdge-TemporalOnly-PatternOff-R'
        cm=modes+['AA-Off','O-1X',REP]
        hashes={m:{} for m in cm};current={m:{} for m in [FULL,MASK,SEL]};execution={m:{} for m in modes}
        for r in rows:
            if r[0]=='final_hash':hashes[r[1]][int(r[2])]=r[3]
            if r[0]=='current_hash':current[r[1]][int(r[2])]=r[3]
            if r[0]=='execution':
                assert r[5]=='PASS';execution[r[1]][int(r[2])]=(int(r[3]),int(r[4]))
        for d in [*hashes.values(),*current.values(),*execution.values()]:assert sorted(d)==list(range(240))
        checks=[r for r in rows if r[0]=='mode_check'];assert len(checks)==240*len(cm) and all(r[-1]=='PASS' for r in checks)
        mismatch=dict(native_control_frames=0,prior_selected_frames=0,prior_edge_frames=0,repeat_frames=0,masked_vs_stencil_frames=0,raw_current_pixels=0,selected_pixels=0,nonselected_pixels=0,coverage_pixels=0,sample_count_frames=0,current_frames=0)
        frames=[];rgb=[]
        for i in range(240):
            prefix=f'frame_{i:05d}';ims={m:image(cap/m/(prefix+'.png')) for m in [FULL,MASK,SEL]}
            for m in [FULL,MASK,SEL]:assert sha(cap/m/(prefix+'.png'))==hashes[m][i]
            for m in ['O-T2X-R','AA-Off','O-1X']:mismatch['native_control_frames']+=int(sha(native/m/(prefix+'.png'))!=hashes[m][i])
            mismatch['prior_selected_frames']+=int(sha(old/oldsel/(prefix+'.png'))!=hashes[SEL][i])
            mismatch['prior_edge_frames']+=int(sha(old/oldsel/(prefix+'-edge.rg8'))!=sha(cap/SEL/(prefix+'-edge.rg8')))
            mismatch['repeat_frames']+=int(hashes[REP][i]!=hashes[SEL][i])
            mismatch['masked_vs_stencil_frames']+=int(hashes[MASK][i]!=hashes[SEL][i])
            cur=image(cap/SEL/(prefix+'-current.png'));assert sha(cap/SEL/(prefix+'-current.png'))==current[SEL][i]
            mismatch['current_frames']+=int(not(current[FULL][i]==current[MASK][i]==current[SEL][i]))
            mismatch['raw_current_pixels']+=int(np.any(cur!=image(native/'AA-Off'/(prefix+'.png')),axis=2).sum())
            mask=edge(cap/SEL/(prefix+'-edge.rg8'));cov=coverage(cap/SEL/(prefix+'-coverage.dds'));count=int(mask.sum())
            mismatch['coverage_pixels']+=int(np.count_nonzero(mask!=cov))
            mismatch['sample_count_frames']+=int(execution[SEL][i][1]!=count)
            mismatch['selected_pixels']+=int((np.any(ims[SEL]!=ims[FULL],axis=2)&mask).sum())
            mismatch['nonselected_pixels']+=int((np.any(ims[SEL]!=cur,axis=2)&~mask).sum())
            for m in modes[:-1]:assert execution[m][i][1]==1920*1061,(m,i,execution[m][i])
            assert execution[SEL][i][0]<execution[MASK][i][0],(i,execution[SEL][i],execution[MASK][i])
            if i==0:assert np.array_equal(ims[SEL],cur)
            rgb.append(hashlib.sha256(ims[SEL].tobytes()).hexdigest())
            frames.append(dict(frame=i,edge_count=count,screen_percent=count/(1920*1061)*100,ps_invocations=execution[SEL][i][0],native_ps_invocations=execution['O-T2X-R'][i][0],masked_ps_invocations=execution[MASK][i][0],passing_samples=execution[SEL][i][1]))
            if i%60==59:print(f'{a.scene} {i+1}/240 verified',flush=True)
        out.update(validation='PASS' if sum(mismatch.values())==0 else 'FAIL',mismatches=mismatch,frames=240,pixels_checked=240*1920*1061,capture=str(cap),prior_capture=str(old),native_capture=str(native),
            execution_means={k:st.mean(x[k] for x in frames) for k in frames[0] if k!='frame'},static_unique_rgb=dict(initial=len(set(rgb[20:60])),late=len(set(rgb[200:240]))),
            scope='Exact coverage and output gate; PSInvocations may include helper lanes. No timing claim.')
        (D/f'{a.scene}-frames.json').write_text(json.dumps(frames,indent=2)+'\n')
        assert all(v==1 for v in out['static_unique_rgb'].values()),out
    (D/f'{a.scene}-{a.phase.lower()}.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ['timing']},indent=2),flush=True)
    assert out['validation']=='PASS',out
if __name__=='__main__':main()
