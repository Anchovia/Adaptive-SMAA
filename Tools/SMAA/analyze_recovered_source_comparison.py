"""Analyze the recovered-source 2x2 comparison with explicit provenance.

All quality sequences start at profile zero and include identical temporal prehistory.
Supersampling is a spatial reference proxy. Frame differences are not ghosting truth.
"""
import argparse, csv, hashlib, json, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from analyze_wide_camera_reference_quality import luma_ssim, edge_strength

IDS=['O-ET2X-R-DocCandidate-DocKernel','O-ET2X-R-SourceCandidate-DocKernel',
     'O-ET2X-R-DocCandidate-SourceKernel','O-ET2X-R-SourceCandidate-SourceKernel']
HISTORIC={'bistro':('20260827_013824','20260827_014143'),'minecraft':('20260827_014324','20260827_014612')}
def frames(root):
    paths=sorted(Path(root).rglob('*.png'))
    # Each run in this matrix contains exactly one output sequence.
    assert len(paths)==480,(root,len(paths))
    indices=[tuple(map(int,re.search(r'_profile_(\d+)_frame_(\d+)\.png$',p.name).groups())) for p in paths]
    assert indices==[(i,i) for i in range(480)],root
    return paths
def rgb(p):return np.asarray(Image.open(p).convert('RGB'))
def digest(a):return hashlib.sha256(a.tobytes()).hexdigest()
def report_text(root):
    files=list(Path(root).glob('*_results.csv'));assert len(files)==1
    s=files[0].read_text(encoding='utf-8-sig');assert not re.search(r'\bFAIL\b',s)
    return s
def average(rows,key,lo,hi):
    return float(np.mean([row[key] for row in rows if lo<=row['frame']<=hi and row.get(key) is not None]))
