# Paired timing analysis for the eight cases (+19/21). Run from the reprojection-off worktree root.
import json,sys
sys.path.insert(0,'Tools/SMAA')
import analyze_color_blend_performance as a
runs=json.load(open('tmp/color-blend-preservation-runs.json',encoding='utf-8-sig'))
if isinstance(runs,dict):runs=[runs]
sel={(r['phase'],r['scene']):r for r in runs if r['label']=='c23-t'}
SEL='ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
SELOFF=SEL.replace('ET2X-R-','ET2X-')
modes={'O-T2X-R':'O-T2X-R','O-ET2X-R':'ABL-'+SEL,'19':'ABL-'+SEL+'+VelocityInEdge','A-T2X-R':'A-T2X-R','A-ET2X-R':'A-ABL-'+SEL,'21':'A-ABL-'+SEL+'+VelocityInEdge',
       'O-T2X':'O-T2X','O-ET2X':'ABL-'+SELOFF,'A-T2X':'A-T2X','A-ET2X':'A-ABL-'+SELOFF}
pairs=[('O-ET2X-R','O-T2X-R'),('O-ET2X','O-T2X'),('A-ET2X-R','A-T2X-R'),('A-ET2X','A-T2X'),       # temporal axis
       ('A-T2X-R','O-T2X-R'),('A-ET2X-R','O-ET2X-R'),('A-T2X','O-T2X'),('A-ET2X','O-ET2X'),      # spatial axis
       ('O-T2X-R','O-T2X'),('O-ET2X-R','O-ET2X'),('A-T2X-R','A-T2X'),('A-ET2X-R','A-ET2X'),      # reprojection axis
       ('O-T2X','O-T2X-R'),('O-ET2X','O-T2X-R'),('A-T2X','O-T2X-R'),('A-ET2X','O-T2X-R'),('19','O-T2X-R'),('21','O-T2X-R')]
METRICS=['SMAA','SF_Spatial','SR_CameraVelocity','SR_Resolve','WholeFrame']+[f'{m}@{h}' for m in ('SMAA','WholeFrame') for h in ('still','moving')]
out={}
for (ph,s),r in sorted(sel.items()):
    print(ph,s,r['executable_sha256'][:12],r.get('gpu_before'),r['report'][-30:])
    if ph!='Benchmark':continue
    rows=a.rows(r['report']);reps=sorted({k[1] for k in rows})
    absolute={k:{met:a.ci([rows[(m,i,met)]['mean'] for i in reps]) for met in METRICS} for k,m in modes.items()}
    paired={}
    for x,c in pairs:
        key=f'{x} vs {c}';paired[key]={}
        for met in METRICS:
            pct=[100*(rows[(modes[x],i,met)]['mean']/rows[(modes[c],i,met)]['mean']-1) for i in reps]
            d=[rows[(modes[x],i,met)]['mean']-rows[(modes[c],i,met)]['mean'] for i in reps]
            paired[key][met]=dict(percent=a.ci(pct),delta_ms=a.ci(d))
    out[s]=dict(report=r['report'],executable_sha256=r['executable_sha256'],repeats=len(reps),absolute=absolute,paired=paired)
    for k in modes:print(f'  {k:>9}',' '.join(f"{met}={absolute[k][met]['mean']:.6f}" for met in ['SMAA','SMAA@still','SMAA@moving','SR_Resolve','WholeFrame']))
    for key,p in paired.items():
        f=lambda met:f"{met} {p[met]['percent']['mean']:+.3f}% [{p[met]['percent']['ci95'][0]:+.3f},{p[met]['percent']['ci95'][1]:+.3f}]"
        print(f'   {key:>20}:',' | '.join(f(m) for m in ['SMAA','SMAA@still','SMAA@moving','WholeFrame']))
if len(sys.argv)>1:json.dump(out,open(sys.argv[1],'w',encoding='utf-8'),indent=1)
