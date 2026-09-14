"""Compare Standard SMAA T2X-R with the source adaptation, with provenance gates.

Separate/integrated equality isolates execution cost. Standard/source comparison
includes the deliberate jitter, kernel, weight and feedback topology differences.
"""
import argparse,csv,json,re
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from analyze_recovered_source_comparison import frames,rgb,digest,report_text,HISTORIC,average
from analyze_wide_camera_reference_quality import luma_ssim,edge_strength

IDS=['O-T2X-R','O-ET2X-R-SourceCandidate-SourceKernel-Separate','O-ET2X-R-SourceCandidate-SourceKernel-Integrated']
PRIOR_SOURCE={'bistro':'20260914_142836','minecraft':'20260914_143331'}

def performance(runs):
    result={}
    for run in runs:
        if not run['label'].endswith('-Benchmark'):continue
        text=report_text(run['report'])
        assert 'Performance benchmark validation: PASS' in text and '4800 frames per mode per repeat' in text
        assert 'repeats: 3' in text and 'Candidate counter readback: disabled' in text and run['window']=='visible'
        assert '1920 x 1017' in text
        modes={mode:{} for mode in IDS}
        for row in csv.reader(text.splitlines()):
            row=[v.strip() for v in row]
            if len(row)>=12 and row[0] in modes and row[2] in ('GPU timestamp','CPU wall interval'):
                assert int(row[3])==14400 and int(row[10])==3,row
                modes[row[0]][row[1]]={key:float(row[n]) for key,n in [('mean_ms',4),('median_ms',5),('stddev_ms',6),('p95_ms',7),('p99_ms',8),('run_mean_stddev_ms',11)]}
        required=[{'SMAAStandardSpatialT2X','SMAAStandardTemporalResolve'},
                  {'TSCMAAPrepareCandidates','TSCMAAExtractCandidates'},
                  {'TSCMAAClearIntegratedCandidateBuffers'}]
        for i,mode in enumerate(IDS):
            assert {'SMAA','WholeFrame','SMAAGenerateCameraVelocity'}.issubset(modes[mode]),modes[mode].keys()
            assert required[i].issubset(modes[mode]),modes[mode].keys()
        assert 'TSCMAAExtractCandidates' not in modes[IDS[2]]
        changes={}
        for metric in ('SMAA','WholeFrame'):
            val=[modes[mode][metric]['mean_ms'] for mode in IDS]
            changes[metric]={'integrated_vs_standard_pct':100*(val[2]/val[0]-1),'integrated_vs_separate_pct':100*(val[2]/val[1]-1),'integrated_minus_standard_ms':val[2]-val[0]}
        result[run['label'].split('-')[0]]={'run':run,'metrics':modes,'changes':changes}
    return result

def quality(runs,bench,out,scene):
    by={r['label']:r for r in runs}
    keys=[f'{scene}-Quality-{suffix}' for suffix in ('O-1X','O-T2X-R','source-0','source-1')]
    selected=[by[k] for k in keys]
    for run in selected:
        text=report_text(run['report'])
        assert 'flythrough-wide-yaw-360' in text and 'capture [0, 479]' in text and 'Warm-up:         60' in text and '1920 x 1017' in text
    seq=[frames(r['report']) for r in selected]
    old,refID=HISTORIC[scene]
    reference=frames(bench/refID/'SS_Reference');control=frames(bench/old/'O_1X');prior=frames(bench/PRIOR_SOURCE[scene])
    rows=[[],[]];prev=[None,None];prevRef=None
    mismatches={'spatial_control':0,'separate_integrated':0,'prior_source_integrated':0}
    worst=(-1,0)
    for n in range(480):
        raw=[rgb(paths[n]) for paths in seq];ref=rgb(reference[n])
        assert all(x.shape==ref.shape==(1017,1920,3) for x in raw)
        mismatches['spatial_control']+=digest(raw[0])!=digest(rgb(control[n]))
        mismatches['separate_integrated']+=digest(raw[2])!=digest(raw[3])
        mismatches['prior_source_integrated']+=digest(raw[3])!=digest(rgb(prior[n]))
        r=ref.astype(np.float32)
        values=[raw[1].astype(np.float32),raw[3].astype(np.float32)]
        for i,v in enumerate(values):
            diff=v-r;mse=float(np.mean(diff*diff))
            row={'scene':scene,'mode':IDS[0 if i==0 else 2],'frame':n,'rgb_mae':float(np.mean(abs(diff))),
                 'psnr':float(10*np.log10(255**2/max(mse,1e-20))),'ssim':None,'edge_ratio':None,'temporal_delta_residual':None}
            if n%8==0:row.update(ssim=luma_ssim(v,r),edge_ratio=edge_strength(v)/max(edge_strength(r),1e-12))
            if prev[i] is not None:row['temporal_delta_residual']=float(np.mean(abs((v-prev[i])-(r-prevRef))))
            rows[i].append(row);prev[i]=v
        prevRef=r
        delta=rows[1][-1]['rgb_mae']-rows[0][-1]['rgb_mae']
        if delta>worst[0]:worst=(delta,n)
        if n%120==0:print(f'{scene}: reference analysis {n}/480',flush=True)
    assert not any(mismatches.values()),mismatches
    summary={'runs':dict(zip(keys,selected)),'reference':str(bench/refID),'pixel_hash_mismatch':mismatches,'windows':{}}
    for window,lo,hi in [('all',0,479),('central_motion',150,329),('transition',410,439),('post_still',440,479)]:
        summary['windows'][window]={IDS[0 if i==0 else 2]:{key:average(rr,key,lo,hi) for key in ('rgb_mae','psnr','ssim','edge_ratio','temporal_delta_residual')} for i,rr in enumerate(rows)}
    with (out/f'{scene}-quality-per-frame.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0][0]));writer.writeheader();writer.writerows(rows[0]+rows[1])
    n=worst[1]
    ims=[Image.open(reference[n]).convert('RGB'),Image.open(seq[1][n]).convert('RGB'),Image.open(seq[3][n]).convert('RGB')]
    sheet=Image.new('RGB',(1152,232),'#15191e');draw=ImageDraw.Draw(sheet)
    for i,im in enumerate(ims):
        draw.text((i*384+8,8),['Supersample spatial proxy','Original Standard SMAA T2X-R','Source SMAA integrated'][i],fill='white')
        sheet.paste(im.resize((384,203)),(i*384,28))
    sheet.save(out/f'{scene}-comparison.png');summary['representative_frame']=n
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scene',choices=['bistro','minecraft']);p.add_argument('--performance-only',action='store_true');a=p.parse_args()
    runs=json.loads(a.manifest.read_text(encoding='utf-8-sig'));a.output.mkdir(parents=True,exist_ok=True)
    dest=a.output/'comparison.json'
    result=json.loads(dest.read_text()) if dest.exists() else {'classification':'Standard T2X-R vs recovered-source SMAA adaptation; supersample spatial proxy, not temporal ground truth','quality':{}}
    if not a.performance_only:
        for scene in ([a.scene] if a.scene else HISTORIC):result['quality'][scene]=quality(runs,Path(__file__).resolve().parents[2]/'Projects/CMAA2/AutoBench',a.output,scene)
    result['performance']=performance(runs);dest.write_text(json.dumps(result,indent=2,allow_nan=False))
    print(f'PASS: {dest}',flush=True)
if __name__=='__main__':main()
