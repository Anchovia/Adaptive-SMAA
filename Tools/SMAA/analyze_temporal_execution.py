"""Same-output execution controls and spatial mask locality (not warp counters)."""
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image

MODES=['O-T2X-R','ABL-NativeSM5-R','ABL-Lod-R','ABL-CurrentFirst-R',
       'ABL-Contrast-All-R','ABL-Contrast-001-R','ABL-Structured-001-R',
       'ABL-Flatten-001-R','ABL-PrefetchVelocity-001-R']
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rgb(p):
    with Image.open(p) as im: return np.asarray(im.convert('RGB'))

def capture(folder, old):
    names=MODES+['DBG-CurrentSpatial-R','DBG-ContrastMask-001-R']
    paths={n:sorted((folder/n).glob('frame_*.png')) for n in names}
    assert all(len(p)==240 for p in paths.values())
    assert all([p.name for p in seq]==[f'frame_{i:05}.png' for i in range(240)] for seq in paths.values())
    checks={n:0 for n in names if n in ('O-T2X-R','ABL-Contrast-All-R','ABL-Contrast-001-R','DBG-CurrentSpatial-R','DBG-ContrastMask-001-R')}
    matches={n:0 for n in MODES[1:]};selection=[];locality=[]
    manifests=[]
    for i in range(240):
        hashes={n:digest(paths[n][i]) for n in names}
        manifests.append(dict(frame=i,sha256=hashes))
        for n in checks: checks[n]+=hashes[n]!=digest(old/n/paths[n][i].name)
        for n in MODES[1:]:
            target='O-T2X-R' if n in MODES[1:5] else 'ABL-Contrast-001-R'
            matches[n]+=hashes[n]!=hashes[target]
        mask=rgb(paths['DBG-ContrastMask-001-R'][i])[:,:,0]
        assert mask.shape==(1061,1920) and np.all((mask==0)|(mask==255))
        mask=mask==255;selection.append(int(mask.sum()))
        # Screen-space tiles are proxies only; no assumed raster-to-warp mapping.
        for h,w in [(2,2),(4,8),(8,4)]:
            hh,ww=mask.shape[0]//h*h,mask.shape[1]//w*w
            counts=mask[:hh,:ww].reshape(hh//h,h,ww//w,w).sum(axis=(1,3))
            active=counts>0
            locality.append(dict(frame=i,tile=f'{w}x{h}',covered_pixels=hh*ww,
                mixed_fraction=float(((counts>0)&(counts<h*w)).mean()),
                active_fraction=float(active.mean()),
                selected_per_active_tile=float(counts[active].mean()) if active.any() else 0))
        if i%60==59: print(f'Validated {i+1}/240',flush=True)
    assert all(v==0 for v in checks.values()),checks
    assert all(v==0 for v in matches.values()),matches
    summaries={}
    for tile in sorted(set(x['tile'] for x in locality)):
        summaries[tile]={k:float(np.mean([x[k] for x in locality if x['tile']==tile]))
            for k in ('mixed_fraction','active_fraction','selected_per_active_tile')}
    return dict(capture=str(folder),prior_capture=str(old),prior_hash_mismatches=checks,
        control_hash_mismatches=matches,selection_mean=float(np.mean(selection)),
        selection_percent=float(np.mean(selection)/2037120*100),
        locality=summaries,locality_note='Screen-space tile proxy, NOT measured warp divergence or memory transactions; partial bottom tiles excluded.',
        frame_hashes=manifests,per_frame_locality=locality)

def performance(path, modes=None):
    modes=MODES if modes is None else modes
    text=path.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text
    assert '1920 x 1061' in text and 'Vsync:        OFF' in text
    rows=[];distributions=[]
    for line in text.splitlines():
        v=[s.strip() for s in next(csv.reader([line]))]
        if v and v[0]=='timing': rows.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),mean_ms=float(v[5]),p95_ms=float(v[6])))
        if v and v[0]=='distribution': distributions.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),median_ms=float(v[5]),sample_std_ms=float(v[6]),p99_ms=float(v[7]),wall_fps=float(v[8]),wall_1pct_low_fps=float(v[9])))
    assert len(rows)==len(modes)*15 and len(distributions)==len(modes)*15 and set(x['mode'] for x in rows)==set(modes)
    metrics=['SMAA','Spatial','Resolve','WholeFrame','WallFrame']
    result={}
    for n in modes:
        result[n]={}
        for m in metrics:
            cells=sorted([r for r in rows if r['mode']==n and r['metric']==m],key=lambda x:x['run'])
            assert [x['run'] for x in cells]==[0,1,2] and all(x['samples']==4800 for x in cells)
            a=np.array([x['mean_ms'] for x in cells]);assert np.all(np.isfinite(a)&(a>0))
            result[n][m]=dict(mean_ms=float(a.mean()),run_std_ms=float(a.std(ddof=1)),runs_ms=a.tolist())
            d=sorted([r for r in distributions if r['mode']==n and r['metric']==m],key=lambda x:x['run'])
            assert [x['run'] for x in d]==[0,1,2] and all(x['samples']==4800 for x in d)
            assert all(np.isfinite(x[k]) and x[k]>=0 for x in d for k in ['median_ms','sample_std_ms','p99_ms','wall_fps','wall_1pct_low_fps'])
            result[n][m]['run_distributions']=d
    for n in modes:
        for m in metrics:
            for label,other in [('native','O-T2X-R'),('prior','ABL-Contrast-001-R')]:
                a=np.array(result[n][m]['runs_ms']);b=np.array(result[other][m]['runs_ms'])
                result[n][m][f'percent_vs_{label}']=float((a.mean()/b.mean()-1)*100)
                result[n][m][f'paired_deltas_vs_{label}_ms']=(a-b).tolist()
    return dict(source=str(path),report_sha256=digest(path),modes=result,rows=rows,distributions=distributions)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path);p.add_argument('--prior',type=Path)
    p.add_argument('--performance',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();data=capture(a.capture,a.prior) if a.capture else performance(a.performance)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,indent=2)+'\n');print('PASS:',a.output)
