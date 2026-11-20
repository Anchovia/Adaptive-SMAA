"""Formal (visible-window) GPU timing of the final combination: case 4, the selected route alone and with
(c') Cross5, Adaptive + selected route alone and with Cross5, one clean-process report per scene.

Paired changes are computed per repeat against modes of the SAME process (case 4, selected route, selected +
Cross5, Adaptive + selected route) and averaged with a Student-t 95% interval over the repeats
(analyze_color_blend_performance.ci). "outside" is SMAA minus the camera velocity, spatial and resolve scopes.
Frame statistics (WallFrame, WholeFrame): mean with its interval, and the per-run median, p95, p99, within-run
standard deviation and 1% low fps averaged over the runs.

With --hidden <timing.json of the integration branch> the same paired changes measured in a hidden window
(engineering) are listed next to these; only ratios are compared, since the window sizes may differ.

usage: analyze_adaptive_selected_cross5_formal_timing.py --report bistro=<csv> --report minecraft=<csv>
         --resolution 1920x1017 [--hidden <json>] --out <json>
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import analyze_color_blend_performance as p

SEL = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
X5 = '+HistoryVelocityPingPongCross5'
MODES = [('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('cross5', SEL + X5), ('A-selected', 'A-' + SEL), ('A-cross5', 'A-' + SEL + X5)]
CONTROLS = [('vs_native', 'O-T2X-R'), ('vs_selected', SEL), ('vs_cross5', SEL + X5), ('vs_A_selected', 'A-' + SEL)]
SCOPES = ['SMAA', 'WholeFrame', 'SR_CameraVelocity', 'SF_Spatial', 'SR_Resolve', 'WallFrame']
# Comparisons the document reports: (label, mode key, control key)
KEY = [('A+selected+Cross5 vs case 4', 'A-cross5', 'vs_native'), ('A+selected vs case 4', 'A-selected', 'vs_native'),
       ('selected+Cross5 vs case 4', 'cross5', 'vs_native'), ('selected vs case 4', 'selected', 'vs_native'),
       ('Adaptive on selected (A+selected vs selected)', 'A-selected', 'vs_selected'),
       ('Adaptive on selected+Cross5 (A+selected+Cross5 vs selected+Cross5)', 'A-cross5', 'vs_cross5'),
       ('Cross5 on Original (selected+Cross5 vs selected)', 'cross5', 'vs_selected'),
       ('Cross5 on Adaptive (A+selected+Cross5 vs A+selected)', 'A-cross5', 'vs_A_selected')]


def scene(report):
    r = p.rows(report)
    text = Path(report).read_text(encoding='utf-8-sig')
    res_m = re.search(r'Resolution:\s*(\d+)\s*x\s*(\d+)', text)
    runs = sorted({k[1] for k in r})
    names = dict(MODES)
    assert {k[0] for k in r} == set(names.values()), sorted({k[0] for k in r})
    for _, m in MODES:
        for run in runs:
            for metric in SCOPES:
                assert (m, run, metric) in r, (m, run, metric)

    def value(m, run, metric):
        if metric == 'outside':
            return value(m, run, 'SMAA') - sum(value(m, run, s) for s in ('SR_CameraVelocity', 'SF_Spatial', 'SR_Resolve'))
        return r[(m, run, metric)]['mean']
    out = dict(report=str(report), resolution=[int(res_m.group(1)), int(res_m.group(2))] if res_m else None, repeats=len(runs),
               samples_per_repeat=r[(SEL, runs[0], 'SMAA')]['samples'], absolute={}, frame_stats={})
    for key, _ in CONTROLS:
        out[key] = {}
    for k, m in MODES:
        out['absolute'][k] = {metric: p.ci([value(m, run, metric) for run in runs]) for metric in SCOPES + ['outside']}
        out['frame_stats'][k] = {}
        for metric in ('WallFrame', 'WholeFrame'):
            rows = [r[(m, run, metric)] for run in runs]
            mean = p.ci([x['mean'] for x in rows])
            out['frame_stats'][k][metric] = dict(mean_ms=mean, fps_from_mean=1000.0 / mean['mean'],
                                                 median_ms=sum(x['median'] for x in rows) / len(rows), p95_ms=sum(x['p95'] for x in rows) / len(rows),
                                                 p99_ms=sum(x['p99'] for x in rows) / len(rows), within_run_stddev_ms=sum(x['stddev'] for x in rows) / len(rows),
                                                 low1_fps=sum(x['low1_fps'] for x in rows) / len(rows))
        for key, control in CONTROLS:
            if m == control:
                continue
            out[key][k] = {}
            for metric in SCOPES + ['outside']:
                entry = dict(delta_us=p.ci([1000 * (value(m, run, metric) - value(control, run, metric)) for run in runs]))
                if metric != 'outside' and all(value(control, run, metric) != 0 for run in runs):
                    entry['percent'] = p.ci([100 * (value(m, run, metric) / value(control, run, metric) - 1) for run in runs])
                out[key][k][metric] = entry
    return out


def fmt(c, unit='%', digits=2):
    lo, hi = c['ci95'] if c['ci95'] else (c['mean'], c['mean'])
    return f"{c['mean']:+.{digits}f}{unit} [{lo:+.{digits}f}, {hi:+.{digits}f}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='append', required=True)
    ap.add_argument('--resolution', required=True)
    ap.add_argument('--hidden')
    ap.add_argument('--out', required=True)
    x = ap.parse_args()
    want = [int(v) for v in x.resolution.lower().split('x')]
    res = dict(classification='formal', window='visible', expected_resolution=want, scenes={})
    hidden = json.loads(Path(x.hidden).read_text(encoding='utf-8')) if x.hidden else None
    for a in x.report:
        name, path = a.split('=', 1)
        s = scene(path)
        assert s['resolution'] == want, (name, s['resolution'], want)
        if hidden and name in hidden:
            h = hidden[name]
            s['hidden_engineering'] = {label: dict(formal_percent=s[ctrl][k]['SMAA']['percent'], hidden_percent=h[ctrl][k]['SMAA']['percent'])
                                       for label, k, ctrl in KEY}
            s['resolve_vs_hidden'] = {k: dict(formal_us=s['absolute'][k]['SR_Resolve']['mean'] * 1000,
                                              hidden_us=h['absolute'][k]['SR_Resolve']['mean'] * 1000) for k, _ in MODES}
            s['cross5_resolve_delta_vs_hidden'] = {
                'Original': dict(formal_us=s['vs_selected']['cross5']['SR_Resolve']['delta_us'], hidden_us=h['vs_selected']['cross5']['SR_Resolve']['delta_us']),
                'Adaptive': dict(formal_us=s['vs_A_selected']['A-cross5']['SR_Resolve']['delta_us'], hidden_us=h['vs_A_selected']['A-cross5']['SR_Resolve']['delta_us'])}
        res['scenes'][name] = s
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    for name, s in res['scenes'].items():
        print(f"## {name} ({s['repeats']} repeats, {s['resolution'][0]}x{s['resolution'][1]}, visible)")
        for k, _ in MODES:
            a, f = s['absolute'][k], s['frame_stats'][k]
            print(f"  {k:11} SMAA {a['SMAA']['mean']*1000:7.2f} us  spatial {a['SF_Spatial']['mean']*1000:7.2f}  resolve {a['SR_Resolve']['mean']*1000:6.2f}"
                  f"  vel {a['SR_CameraVelocity']['mean']*1000:6.2f}  Whole {f['WholeFrame']['mean_ms']['mean']:.4f} ms  Wall {f['WallFrame']['mean_ms']['mean']:.4f} ms"
                  f" ({f['WallFrame']['fps_from_mean']:.1f} fps, p95 {f['WallFrame']['p95_ms']:.3f}, p99 {f['WallFrame']['p99_ms']:.3f}, 1%low {f['WallFrame']['low1_fps']:.1f}, sd {f['WallFrame']['within_run_stddev_ms']:.3f})")
        for label, k, ctrl in KEY:
            e = s[ctrl][k]
            line = f"  {label:70} SMAA {fmt(e['SMAA']['percent'])}  Whole {fmt(e['WholeFrame']['percent'])}  spatial {fmt(e['SF_Spatial']['delta_us'], ' us')}  resolve {fmt(e['SR_Resolve']['delta_us'], ' us')}  outside {fmt(e['outside']['delta_us'], ' us')}"
            if 'hidden_engineering' in s:
                line += f"  | hidden {fmt(s['hidden_engineering'][label]['hidden_percent'])}"
            print(line)


if __name__ == '__main__':
    main()
