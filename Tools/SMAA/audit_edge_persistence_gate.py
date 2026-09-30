"""Validate saved gate artifacts and record the isolated renderer/capability scope."""
import json,subprocess
import numpy as np
from edge_persistence_trace_inputs import ROOT,dump,sha
from analyze_edge_persistence_gate import DOC,OUT

def main():
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    assert branch=='validation/spatial-edge-persistence-gate'
    subprocess.run(['git','diff','304f749','--exit-code','--','Projects/CMAA2','Modules'],cwd=ROOT,check=True)
    a=np.load(OUT/'minecraft-thin_edges.npz');rx,ry,_,_=a['roi'];witnesses=[]
    for f,x,y in [(131,971,544),(134,972,544),(132,972,544),(135,973,544)]:
        i=int(np.flatnonzero(a['frames']==f)[0]);z=(i,y-ry,x-rx)
        r=dict(frame=f,pixel=[x,y],selected_current=bool(a['current_mask'][z]),selected_added=bool(a['added_mask'][z]),
            safe=bool(a['safe'][z]),weight=float(a['weight'][z]))
        assert r['safe'] and r['selected_added']==(f in [131,134])
        for k in ['base','proxy','native','reference']:r[k]=a[k][z].tolist()
        witnesses.append(r)
    dump(DOC/'witnesses.json',witnesses)
    results=[]
    for scene in ['bistro','minecraft']:
        r=json.loads((DOC/f'{scene}-results.json').read_text());assert r['validation']=='PASS' and len(r['frames'])==29
        assert r['summary']['still']['added_pixel_frames']==0
        results.append(dict(scene=scene,frames=len(r['frames']),sha256=sha(DOC/f'{scene}-results.json')))
    media=json.loads((DOC/'media.json').read_text());assert media['validation']=='PASS'
    for row in media['items']:assert sha(row['png'])==row['png_sha256'] and row['lossless_roundtrip']
    probe=(DOC/'stencil-ref-probe.txt').read_text(encoding='utf-8-sig')
    assert 'NVIDIA GeForce RTX 3060 Ti' in probe and 'ps_stencil_ref=0' in probe
    assert all(f'{p}_compile_hr=00000000' in probe and f'{p}_create_hr=80070057' in probe for p in ['ps_5_0','ps_5_1'])
    dump(DOC/'audit.json',dict(validation='PASS',branch=branch,direct_base='304f7493c6a5e53fa3cfac5dfd084ce0e86ca459',
        renderer_diff_zero=True,gpu_aa_implementation=False,gpu_performance_measured=False,results=results,
        media_count=len(media['items']),probe_executable_sha256=sha(ROOT/'tmp/stencil-ref-probe.exe'),
        probe_scope='No window or draw; feature query and shader compile/create only.',
        probe_compiler='MSVC 14.44.35207 x64; Windows SDK 10.0.26100.0; C++17; d3d11.lib and d3dcompiler.lib',
        npz=[dict(path=str(p),sha256=sha(p)) for p in OUT.glob('*.npz')],
        verdict='Partial line-retention evidence; no overall quality, disocclusion, or speed success claim.'))
    print('PASS: 58 offline frames, 8 original-color comparison sets, unchanged renderer, unsupported stencil export')

if __name__=='__main__':main()
