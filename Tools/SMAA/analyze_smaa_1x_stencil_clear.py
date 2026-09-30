"""Validate the isolated original-SMAA-1X stencil initialization experiment."""
import argparse,csv,hashlib,json,statistics,subprocess
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/SMAA-1X-Stencil-Clear'
BASE='c51ca2896979c78d7fd10c208303c0420a819c76'
MODES=['O-1X-LegacyStencil','O-1X-ClearStencil']
CAPTURE_MODES=MODES+[m+'-Repeat' for m in MODES]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,data):
    DOC.mkdir(parents=True,exist_ok=True)
    (DOC/name).write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def rgb(path):
    with Image.open(path) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(path,im.mode,im.size)
        return np.array(im)
def receipt(scene,phase,path):
    records=json.loads(path.read_text(encoding='utf-8-sig'))
    selected=[r for r in records if r['scene']==scene and r['phase']==phase]
    assert len(selected)==1
    r=selected[0];report=Path(r['report']);assert sha(report)==r['report_sha256'].lower()
    text=report.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'Aggregate: FAIL' not in text
    rows=[[x.strip() for x in row] for row in csv.reader(text.splitlines())]
    audit=json.loads((DOC/'source-audit.json').read_text(encoding='utf-8'))
    assert audit['executable_sha256']==r['executable_sha256'].lower()
    return r,report,rows

def audit():
    core=[]
    for path in git('ls-tree','-r','--name-only',BASE,'Projects/CMAA2/SMAA').decode().splitlines():
        if path.endswith(('vaSMAAWrapper.h','vaSMAAWrapperDX11.cpp')):continue
        local=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
        original=git('show',BASE+':'+path).replace(b'\r\n',b'\n')
        assert local==original,path
        core.append(dict(path=path,normalized_sha256=hashlib.sha256(local).hexdigest()))
    wrapper=(ROOT/'Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp').read_text()
    assert wrapper.count('ClearDepthStencilView')==1
    assert 'if( m_oneXStencilClear )' in wrapper and 'D3D11_CLEAR_STENCIL, 1.0f, 0' in wrapper
    official=ROOT/'tmp/stencil-clear-official'
    tree=json.loads((official/'tree.json').read_text())
    demo=(official/'Demo_DX10_Code_Demo.cpp').read_text(encoding='utf-8')
    assert 'device->ClearDepthStencilView(*rtc.mainDS, D3D10_CLEAR_DEPTH | D3D10_CLEAR_STENCIL, 1.0, 0);' in demo
    proof={p.name:sha(p) for p in official.iterdir() if p.is_file() and p.name!='tree.json'}
    changed={p:sha(ROOT/p) for p in ['Projects/CMAA2/CMAA2Sample.cpp','Projects/CMAA2/OneXStencilClearVerification.inl','Projects/CMAA2/SMAA/vaSMAAWrapper.h','Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp']}
    write('source-audit.json',dict(validation='PASS',baseline=BASE,branch=git('branch','--show-current').decode().strip(),
        unchanged_core=core,changed_sources=changed,official_commit=tree['sha'],official_file_hashes=proof,
        official_clear_lines=[596,601],official_one_x_call_line=686,official_per_frame_clear_line=739,
        executable_sha256=sha(ROOT/'Projects/CMAA2/CMAA2.exe'),
        interpretation='Official demo clears the shared main stencil before SMAA; our wrapper has a separate uncleared SMAA stencil. Not a new SMAA algorithm.'))
    print('PASS source audit:',len(core),'unchanged files',flush=True)

