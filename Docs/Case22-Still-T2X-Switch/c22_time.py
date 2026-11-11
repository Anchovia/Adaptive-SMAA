# Paired timing analysis for case 22 next to case 4, the selected route and case 19.
# Changes are computed per repeat inside one process and averaged (Student-t 95%).
# Run from the case 22 worktree root.
import json,sys
sys.path.insert(0,'Tools/SMAA')
import analyze_color_blend_performance as a

runs=json.load(open('tmp/color-blend-preservation-runs.json',encoding='utf-8-sig'))
if isinstance(runs,dict):runs=[runs]
sel={(r['phase'],r['scene']):r for r in runs if r['label']=='c22-t'}
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
modes={'4':'O-T2X-R','sel':SEL,'19':SEL+'+VelocityInEdge','22':'SWITCH-StillO-T2X-R-N4+MovingSelected'}
pairs=[('sel','4'),('19','4'),('22','4'),('22','sel'),('22','19')]
METRICS=['SMAA','SF_Spatial','SR_CameraVelocity','SR_Resolve','WholeFrame']+[f'{m}@{h}' for m in ('SMAA','SF_Spatial','SR_Resolve','WholeFrame') for h in ('still','moving')]
out={}
for (ph,s),r in sorted(sel.items()):
    print(ph,s,r['executable_sha256'][:12],r.get('gpu_before'),r['report'][-30:])
    if ph!='Benchmark':continue
    rows=a.rows(r['report']);reps=sorted({k[1] for k in rows})
    for k,m in modes.items():assert any(x[0]==m for x in rows),(s,k)
    absolute={k:{met:a.ci([rows[(m,i,met)]['mean'] for i in reps]) for met in METRICS} for k,m in modes.items()}
    paired={}
    for x,c in pairs:
        key=f'{x} vs {c}';paired[key]={}
        for met in METRICS:
            pct=[100*(rows[(modes[x],i,met)]['mean']/rows[(modes[c],i,met)]['mean']-1) for i in reps]
            d=[rows[(modes[x],i,met)]['mean']-rows[(modes[c],i,met)]['mean'] for i in reps]
            paired[key][met]=dict(percent=a.ci(pct),delta_ms=a.ci(d))
    out[s]=dict(report=r['report'],executable_sha256=r['executable_sha256'],repeats=len(reps),absolute=absolute,paired=paired)
    for k in modes:print(f'  {k:>3}',' '.join(f"{met}={absolute[k][met]['mean']:.6f}" for met in METRICS if '@' not in met));print('      ',' '.join(f"{met}={absolute[k][met]['mean']:.6f}" for met in METRICS if '@' in met))
    for key,p in paired.items():
        f=lambda met:f"{met} {p[met]['percent']['mean']:+.3f}% [{p[met]['percent']['ci95'][0]:+.3f},{p[met]['percent']['ci95'][1]:+.3f}]"
        print(f'   {key:>10}:',' | '.join(f(m) for m in ['SMAA','SF_Spatial','SR_Resolve','WholeFrame']))
        print(f'   {"":>10}  ',' | '.join(f(m) for m in ['SMAA@still','SMAA@moving','WholeFrame@still','WholeFrame@moving']))
if len(sys.argv)>1:json.dump(out,open(sys.argv[1],'w',encoding='utf-8'),indent=1)
