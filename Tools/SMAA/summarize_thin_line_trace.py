"""Save trace witnesses; these are diagnostics, not a proposed new AA method."""
import json
from pathlib import Path
import numpy as np
from analyze_thin_line_trace import ROOT,DOC,OUT,A,C,ROIS,rgb,dds,edges,sha,ph,dump

def main():
    still=[];validation=[]
    for scene,regions in ROIS.items():
        v=json.loads((DOC/f'{scene}-capture-validation.json').read_text())
        assert v['validation']=='PASS'
        validation.append(dict(scene=scene,frames=v['baseline_rgb_frames'],
            trace_frames=2*v['trace_frames_per_mode'],
            maximum_safe_cpu_rgb_error=max(r['max_rgb_error_safe'] for r in v['records'])))
        cap=Path(v['capture'])
        for tag,mode in [('edge-off',A),('native-on',C)]:
            velocity_max=0.0
            for f in range(190,196):
                velocity_max=max(velocity_max,float(np.max(np.abs(dds(cap/mode/f'frame_{f:05d}-velocity.dds')))))
            for region in regions:
                p=OUT/f'{scene}-{region}-{tag}.npz';a=np.load(p)
                ix=np.flatnonzero((a['frames']>=190)&(a['frames']<=195));assert len(ix)==6
                d={k:int(sum(not np.array_equal(a[k][j],a[k][ix[0]]) for j in ix[1:])) for k in ['raw','current','previous_point','final']}
                changing=int(np.any(a['current'][ix]!=a['previous_point'][ix],axis=-1).sum())
                output_change=int(np.any(a['current'][ix]!=a['final'][ix],axis=-1).sum())
                assert d['final']==0
                if tag=='edge-off':assert changing==output_change==0 and velocity_max==0
                else:
                    for k in ['raw','current']:
                        assert np.array_equal(a[k][ix[0]],a[k][ix[2]]) and np.array_equal(a[k][ix[1]],a[k][ix[3]])
                still.append(dict(scene=scene,region=region,mode=mode,frames=list(range(190,196)),
                    roi=a['roi'].tolist(),roi_npz_sha256=sha(p),frames_different_from_first=d,
                    pixel_frame_current_history_difference=changing,pixel_frame_current_final_difference=output_change,
                    maximum_abs_velocity_full_screen=velocity_max))

    # Reuse actual GPU full-screen Pattern-Off output from its independent branch.
    # It is NOT a new mode in this trace branch and NOT the CPU virtual resolve.
    old=Path('D:/SMAAResearchCaptures/coverage-pattern-control-20260930/capture/minecraft/20260930_234720')
    oldmode='ABL-Spatial-FullScreen-PatternOff-R'
    v=json.loads((DOC/'minecraft-capture-validation.json').read_text());cap=Path(v['capture'])
    a=np.load(OUT/'minecraft-thin_edges-edge-off.npz');c=np.load(OUT/'minecraft-thin_edges-native-on.npz')
    rx,ry,_,_=a['roi'];witnesses=[];sources=[]
    for f,x,y in [(130,971,544),(131,971,544),(132,972,544),(133,972,544),(134,972,544),(135,973,544)]:
        ix=int(np.flatnonzero(a['frames']==f)[0]);z=(ix,y-ry,x-rx)
        assert bool(a['safe'][z])
        target=rgb(cap/A/f'frame_{f:05d}.png');prior=rgb(old/A/f'frame_{f:05d}.png')
        assert np.array_equal(target,prior)
        full=rgb(old/oldmode/f'frame_{f:05d}.png')
        point=np.floor(a['coords'][z]).astype(int)
        pe=edges(cap/A/f'frame_{f-1:05d}-edge.rg8')
        row=dict(frame=f,pixel=[x,y],selected=bool(a['mask'][z]),safe_point=True,
            point_coordinate=a['coords'][z].tolist(),point_texel=point.tolist(),
            previous_edge_at_point=bool(pe[point[1],point[0]].any()),
            hypothetical_native_weight=float(a['weight'][z]),
            hypothetical_cpu_full_resolve=a['full_resolve'][z].tolist(),
            prior_actual_full_screen_off_rgb=full[y,x].tolist(),
            native_pattern_on_rgb=c['final'][z].tolist())
        for key in ['raw','current','previous_point','final']:row[key]=a[key][z].tolist()
        witnesses.append(row)
        sources.append(dict(frame=f,new_target_rgb_sha256=ph(target),old_target_rgb_sha256=ph(prior),
            prior_full_screen_path=str(old/oldmode/f'frame_{f:05d}.png'),prior_full_screen_rgb_sha256=ph(full)))
    assert all(not x['selected'] and x['previous_edge_at_point'] for x in witnesses if x['frame'] in [131,134])
    dump(DOC/'findings.json',dict(validation='PASS',validation_totals=validation,
        still=still,witnesses=witnesses,external_output_bridge=sources,
        external_branch='validation/spatial-edge-coverage-pattern-control',external_renderer_commit='eb1bd0b',
        limitations=['Pixel witnesses are selected observed failures, not whole-image statistics.',
            'The CPU history/weight for nonselected pixels was never executed by the selective GPU resolve.',
            'Previous-edge lookup diagnoses temporal nonselection; no persistence/dilation is implemented.',
            'Current and history both missing a signal cannot be repaired by a different mixing weight alone.',
            'Native-On differs in both sample pattern and coverage; no isolated jitter effect size is claimed.']))
    print('PASS: still-phase traces and six moving-line witnesses')

if __name__=='__main__':main()