def capture(scene,path):
    r,report,rows=receipt(scene,'Capture',path)
    checks=[row for row in rows if row and row[0]=='mode_check'];assert len(checks)==960
    counts={}
    for m in CAPTURE_MODES:
        group=[row for row in checks if row[1]==m]
        assert [int(row[2]) for row in group]==list(range(240))
        assert all(row[3:7]==['Clear' if 'ClearStencil' in m else 'Legacy','TemporalOff','NoR','PASS'] for row in group)
        counts[m]=[int(row[7]) for row in group];assert min(counts[m])>0
        assert [p.name for p in sorted((report.parent/m).glob('*.png'))]==[f'frame_{i:05d}.png' for i in range(240)]
    old=json.loads((ROOT/f'Docs/Baseline-Restart/{scene}-capture.json').read_text(encoding='utf-8'))
    oldroot=Path(old['capture'])/'O-1X'
    hashes={m:[] for m in CAPTURE_MODES};resultrows=[]
    totals=dict(clear_vs_legacy_mismatch_frames=0,clear_vs_legacy_changed_pixels=0,max_channel_error=0,repeat_mismatch_frames=0,old_1x_mismatch_frames=0)
    mae=[]
    for i in range(240):
        name=f'frame_{i:05d}.png';ims={m:rgb(report.parent/m/name) for m in CAPTURE_MODES}
        for m,im in ims.items():hashes[m].append(hashlib.sha256(im.tobytes()).hexdigest())
        diff=np.abs(ims[MODES[1]].astype(np.int16)-ims[MODES[0]].astype(np.int16))
        pixels=int(np.any(diff!=0,axis=2).sum());maximum=int(diff.max());error=float(diff.mean())
        totals['clear_vs_legacy_mismatch_frames']+=int(pixels>0);totals['clear_vs_legacy_changed_pixels']+=pixels
        totals['max_channel_error']=max(totals['max_channel_error'],maximum);mae.append(error)
        for m in MODES:totals['repeat_mismatch_frames']+=int(not np.array_equal(ims[m],ims[m+'-Repeat']))
        totals['old_1x_mismatch_frames']+=int(not np.array_equal(ims[MODES[0]],rgb(oldroot/name)))
        resultrows.append(dict(frame=i,changed_pixels=pixels,max_channel_error=maximum,rgb_mae=error,
            legacy_ps_invocations=counts[MODES[0]][i],clear_ps_invocations=counts[MODES[1]][i],
            legacy_rgb_sha256=hashes[MODES[0]][-1],clear_rgb_sha256=hashes[MODES[1]][-1]))
        if i%60==59:print(scene,i+1,'/240 validated',flush=True)
    assert totals['repeat_mismatch_frames']==0,totals
    assert totals['clear_vs_legacy_mismatch_frames']==0,totals
    assert totals['old_1x_mismatch_frames']==0,totals
    static={m:{w:len(set(hashes[m][start:end])) for w,start,end in [('initial',20,60),('late',200,240)]} for m in MODES}
    assert all(n==1 for v in static.values() for n in v.values()),static
    summary={m:{w:statistics.mean(counts[m][start:end]) for w,start,end in [('all',0,240),('moving',60,180),('late',200,240)]} for m in MODES}
    oldq=json.loads((ROOT/f'Docs/Baseline-Restart/{scene}-cgvqm.json').read_text(encoding='utf-8'))
    score={w:v['smaa_1x_score'] for w,v in oldq['results'].items()}
    write(f'{scene}-capture.json',dict(validation='PASS',scene=scene,receipt=r,frames_per_mode=240,mode_checks=960,
        comparisons=totals,rgb_mae=statistics.mean(mae),static_unique_rgb=static,spatial_ps_invocations=summary,
        old_1x_capture=str(oldroot),old_capture_metadata_sha256=sha(ROOT/f'Docs/Baseline-Restart/{scene}-capture.json'),
        quality=dict(method='Pixel-exact RGB equivalence to existing 1X; no new CGVQM model run',scores_both_modes=score,
                     score_difference=0,source_sha256=sha(ROOT/f'Docs/Baseline-Restart/{scene}-cgvqm.json'))))
    with (DOC/f'{scene}-frames.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=resultrows[0]);writer.writeheader();writer.writerows(resultrows)
    print(json.dumps(dict(scene=scene,comparisons=totals,PSInvocations=summary)),flush=True)

def performance(scene,phase,path):
    r,report,rows=receipt(scene,phase,path)
    samples=240 if phase=='Smoke' else 4800;repeats=1 if phase=='Smoke' else 6
    timing=[row for row in rows if row and row[0]=='timing'];assert len(timing)==2*2*repeats
    modes={}
    for m in MODES:
        modes[m]={}
        for metric in ['SMAA','WallFrame']:
            group=sorted([row for row in timing if row[1]==m and row[3]==metric],key=lambda row:int(row[2]))
            assert [int(row[2]) for row in group]==list(range(repeats))
            assert all(int(row[4])==samples for row in group)
            means=[float(row[5]) for row in group];assert min(means)>0
            modes[m][metric]=dict(mean_ms=statistics.mean(means),run_mean_std_ms=statistics.stdev(means) if repeats>1 else None,
                run_means_ms=means,mean_run_median_ms=statistics.mean(float(row[6]) for row in group),
                mean_run_p95_ms=statistics.mean(float(row[7]) for row in group),mean_run_p99_ms=statistics.mean(float(row[8]) for row in group),
                mean_frame_stddev_ms=statistics.mean(float(row[9]) for row in group),
                mean_slowest_one_percent_equivalent_fps=statistics.mean(float(row[10]) for row in group))
    contrasts={}
    for metric in ['SMAA','WallFrame']:
        a=modes[MODES[0]][metric];b=modes[MODES[1]][metric]
        contrasts[metric]=dict(change_percent=(b['mean_ms']/a['mean_ms']-1)*100,
            difference_ms=b['mean_ms']-a['mean_ms'],paired_run_change_percent=[(y/x-1)*100 for x,y in zip(a['run_means_ms'],b['run_means_ms'])])
    write(f'{scene}-{phase.lower()}.json',dict(validation='PASS',scene=scene,phase=phase,receipt=r,
        frames_per_mode_run=samples,repeats=repeats,modes=modes,contrasts=contrasts,
        classification='Paired same-executable 1X stencil-clear-only engineering GPU timing; hidden; no capture/readback/query.'))
    print(json.dumps(dict(scene=scene,phase=phase,contrasts=contrasts)),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['audit','Capture','Smoke','Benchmark'])
    p.add_argument('--scene',choices=['bistro','minecraft']);p.add_argument('--receipt',type=Path,default=ROOT/'tmp/smaa-1x-stencil-clear-runs.json');a=p.parse_args()
    if a.phase=='audit':audit()
    elif a.phase=='Capture':capture(a.scene,a.receipt)
    else:performance(a.scene,a.phase,a.receipt)
if __name__=='__main__':main()
