# Paired timing analysis for cases 20/21 (Adaptive + selected route, Adaptive + case 19).
# Every change is computed per repeat inside one process and then averaged (Student-t 95%).
import json,sys,statistics
sys.path.insert(0,'Tools/SMAA')
import analyze_color_blend_performance as a

runs=json.load(open('tmp/color-blend-preservation-runs.json',encoding='utf-8-sig'))
if isinstance(runs,dict):runs=[runs]
sel={}
for r in runs:
    if r['label']=='c20-t':sel[(r['phase'],r['scene'])]=r
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
VEL=SEL+'+VelocityInEdge'
N='O-T2X-R'
modes={'4':N,'sel':SEL,'19':VEL,'A4':'A-T2X-R','20':'A-'+SEL,'21':'A-'+VEL}
pairs=[('A4','4'),('20','sel'),('21','19'),('sel','4'),('19','4'),('A4','4'),('20','4'),('21','4'),('20','A4'),('21','A4'),('21','20'),('19','sel')]
seen=set();pairs=[p for p in pairs if not (p in seen or seen.add(p))]
METRICS=['SMAA','SF_Spatial','SR_CameraVelocity','SR_Resolve','WholeFrame']
out={}
for (ph,s),r in sorted(sel.items()):
    print(ph,s,r['executable_sha256'][:12],'dirty',r.get('dirty'),r.get('gpu_before'),r['report'][-30:])
    if ph!='Benchmark':continue
    rows=a.rows(r['report'])
    present={k[0] for k in rows};reps=sorted({k[1] for k in rows})
    for k,m in modes.items():assert m in present,(s,k)
    samples={k[2]:v['samples'] for k,v in rows.items() if k[0]==N and k[1]==reps[0]}
    absolute={k:{met:a.ci([rows[(m,i,met)]['mean'] for i in reps]) for met in METRICS} for k,m in modes.items()}
    paired={}
    for x,c in pairs:
        key=f'{x} vs {c}';paired[key]={}
        for met in METRICS:
            pct=[100*(rows[(modes[x],i,met)]['mean']/rows[(modes[c],i,met)]['mean']-1) for i in reps]
            d=[rows[(modes[x],i,met)]['mean']-rows[(modes[c],i,met)]['mean'] for i in reps]
            paired[key][met]=dict(percent=a.ci(pct),delta_ms=a.ci(d))
    out[s]=dict(report=r['report'],executable_sha256=r['executable_sha256'],repeats=len(reps),samples=samples,absolute=absolute,paired=paired)
    print(' repeats',len(reps),'samples',samples.get('SMAA'))
    for k in modes:
        print(f'  {k:>3}',' '.join(f"{met}={absolute[k][met]['mean']:.6f}" for met in METRICS))
    for key,p in paired.items():
        def f(met):
            q=p[met]['percent'];c=q['ci95']
            return f"{met} {q['mean']:+.3f}% [{c[0]:+.3f},{c[1]:+.3f}]"
        print(f'   {key:>10}:',' | '.join(f(m) for m in ['SMAA','SF_Spatial','WholeFrame']))
if len(sys.argv)>1:json.dump(out,open(sys.argv[1],'w',encoding='utf-8'),indent=1)