def quality(manifest,bench,out,selected=None):
    runs={x['label']:x for x in manifest};summary={}
    for scene,(old,reference) in HISTORIC.items():
        if selected is not None and scene!=selected:continue
        keys=[f'{scene}-spatial-control']+[f'{scene}-profile-{i}' for i in range(4)]
        if any(k not in runs for k in keys):continue
        sources=[runs[k]['report'] for k in keys]
        for src in sources:
            t=report_text(src)
            assert 'flythrough-wide-yaw-360' in t and 'capture [0, 479]' in t and 'Warm-up:         60' in t
            assert '1920 x 1017' in t
        seq=[frames(src) for src in sources];ref=frames(bench/reference/'SS_Reference');control=frames(bench/old/'O_1X')
        rows=[[] for _ in range(4)];bridges=0;previous=[None]*4;previous_ref=None
        best=(-1,None)
        for n in range(480):
            raw=[rgb(s[n]) for s in seq];target=rgb(ref[n]);oldcontrol=rgb(control[n])
            assert all(a.shape==target.shape==(1017,1920,3) for a in raw)
            bridges+=digest(raw[0])!=digest(oldcontrol)
            a=[v.astype(np.float32) for v in raw];r=target.astype(np.float32)
            for i in range(4):
                v=a[i+1];diff=v-r;mse=float(np.mean(diff*diff))
                row=dict(scene=scene,mode=IDS[i],frame=n,rgb_mae=float(np.mean(abs(diff))),
                    psnr=10*np.log10(255**2/max(mse,1e-20)),difference_from_document=float(np.mean(abs(v-a[1]))),
                    temporal_delta_residual=None,ssim=None,edge_ratio=None)
                if previous[i] is not None:
                    row['temporal_delta_residual']=float(np.mean(abs((v-previous[i])-(r-previous_ref))))
                if n%8==0:
                    row['ssim']=luma_ssim(v,r)
                    row['edge_ratio']=edge_strength(v)/max(edge_strength(r),1e-12)
                rows[i].append(row);previous[i]=v
            previous_ref=r
            d=float(np.mean(abs(a[4]-a[1])))
            if 60<=n<420 and d>best[0]:best=(d,n)
            if n%120==0:print(f'{scene}: analyzed {n}/480',flush=True)
        assert bridges==0,f'{scene}: O-1X historical pose/content bridge failed: {bridges}'
        scene_summary={'spatial_control_pixel_hash_mismatch':bridges,'reference':str(bench/reference),
            'runs':{k:runs[k] for k in keys},'windows':{},'peak_difference_frame':best[1]}
        for name,lo,hi in [('all',0,479),('central_motion',150,329),('transition',410,439),('post_still',440,479)]:
            scene_summary['windows'][name]=[{key:average(row,key,lo,hi) for key in ['rgb_mae','psnr','temporal_delta_residual','ssim','edge_ratio','difference_from_document']} for row in rows]
        with (out/f'{scene}-quality-per-frame.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0][0]));w.writeheader();w.writerows([v for row in rows for v in row])
        n=best[1];images=[Image.open(seq[i+1][n]).convert('RGB') for i in range(4)]
        # Select a concrete region of largest aggregate algorithm disagreement.
        delta=np.abs(np.asarray(images[3],dtype=float)-np.asarray(images[0],dtype=float)).mean(axis=-1)
        candidates=[(float(delta[y:y+224,x:x+320].mean()),x,y) for y in range(0,1017-224,56) for x in range(0,1920-320,80)]
        _,x,y=max(candidates);box=(x,y,x+320,y+224);scene_summary['peak_crop']=box
        sheet=Image.new('RGB',(960,704),'#171b22');draw=ImageDraw.Draw(sheet)
        for i,im in enumerate(images):
            ox=(i%2)*480;oy=(i//2)*352
            draw.text((ox+12,oy+8),IDS[i],fill='white')
            sheet.paste(im.crop(box).resize((480,320)),(ox,oy+30))
        sheet.save(out/f'{scene}-four-way-crop.png')
        motion=[]
        for n in range(396,444,2):
            tile=Image.new('RGB',(960,704),'#171b22');draw=ImageDraw.Draw(tile)
            for i in range(4):
                im=Image.open(seq[i+1][n]).convert('RGB').crop(box).resize((480,320))
                ox=(i%2)*480;oy=(i//2)*352;tile.paste(im,(ox,oy+30));draw.text((ox+6,oy+8),f'{IDS[i]} frame {n}',fill='white')
            motion.append(tile)
        motion[0].save(out/f'{scene}-transition.gif',save_all=True,append_images=motion[1:],duration=100,loop=0)
        summary[scene]=scene_summary
    return summary

def performance(manifest):
    result={}
    for run in manifest:
        if not run['label'].endswith('-paired-benchmark'):continue
        t=report_text(run['report']);assert 'Performance benchmark validation: PASS' in t
        assert '4800 frames per mode per repeat' in t and 'repeats: 3' in t and 'Candidate counter readback: disabled' in t
        assert run['window']=='visible'
        entries={mode:{} for mode in IDS}
        for row in csv.reader(t.splitlines()):
            row=[v.strip() for v in row]
            if len(row)>=12 and row[0] in IDS and row[2] in ('GPU timestamp','CPU wall interval'):
                assert int(row[3])==14400 and int(row[10])==3,row
                entries[row[0]][row[1]]={k:float(row[j]) for k,j in [('mean_ms',4),('median_ms',5),('p95_ms',7),('p99_ms',8),('run_mean_stddev_ms',11)]}
        assert all('SMAA' in entries[v] and 'WholeFrame' in entries[v] for v in IDS)
        result[run['label']]={'run':run,'metrics':entries}
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--performance-only',action='store_true');p.add_argument('--scene',choices=['bistro','minecraft']);a=p.parse_args()
    runs=json.loads(a.manifest.read_text(encoding='utf-8-sig'));a.output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[2];bench=root/'Projects/CMAA2/AutoBench'
    result={'classification':'Recovered-source SMAA adaptation 2x2 comparison; supersample spatial proxy, not temporal ground truth',
        'quality':{} if a.performance_only else quality(runs,bench,a.output,a.scene),'performance':performance(runs),'ssim_stride':8}
    if a.scene and (a.output/'comparison.json').exists():
        previous=json.loads((a.output/'comparison.json').read_text())['quality']
        previous.update(result['quality']);result['quality']=previous
    name='performance.json' if a.performance_only else 'comparison.json'
    (a.output/name).write_text(json.dumps(result,indent=2,allow_nan=False))
    print(f'PASS: wrote {a.output/name}',flush=True)
if __name__=='__main__':main()
