"""Validate case19 timing reports and compute same-process paired changes."""
import argparse, collections, csv, hashlib, json, math, re
from pathlib import Path
from analyze_color_blend_performance import rows, summarize, ci
from verify_case19_spatial import MODES, CASE18
METRICS={'SMAA','SF_Spatial','SR_CameraVelocity','SR_Resolve','WholeFrame','WallFrame'}
def analyze(receipt):
    phase=receipt['phase']
    frames,repeats={'Smoke':(240,1),'Benchmark':(4800,6),'Profile':(2400,3)}[phase]
    path=Path(receipt['report']);body=path.read_text(encoding='utf-8-sig')
    if hashlib.sha256(path.read_bytes()).hexdigest().upper()!=receipt['report_sha256'].upper():raise ValueError('Report SHA mismatch')
    for required in ['Case19 spatial cost matrix','PNG/query/readback Off' if phase!='Profile' else 'diagnostic per-pass GPU timers On','API:  DirectX11','Vsync:        OFF','Fullscreen:   Windowed']:
        if required not in body:raise ValueError(f'Missing condition: {required}')
    if not re.search(r'Resolution:\s*1920\s*x\s*1061\b',body):raise ValueError('Wrong resolution')
    if 'FAIL' in body or 'Aggregate: PASS' not in body:raise ValueError('Failed/incomplete report')
    raw=rows(path);metrics=METRICS|({'SP_Prepare','SP_Edge','SP_Weights','SP_Neighborhood'} if phase=='Profile' else set())
    expected={(m,r,t) for m in MODES for r in range(repeats) for t in metrics}
    if set(raw)!=expected or len(re.findall(r'^timing,',body,re.M))!=len(raw):raise ValueError('Missing/duplicate mode/run/metric rows')
    if any(v['samples']!=frames or not all(math.isfinite(v[k]) and v[k]>0 for k in ['mean','median','p95','p99','low1_fps']) for v in raw.values()):
        raise ValueError('Invalid sample counts or timing')
    formats=collections.Counter()
    for row in csv.reader(body.splitlines()):
        row=[v.strip() for v in row]
        if row and row[0]=='edge_storage':
            if row[1] not in MODES or int(row[2])!=(28 if 'Case19-EdgeRGBA8' in row[1] else 49) or row[3]!='PASS':raise ValueError('Incorrect actual edge format')
            formats[row[1]]+=1
    if formats!=collections.Counter({m:repeats for m in MODES}):raise ValueError('Missing actual format checks')
    result=summarize(path)
    for mode in MODES:
        if mode==CASE18:continue
        result['paired'][f'{mode} vs {CASE18}']={
            metric:dict(percent=ci([100*(raw[(mode,r,metric)]['mean']/raw[(CASE18,r,metric)]['mean']-1) for r in range(repeats)]),
                delta_ms=ci([raw[(mode,r,metric)]['mean']-raw[(CASE18,r,metric)]['mean'] for r in range(repeats)]))
            for metric in sorted(metrics)}
    result.update(validation='PASS',receipt=receipt,actual_format_checks=dict(formats))
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runs',required=True);ap.add_argument('--label',required=True);ap.add_argument('--phase',choices=['Smoke','Benchmark','Profile'],required=True);ap.add_argument('--out',required=True);x=ap.parse_args()
    receipts=json.loads(Path(x.runs).read_text(encoding='utf-8-sig'))
    selected=[r for r in receipts if r['harness']=='Case19' and r['label']==x.label and r['phase']==x.phase]
    if len(selected)!=2 or {r['scene'] for r in selected}!={'bistro','minecraft'}:raise ValueError('Expected one complete report per scene')
    result={r['scene']:analyze(r) for r in selected}
    Path(x.out).write_text(json.dumps(result,indent=1)+'\n',encoding='utf-8')
    print(f'PASS: {x.phase}, two scenes, six configurations')
if __name__=='__main__':main()
