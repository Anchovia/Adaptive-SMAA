"""Collect gate evidence and draw a static comparison figure."""
import json, shutil
from pathlib import Path
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from analyze_candidate_selection_gate import ROOT, OUT, IDS, read

def main():
    target=ROOT/'Docs/Candidate-Selection-Gate-20260915';target.mkdir(parents=True,exist_ok=True)
    names=['short','regressions','smoke','quality','masks','performance','publication-bridge']
    for name in names:
        data=read(OUT/f'{name}.json');assert data['status']=='PASS'
        shutil.copy2(OUT/f'{name}.json',target/f'{name}.json')
    shutil.copy2(OUT/'runs.json',target/'runs.json')
    assert len(read(target/'media.json')) == 4
    shutil.copy2(OUT/'readiness-incidents.json',target/'readiness-incidents.json')
    shutil.copy2(OUT/'pre-publication-fix-runs.json',target/'pre-publication-fix-runs.json')
    for run in read(OUT/'runs.json'):
        if run['label'].endswith(('-Smoke','-Benchmark')) or run['label'].startswith('material-publication-'):
            reports=list(Path(run['report']).glob('*_results.csv'))
            assert len(reports)==1
            shutil.copy2(reports[0],target/f"{run['label']}-results.csv")
    for scene in ('bistro','minecraft'):
        shutil.copy2(OUT/f'{scene}-per-frame.csv',target/f'{scene}-per-frame.csv')
    q=read(OUT/'quality.json');p=read(OUT/'performance.json');comparisons=[]
    fig,axes=plt.subplots(2,2,figsize=(11,7.4));colors=['#64748b','#0f766e','#c26923'];labels=['Standard T2X-R','Document candidate','Source candidate']
    for column,scene in enumerate(('bistro','minecraft')):
        ax=axes[0,column]
        for i,key in enumerate(('O-T2X-R','profile-0','profile-1')):
            scores=[next(r['score'] for r in q['cgvqm'] if (r['scene'],r['key'],r['window'])==(scene,key,w)) for w in ('central','transition')]
            ax.bar(np.arange(2)+(i-1)*0.24,scores,width=.24,color=colors[i],label=labels[i])
        ax.set_xticks([0,1],['Central motion','Motion to still']);ax.set_ylim(90,100);ax.set_ylabel('CGVQM-2 (higher is better)');ax.set_title(scene.capitalize());ax.grid(axis='y',alpha=.15)
        metrics=p['scenes'][scene]['metrics'];ax=axes[1,column]
        times=[metrics[m]['SMAA']['mean_ms'] for m in IDS];sd=[metrics[m]['SMAA']['run_mean_stddev_ms'] for m in IDS]
        ax.bar(range(3),times,color=colors,yerr=sd,capsize=4);ax.set_xticks(range(3),['Standard','Doc candidate','Source candidate']);ax.set_ylabel('Whole SMAA GPU time (ms)');ax.grid(axis='y',alpha=.15)
        for i,value in enumerate(times):ax.annotate(f'{value:.3f}',(i,value),xytext=(0,7),textcoords='offset points',ha='center')
        ax.set_ylim(0,max(times)*1.25)
        for window in ('central','transition'):
            selected={r['key']:r['score'] for r in q['cgvqm'] if r['scene']==scene and r['window']==window}
            comparisons.append(dict(scene=scene,window=window,source_minus_document_cgvqm=selected['profile-1']-selected['profile-0'],
                document_minus_standard_cgvqm=selected['profile-0']-selected['O-T2X-R'],source_minus_standard_cgvqm=selected['profile-1']-selected['O-T2X-R']))
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=3,bbox_to_anchor=(.5,.95),frameon=False)
    fig.suptitle('Candidate-only comparison with Standard T2X-R control',y=.995)
    fig.subplots_adjust(top=.85,bottom=.14,hspace=.33,wspace=.25)
    fig.text(.5,.025,'Selective modes share the document kernel; Standard retains its native temporal settings.\nQuality: wide camera path; verified pixel-exact reuse of spatial-reference scores.\nTiming: separate flythrough; 4,800 frames x 3, readback off. Error bars: run-mean SD. CGVQM axis starts at 90.',ha='center',fontsize=9)
    fig.savefig(target/'quality-performance.svg');fig.savefig(OUT/'quality-performance.png',dpi=140);plt.close(fig)
    (target/'comparisons.json').write_text(json.dumps(comparisons,indent=2))
    print(json.dumps(comparisons,indent=2))
if __name__=='__main__':main()
