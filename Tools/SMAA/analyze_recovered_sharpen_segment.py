"""Clipping factorial: baseline/mask bridges, spatial proxy and temporal diagnostics."""
import argparse, csv, hashlib, json, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from analyze_recovered_source_comparison import HISTORIC, rgb, digest, report_text
from validate_recovered_sharpen_segment import NAMES

ROOT=Path(__file__).resolve().parents[2];BENCH=ROOT/'Projects/CMAA2/AutoBench'
OLD={'bistro':'20260915_153127','minecraft':'20260915_153529'}
OLD_MASK={'bistro':'20260914_191234','minecraft':'20260914_191249'}
WINDOWS={'central':(150,329),'transition':(410,439),'post_still':(440,479)}

def sequence(path,count):
    files=sorted(Path(path).rglob('*.png'));assert len(files)==count,(path,len(files),count)
    ix=[tuple(map(int,re.search(r'_profile_(\d+)_frame_(\d+)\.png$',p.name).groups())) for p in files]
    assert ix==[(i,i) for i in range(count)],path
    return files

def manifest(path,mode,scene):
    all_runs=json.loads(path.read_text(encoding='utf-8-sig'))
    selected=[r for r in all_runs if r['mode']==mode and r['scene']==scene]
    assert len(selected)==4,'Missing or duplicate factorial run'
    runs={r['variant']:r for r in selected}
    assert set(runs)==set(NAMES),(mode,scene)
    for i,name in enumerate(NAMES):
        r=runs[name];assert r['status']=='PASS' and r['signed_chroma']==1 and r['ycocg_clamp']==1 and r['disable_sharpen']==i&1 and r['segment_clip']==i>>1
        assert hashlib.sha256(r['utility_source'].encode()).hexdigest()==r['utility_sha256'].lower()
        assert f'#define SMAA_RECOVERED_DISABLE_SHARPEN {i&1}' in r['utility_source']
        assert f'#define SMAA_RECOVERED_SEGMENT_CLIP {i>>1}' in r['utility_source']
        assert '#define SMAA_RECOVERED_SIGNED_CHROMA 1' in r['utility_source'] and '#define SMAA_RECOVERED_YCOCG_CLAMP 1' in r['utility_source']
        t=report_text(r['report']);assert 'SourceCandidate-SourceKernel-Integrated' in t
        assert '1920 x 1017' in t and 'flythrough-wide-yaw-360' in t and 'Warm-up:         60' in t
    assert len({r['exe_sha256'] for r in runs.values()})==1
    assert len({r['candidate_sha256'] for r in runs.values()})==1
    normalized={r['utility_source'].replace(f'#define SMAA_RECOVERED_DISABLE_SHARPEN {r["disable_sharpen"]}',
        '#define SMAA_RECOVERED_DISABLE_SHARPEN 0').replace(f'#define SMAA_RECOVERED_SEGMENT_CLIP {r["segment_clip"]}',
        '#define SMAA_RECOVERED_SEGMENT_CLIP 0') for r in runs.values()}
    assert len(normalized)==1,'Clipping factors were not the only utility change'
    return runs

