"""Paired GPU timing of the history rejection modes (Benchmark phase of the Optimization harness).

Uses analyze_color_blend_performance.rows to read one clean-process report per scene. Changes are
computed per repeat against native case 4 (O-T2X-R) and the selected route of the SAME process and
then averaged with a Student-t 95% interval over repeats. "outside" is SMAA minus the three scopes
(SR_CameraVelocity, SF_Spatial, SR_Resolve); for (b) it holds the raw depth copy.

usage: analyze_selected_history_rejection_timing.py --report bistro=<results.csv> --report minecraft=<results.csv> --out <json>
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import analyze_color_blend_performance as p

SEL = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
MODES = [('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('clamp3x3', SEL + '+HistoryClamp3x3'),
         ('prevdepth', SEL + '+HistoryPreviousDepth'), ('velocity', SEL + '+HistoryVelocityWeight')]
METRICS = ['SMAA', 'WholeFrame', 'SR_CameraVelocity', 'SF_Spatial', 'SR_Resolve', 'outside', 'WallFrame']


def scene(report):
    r = p.rows(report)
    runs = sorted({k[1] for k in r})
    names = dict(MODES)
    assert {k[0] for k in r} == set(names.values()), sorted({k[0] for k in r})

    def value(mode, run, metric):
        if metric == 'outside':
            return value(mode, run, 'SMAA') - sum(value(mode, run, m) for m in ('SR_CameraVelocity', 'SF_Spatial', 'SR_Resolve'))
        return r[(mode, run, metric)]['mean']
    for k, m in MODES:
        for run in runs:
            for metric in ('SMAA', 'WholeFrame', 'SR_CameraVelocity', 'SF_Spatial', 'SR_Resolve', 'WallFrame'):
                assert (m, run, metric) in r, (m, run, metric)
                assert r[(m, run, metric)]['samples'] == r[(SEL, runs[0], 'SMAA')]['samples'], (m, run, metric)
    res = dict(report=str(report), repeats=len(runs), samples_per_repeat=r[(SEL, runs[0], 'SMAA')]['samples'],
               absolute={}, vs_native={}, vs_selected={})
    for k, m in MODES:
        res['absolute'][k] = {metric: p.ci([value(m, run, metric) for run in runs]) for metric in METRICS}
        for control, out in (('O-T2X-R', res['vs_native']), (SEL, res['vs_selected'])):
            if m == control:
                continue
            out[k] = {}
            for metric in METRICS:
                delta = [value(m, run, metric) - value(control, run, metric) for run in runs]
                entry = dict(delta_us=p.ci([1000 * d for d in delta]))
                if metric != 'outside':
                    entry['percent'] = p.ci([100 * (value(m, run, metric) / value(control, run, metric) - 1) for run in runs])
                out[k][metric] = entry
    return res


def fmt(c, digits=2):
    lo, hi = c['ci95'] if c['ci95'] else (c['mean'], c['mean'])
    return f"{c['mean']:+.{digits}f} [{lo:+.{digits}f}, {hi:+.{digits}f}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='append', required=True)
    ap.add_argument('--out', required=True)
    x = ap.parse_args()
    res = {}
    for a in x.report:
        name, path = a.split('=', 1)
        res[name] = scene(path)
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    for name, s in res.items():
        print(f'## {name} ({s["repeats"]} repeats)')
        for k, _ in MODES:
            a = s['absolute'][k]
            print(f"  {k:10} SMAA {a['SMAA']['mean']*1000:8.2f} us  Whole {a['WholeFrame']['mean']:.4f} ms  vel {a['SR_CameraVelocity']['mean']*1000:6.2f}"
                  f"  spatial {a['SF_Spatial']['mean']*1000:7.2f}  resolve {a['SR_Resolve']['mean']*1000:6.2f}  outside {a['outside']['mean']*1000:6.2f}")
        for title, part in (('vs O-T2X-R', s['vs_native']), ('vs selected', s['vs_selected'])):
            print(' ', title)
            for k, v in part.items():
                print(f"    {k:10} SMAA % {fmt(v['SMAA']['percent'])}  Whole % {fmt(v['WholeFrame']['percent'])}  "
                      f"spatial us {fmt(v['SF_Spatial']['delta_us'])}  resolve us {fmt(v['SR_Resolve']['delta_us'])}  outside us {fmt(v['outside']['delta_us'])}")


if __name__ == '__main__':
    main()
