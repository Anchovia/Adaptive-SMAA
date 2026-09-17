"""Validate contrast capture semantics and summarize paired native timings."""
import argparse,csv,hashlib,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

def rgb(p):
    with Image.open(p) as im:return np.asarray(im.convert('RGB'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def reuse_capture(folder,out,existing):
    # Only reuse derived CPU calculations when every new PNG is byte-exact.
    data=json.loads((existing/'quality.json').read_text())
    assert all(v==0 for v in data['checks'].values())
    old=Path(data['source'])
    files=sorted(p.relative_to(folder) for p in folder.glob('*/*.png'))
    assert len(files)==2160
    assert files==sorted(p.relative_to(old) for p in old.glob('*/*.png'))
    assert all(digest(folder/f)==digest(old/f) for f in files)
    for report in folder.glob('*_results.csv'):
        assert 'Aggregate: PASS' in report.read_text(encoding='utf-8-sig')
    data['source']=str(folder)
    data['exact_png_analysis_bridge']={'cached_analysis':str(existing),'frames':len(files),'mismatches':0}
    for f in existing.iterdir():
        if f.name!='quality.json' and f.is_file():shutil.copy2(f,out/f.name)
    (out/'quality.json').write_text(json.dumps(data,indent=2)+'\n')
    print('PASS: all 2160 new PNG hashes match; reuse exact CPU analysis')
def capture(folder,out):
    names=['O-T2X-R','ABL-Contrast-All-R','ABL-Contrast-0005-R','ABL-Contrast-001-R',
           'ABL-Contrast-002-R','ABL-Contrast-None-R','DBG-CurrentSpatial-R',
           'DBG-ContrastMask-001-R','O-T2X-R-Repeat']
    paths={n:sorted((folder/n).glob('frame_*.png')) for n in names}
    assert all(len(p)==240 for p in paths.values())
    expected=[f'frame_{i:05d}.png' for i in range(240)]
    assert all([f.name for f in p]==expected for p in paths.values())
    checks={'native_repeat_mismatched_values':0,'all_native_mismatched_values':0,
            'none_spatial_mismatched_values':0,'selected_native_mismatched_values':0,
            'bypassed_spatial_mismatched_values':0}
    rows=[];prev={};coverage=[];size=None
    for i in range(240):
        images={n:rgb(p[i]) for n,p in paths.items()}
        if size is None:size=list(images[names[0]].shape)
        assert all(list(im.shape)==size for im in images.values())
        base=images['O-T2X-R'];spatial=images['DBG-CurrentSpatial-R']
        checks['native_repeat_mismatched_values']+=int(np.count_nonzero(base!=images['O-T2X-R-Repeat']))
        checks['all_native_mismatched_values']+=int(np.count_nonzero(base!=images['ABL-Contrast-All-R']))
        checks['none_spatial_mismatched_values']+=int(np.count_nonzero(spatial!=images['ABL-Contrast-None-R']))
        mask=images['DBG-ContrastMask-001-R'][:,:,0]
        assert np.all((mask==0)|(mask==255))
        selected=mask==255;test=images['ABL-Contrast-001-R']
        checks['selected_native_mismatched_values']+=int(np.count_nonzero(test[selected]!=base[selected]))
        checks['bypassed_spatial_mismatched_values']+=int(np.count_nonzero(test[~selected]!=spatial[~selected]))
        coverage.append(float(selected.mean()))
        for n in names[:6]:
            im=images[n];lum=im.astype(np.float32)@np.array([.2126,.7152,.0722],np.float32)
            rows.append({'frame':i,'mode':n,'rgb_mae_vs_native':float(np.abs(im.astype(np.int16)-base).mean()),
                'luma_delta1':float(np.abs(lum-prev[n]).mean()) if n in prev else None})
            prev[n]=lum
        if i in (90,179,180,239):
            sheet=Image.new('RGB',(1600,508),'#15181c');d=ImageDraw.Draw(sheet)
            for col,n in enumerate(['O-T2X-R','ABL-Contrast-0005-R','ABL-Contrast-001-R','ABL-Contrast-002-R']):
                sheet.paste(Image.fromarray(images[n]).resize((400,221)),(col*400,27))
                diff=np.clip(np.abs(images[n].astype(np.int16)-base)*8,0,255).astype(np.uint8)
                sheet.paste(Image.fromarray(diff).resize((400,221)),(col*400,278))
                d.text((col*400+5,7),n,fill='white')
                d.text((col*400+5,257),'difference to native x8',fill='white')
            sheet.save(out/f'frame_{i:03d}.png')
        if i%60==59:print(f'Analyzed {i+1}/240',flush=True)
    summary={}
    for n in names[:6]:
        moving=[r for r in rows if r['mode']==n and 60<=r['frame']<180]
        still=[r for r in rows if r['mode']==n and 200<=r['frame']<240]
        hashes=[digest(p) for p in paths[n][200:240]]
        summary[n]={'moving_rgb_mae_vs_native':float(np.mean([r['rgb_mae_vs_native'] for r in moving])),
            'late_still_luma_delta1':float(np.mean([r['luma_delta1'] for r in still])),
            'late_still_unique_png':len(set(hashes)),
            'two_frame_equal_of_38':sum(a==b for a,b in zip(hashes,hashes[2:]))}
    gifframes=[]
    for i in range(200,220):
        canvas=Image.new('RGB',(1440,388),'#15181c');draw=ImageDraw.Draw(canvas)
        for col,n in enumerate(['O-T2X-R','ABL-Contrast-001-R','ABL-Contrast-002-R']):
            with Image.open(paths[n][i]) as im:
                # Fixed central ROI; no metric-driven worst-case selection.
                crop=im.convert('RGB').crop((720,350,1200,710))
                canvas.paste(crop,(col*480,28))
            draw.text((col*480+5,8),f'{n} | frame {i} | 3x slow',fill='white')
        gifframes.append(canvas)
    gifpath=out/'late-still-3x-slow.gif'
    gifframes[0].save(gifpath,save_all=True,append_images=gifframes[1:],duration=50,loop=0,disposal=2)
    with Image.open(gifpath) as im:assert im.n_frames==20
    with (out/'per-frame.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    result={'source':str(folder),'shape':size,'checks':checks,'modes':summary,
        'coverage_at_threshold_001':{'mean':float(np.mean(coverage)),'min':min(coverage),'max':max(coverage)},
        'scope':'Engineering correctness and temporal stability; native differences are not ground-truth quality scores.'}
    (out/'quality.json').write_text(json.dumps(result,indent=2)+'\n')
    assert all(v==0 for v in checks.values()),checks
    print('PASS: native repeat, all/native, none/spatial, selected/native, bypassed/spatial')

def performance(path,out):
    text=path.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text
    rows=[]
    for line in text.splitlines():
        v=[s.strip() for s in next(csv.reader([line]))]
        if v and v[0]=='timing':rows.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),mean_ms=float(v[5]),p95_ms=float(v[6])))
    assert len(rows)==54,(len(rows),'expected 6 configurations x3 metrics x3 repeats')
    means={}
    for mode in sorted(set(r['mode'] for r in rows)):
        means[mode]={}
        for metric in ('SMAA','Spatial','Resolve'):
            cells=sorted([r for r in rows if r['mode']==mode and r['metric']==metric],key=lambda r:r['run'])
            assert [r['run'] for r in cells]==[0,1,2]
            assert all(r['samples']==4800 and np.isfinite(r['mean_ms']) and r['mean_ms']>0 for r in cells)
            a=np.array([r['mean_ms'] for r in cells]);means[mode][metric]={'mean_ms':float(a.mean()),'run_std_ms':float(a.std(ddof=1)),'runs_ms':a.tolist()}
    for mode,data in means.items():
        for metric,values in data.items():values['percent_vs_native']=(values['mean_ms']/means['O-T2X-R'][metric]['mean_ms']-1)*100
    result={'source':str(path),'rows':rows,'modes':means,'report_sha256':digest(path)}
    (out/'performance.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: complete paired performance matrix')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path);p.add_argument('--performance',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--reuse-analysis',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if a.capture:
        if a.reuse_analysis:reuse_capture(a.capture,a.output,a.reuse_analysis)
        else:capture(a.capture,a.output)
    if a.performance:performance(a.performance,a.output)
