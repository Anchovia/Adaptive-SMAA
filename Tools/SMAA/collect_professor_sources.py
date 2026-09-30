import hashlib,json,statistics,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def blob(ref,path):return subprocess.check_output(['git','show',f'{ref}:{path}'],cwd=ROOT)
def doc(ref,path):return json.loads(blob(ref,path))
base=doc('519d211','Docs/Six-Case-Stencil-Lifecycle/summary.json')
records={'sources':{},'performance':[],'quality':list(base['quality']),'short_captures':{},'stencil':{},'branch_records':base['branches']}
for b in base['branches']:
 n=str(b['case']);records['short_captures'][n]={}
 for s in ('bistro','minecraft'):
  cap=doc(b['commit'],f'Docs/Stencil-Lifecycle-Refresh/{s}-capture.json')
  hashes=doc(b['commit'],f'Docs/Stencil-Lifecycle-Refresh/{s}-rgb-hashes.json')
  conf=doc(b['commit'],'Docs/Stencil-Lifecycle-Refresh/case.json')
  records['short_captures'][n][s]=dict(capture_root=cap['capture'],mode=conf['target'],hashes=hashes[conf['target']],commit=b['commit'])
for p in base['performance']:
 if p['case'] not in (4,6):records['performance'].append(dict(**p,repeats=6,frames_per_run=4800,source='519d211 six-case refresh'))
for s in ('bistro','minecraft'):
 benchmark=doc('9e8461a',f'Docs/Edge-Persistence-Cost-Audit/{s}-benchmark.json')
 cap=doc('9e8461a',f'Docs/Edge-Persistence-Cost-Audit/{s}-capture.json')
 control=benchmark['runs']['O-T2X-R']
 for n,m in ((4,'O-T2X-R'),(6,'A-CurrentEdge-Stencil'),(7,'B-PreviousRawEdge-Depth'),(8,'E-PreviousRawEdge-FirstStencil')):
  measures=benchmark['runs'][m]
  mean=lambda key:statistics.mean(measures[key])
  den=lambda key:statistics.mean(control[key])
  records['performance'].append(dict(case=n,scene=s,target=m,total_ms=mean('SMAA'),paired_t2x_r_total_ms=den('SMAA'),total_change_percent=(mean('SMAA')/den('SMAA')-1)*100,resolve_ms=mean('SR_Resolve'),paired_t2x_r_resolve_ms=den('SR_Resolve'),resolve_change_percent=(mean('SR_Resolve')/den('SR_Resolve')-1)*100,repeats=3,frames_per_run=4800,source='9e8461a paired cost audit'))
  records['short_captures'].setdefault(str(n),{})[s]=dict(capture_root=cap['capture_root'],mode=m,hashes=cap['output_hashes'][m],commit='9e8461a')
 q=doc('7095e4b',f'Docs/Edge-Persistence-GPU/{s}-cgvqm.json')
 for n in (7,8):
  records['quality'].append(dict(case=n,scene=s,moving=q['results']['moving']['scores']['ABL-Spatial-PreviousRawEdge-Depth-PatternOff-R'],transition=q['results']['transition']['scores']['ABL-Spatial-PreviousRawEdge-Depth-PatternOff-R'],source='7095e4b',reused_by_rgb_equality=n==8))
 records['stencil'][s]=doc('experiment/smaa-1x-stencil-clear',f'Docs/SMAA-1X-Stencil-Clear/{s}-benchmark.json')
for ref,path in [('experiment/smaa-1x-stencil-clear','Docs/SMAA-1X-Stencil-Clear/report.md'),('519d211','Docs/Six-Case-Stencil-Lifecycle/report.md'),('7095e4b','Docs/Edge-Persistence-GPU/results-ko.md'),('9e8461a','Docs/Edge-Persistence-Cost-Audit/results-ko.md')]:
 raw=blob(ref,path);records['sources'][path]=dict(ref=ref,sha256=hashlib.sha256(raw).hexdigest(),text=raw.decode('utf-8-sig'))
(ROOT/'tmp/professor-sources.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for n in range(1,9):
 out=[p for p in records['performance'] if p['case']==n]
 print(n,[(p['scene'],round(p['total_ms'],6),round(p['total_change_percent'],2)) for p in out])
print('quality7/8',[(q['case'],q['scene'],q['moving'],q['transition']) for q in records['quality'] if q['case']>=7])
