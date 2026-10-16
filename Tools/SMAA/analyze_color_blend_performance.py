"""Paired GPU timing summary for the case-17 preservation/optimization harnesses.

Reads timing rows (type,mode,run,metric,samples,mean,median,p95,p99,stddev,
1%-low fps) from completed clean-process reports. Changes are computed per
repeat against modes of the SAME process (native case 4 and case 17), then
averaged; a Student-t 95% interval (df = repeats-1, no multiple-comparison
correction) describes repeat-to-repeat variation. Absolute times from
different processes are never used as denominators.
"""
import argparse,json,math,re,statistics
from pathlib import Path

CASE17='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend'
NATIVE='O-T2X-R'
T95={1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,8:2.306,9:2.262}
METRICS=['SMAA','SF_Spatial','SR_CameraVelocity','SR_Resolve','WholeFrame','WallFrame','SP_Prepare','SP_Edge','SP_Weights','SP_Neighborhood']

def rows(report):
    text=Path(report).read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and not re.search(r',\s*FAIL\s*(?:,|$)',text,re.M),report
    out={}
    for m in re.finditer(r'^timing,\s*([^,]+),\s*(\d+),\s*([^,]+),\s*(\d+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)',text,re.M):
        mode,run,metric=m.group(1).strip(),int(m.group(2)),m.group(3).strip()
        out[(mode,run,metric)]=dict(samples=int(m.group(4)),mean=float(m.group(5)),median=float(m.group(6)),p95=float(m.group(7)),p99=float(m.group(8)),
            stddev=float(m.group(9)),low1_fps=float(m.group(10)))
    return out
def ci(values):
    n=len(values);mean=statistics.fmean(values)
    if n<2:return dict(mean=mean,ci95=None,runs=values)
    half=T95.get(n-1,1.96)*statistics.stdev(values)/math.sqrt(n);return dict(mean=mean,ci95=[mean-half,mean+half],runs=values)
def summarize(report):
    r=rows(report);modes=sorted({k[0] for k in r});runs=sorted({k[1] for k in r});metrics=[m for m in METRICS if any(k[2]==m for k in r)]
    for mode in modes:
        for run in runs:
            for metric in metrics:assert (mode,run,metric) in r,(mode,run,metric)
    res=dict(report=str(report),modes=modes,repeats=len(runs),samples_per_repeat={m:r[(modes[0],runs[0],m)]['samples'] for m in metrics},absolute={},paired={})
    for mode in modes:
        res['absolute'][mode]={metric:dict(ci([r[(mode,run,metric)]['mean'] for run in runs]),
            median=statistics.fmean(r[(mode,run,metric)]['median'] for run in runs),p95=statistics.fmean(r[(mode,run,metric)]['p95'] for run in runs),
            p99=statistics.fmean(r[(mode,run,metric)]['p99'] for run in runs),within_run_stddev=statistics.fmean(r[(mode,run,metric)]['stddev'] for run in runs),
            low1_fps=statistics.fmean(r[(mode,run,metric)]['low1_fps'] for run in runs)) for metric in metrics}
    for control in [NATIVE,CASE17]:
        if control not in modes:continue
        for mode in modes:
            if mode==control:continue
            key=f'{mode} vs {control}';res['paired'][key]={}
            for metric in metrics:
                pct=[100*(r[(mode,run,metric)]['mean']/r[(control,run,metric)]['mean']-1) for run in runs]
                delta=[r[(mode,run,metric)]['mean']-r[(control,run,metric)]['mean'] for run in runs]
                res['paired'][key][metric]=dict(percent=ci(pct),delta_ms=ci(delta))
    return res
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('reports',nargs='+');ap.add_argument('--out');x=ap.parse_args()
    res=[summarize(p) for p in x.reports];txt=json.dumps(res,indent=1);print(txt[:4000])
    if x.out:Path(x.out).parent.mkdir(parents=True,exist_ok=True);Path(x.out).write_text(txt+'\n',encoding='utf-8')