def verify(a):
    results={}
    for scene in OLD:
        runs=manifest(a.manifest,'Short',scene);masks=manifest(a.manifest,'Masks',scene)
        for name in NAMES:
            for field in ('exe_sha256','candidate_sha256','utility_sha256'):
                assert runs[name][field]==masks[name][field],('Short/mask code mismatch',scene,name,field)
        prior=sequence(BENCH/OLD[scene],480)
        short=sequence(runs[NAMES[0]]['report'],12)
        assert all(digest(rgb(x))==digest(rgb(y)) for x,y in zip(short,prior))
        maskseq=[sequence(masks[n]['report'],12) for n in NAMES]
        finalseq=[sequence(runs[n]['report'],12) for n in NAMES]
        old=sequence(BENCH/OLD_MASK[scene],12)
        for frame in range(12):
            mask=rgb(old[frame]);target=digest(mask)
            assert np.all((mask==0)|(mask==255)) and np.array_equal(mask[...,0],mask[...,1]) and np.array_equal(mask[...,0],mask[...,2])
            assert all(digest(rgb(seq[frame]))==target for seq in maskseq),(scene,frame)
            selected=mask[...,0]>0;base=rgb(finalseq[0][frame])
            for seq in finalseq[1:]:
                changed=np.any(rgb(seq[frame])!=base,axis=-1)
                assert not np.any(changed & ~selected),(scene,frame,'Changed a noncandidate pixel')
        for name in NAMES:sequence(runs[name]['report'],12)
        results[scene]=dict(short_baseline_mismatch=0,candidate_mask_mismatch=0,noncandidate_changed_pixels=0,frames_per_variant=12)
        if a.compare_full_prefix:
            full=manifest(a.manifest,'Quality',scene)
            for name in NAMES:
                for field in ('exe_sha256','candidate_sha256','utility_sha256'):
                    assert full[name][field]==runs[name][field],('Quality/short code mismatch',scene,name,field)
                short_paths=sequence(runs[name]['report'],12);full_paths=sequence(full[name]['report'],480)
                assert all(digest(rgb(x))==digest(rgb(y)) for x,y in zip(short_paths,full_paths)),(scene,name,'Independent prefix repeat')
            results[scene]['independent_full_prefix_mismatch']=0
            results[scene]['independent_full_prefix_frames']=48
    output=dict(status='PASS',scenes=results)
    if a.prior_manifest:
        prior=json.loads(a.prior_manifest.read_text(encoding='utf-8-sig'))
        current=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
        bridges=[]
        for old in prior:
            if old['mode'] not in ('Short','Masks','Quality') or old['status']!='PASS':continue
            matching=[r for r in current if r['label']==old['label'] and r['status']=='PASS']
            assert len(matching)==1,old['label']
            new=matching[0]
            for field in ('candidate_sha256','utility_sha256','arguments'):
                assert new[field]==old[field],('Lifetime bridge changed algorithm configuration',field)
            count=480 if old['mode']=='Quality' else 12
            before=sequence(old['report'],count);after=sequence(new['report'],count)
            assert all(digest(rgb(x))==digest(rgb(y)) for x,y in zip(before,after)),('Lifetime fix pixel change',old['label'])
            bridges.append(dict(label=old['label'],frames=count,mismatch=0,before_report=old['report'],after_report=new['report']))
            print('PASS lifetime bridge: '+old['label'],flush=True)
        output['lifetime_fix_bridges']=bridges
    return output

def quality(a):
    result={}
    for scene in OLD:
        if a.scene and scene!=a.scene:continue
        runs=manifest(a.manifest,'Quality',scene)
        seq=[sequence(runs[n]['report'],480) for n in NAMES]
        prior=sequence(BENCH/OLD[scene],480)
        ref=sequence(BENCH/HISTORIC[scene][1]/'SS_Reference',480)
        rows=[];previous=None;prevref=None;peak=(-1,0)
        for n in range(480):
            raw=[rgb(s[n]) for s in seq];old_image=rgb(prior[n])
            if digest(raw[0])!=digest(old_image):
                # Preserve the actual failing arrays before stopping; a later
                # reread alone cannot establish why an earlier check failed.
                np.savez_compressed(a.output/f'{scene}-baseline-failure-{n}.npz',current=raw[0],prior=old_image)
                raise AssertionError((scene,n,'baseline bridge',str(seq[0][n]),str(prior[n])))
            images=[v.astype(np.float32) for v in raw];r=rgb(ref[n]).astype(np.float32)
            for i,v in enumerate(images):
                d=v-r;mse=float(np.mean(d*d));delta=None
                if previous is not None:delta=float(np.mean(abs((v-previous[i])-(r-prevref))))
                rows.append(dict(scene=scene,variant=NAMES[i],frame=n,mae=float(np.mean(abs(d))),
                    psnr=float(10*np.log10(255**2/max(mse,1e-20))),temporal_delta_residual=delta,
                    baseline_difference=float(np.mean(abs(v-images[0])))))
            score=float(np.mean(abs(images[3]-images[0])))
            if 150<=n<=329 and score>peak[0]:peak=(score,n)
            previous=images;prevref=r
            if n%120==0:print(f'{scene}: {n}/480',flush=True)
        with (a.output/f'{scene}-per-frame.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        windows={}
        for window,(lo,hi) in WINDOWS.items():
            by_mode={name:{key:float(np.mean([r[key] for r in rows if r['variant']==name and lo<=r['frame']<=hi]))
                           for key in ['mae','psnr','temporal_delta_residual','baseline_difference']} for name in NAMES}
            effects={}
            for key in ['mae','psnr','temporal_delta_residual']:
                x=[by_mode[name][key] for name in NAMES]
                effects[key]=dict(disable_sharpen_main=((x[1]-x[0])+(x[3]-x[2]))/2,
                    segment_main=((x[2]-x[0])+(x[3]-x[1]))/2,interaction=x[3]-x[2]-x[1]+x[0])
            windows[window]=dict(metrics=by_mode,effects=effects)
        n=peak[1];base=rgb(seq[0][n]);changed=rgb(seq[3][n]);delta=abs(changed.astype(float)-base).mean(axis=-1)
        _,x,y=max((float(delta[y:y+224,x:x+320].mean()),x,y) for y in range(0,794,56) for x in range(0,1601,80))
        box=(x,y,x+320,y+224)
        def sheet(frame):
            canvas=Image.new('RGB',(960,512),'#17202a');draw=ImageDraw.Draw(canvas)
            paths=[ref[frame]]+[s[frame] for s in seq]
            for i,(name,path) in enumerate(zip(['Spatial reference']+NAMES,paths)):
                ox=i%3*320;oy=i//3*256
                with Image.open(path) as im:canvas.paste(im.convert('RGB').crop(box),(ox,oy+30))
                draw.text((ox+5,oy+6),f'{name} / {frame}',fill='white')
            return canvas
        sheet(n).save(a.output/f'{scene}-peak-crop.png')
        for name,start,end in [('motion',max(150,n-12),min(330,n+12)),('transition',410,440)]:
            images=[sheet(frame) for frame in range(start,end)]
            images[0].save(a.output/f'{scene}-{name}.gif',save_all=True,append_images=images[1:],duration=100,loop=0)
        compact={name:{k:v for k,v in r.items() if k!='utility_source'} for name,r in runs.items()}
        result[scene]=dict(baseline_480_frame_mismatch=0,reference=str(ref[0].parent),runs=compact,windows=windows,peak_frame=n,crop=box)
    return dict(status='PASS',scope='Spatial-reference proxy and temporal-delta diagnostics; not ghosting ground truth',scenes=result)

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['verify','quality'],required=True)
    p.add_argument('--scene',choices=['bistro','minecraft'])
    p.add_argument('--compare-full-prefix',action='store_true')
    p.add_argument('--prior-manifest',type=Path,help='Compare all completed pre-lifetime-fix captures by label and RGB hash')
    p.add_argument('--manifest',type=Path,default=ROOT/'tmp/recovered-sharpen-segment/runs.json')
    p.add_argument('--output',type=Path,default=ROOT/'tmp/recovered-sharpen-segment/analysis');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    result=verify(a) if a.mode=='verify' else quality(a)
    target=a.output/(a.mode+'.json')
    if a.mode=='quality' and a.scene and target.exists():
        old=json.loads(target.read_text());old['scenes'].update(result['scenes']);result=old
    target.write_text(json.dumps(result,indent=2));print('PASS: '+a.mode,flush=True)
if __name__=='__main__':main()
