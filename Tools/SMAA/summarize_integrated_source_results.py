"""Create a compact, validated result bundle for the integrated source comparison."""
import argparse,csv,hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_integrated_source_comparison import IDS

def main():
    p=argparse.ArgumentParser();p.add_argument('--comparison',type=Path,required=True);p.add_argument('--equivalence',type=Path,required=True)
    p.add_argument('--cgvqm-jobs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    comparison=json.loads(a.comparison.read_text());eq=json.loads(a.equivalence.read_text());jobs=json.loads(a.cgvqm_jobs.read_text())
    assert eq['validation']=='PASS' and set(comparison['quality'])==set(comparison['performance'])=={'bistro','minecraft'}
    assert len(jobs)==8 and {(r['scene'],r['mode'],r['window']) for r in jobs}=={(s,m,w) for s in ('bistro','minecraft') for m in ('standard','integrated') for w in ('central','transition')}
    records=[]
    for job in jobs:
        assert hashlib.sha256(Path(job['result']).read_bytes()).hexdigest()==job['result_sha256']
        records.append(json.loads(Path(job['result']).read_text()))
        assert job['reused_pixel_identical_source']==(job['mode']=='integrated')
        other=next(r for r in jobs if r['scene']==job['scene'] and r['window']==job['window'] and r['mode']!=job['mode'])
        assert other['reference_pixel_sha256']==job['reference_pixel_sha256']
        job['delta_from_standard']=job['score']-(job['score'] if job['mode']=='standard' else other['score'])
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'comparison.json').write_text(json.dumps(comparison,indent=2))
    (a.output/'equivalence.json').write_text(json.dumps(eq,indent=2))
    assert all(r['runtime']==records[0]['runtime'] and r['configuration']==records[0]['configuration'] for r in records)
    assert all(r['official_cgvqm']['commit']==records[0]['official_cgvqm']['commit'] for r in records)
    assert all(r[f'{side}_round_trip']['mismatched_values']==0 for r in records for side in ('test','reference'))
    (a.output/'cgvqm.json').write_text(json.dumps({'validation':'PASS','scope':'CGVQM-2; spatial proxy, not temporal ground truth',
        'official_commit':records[0]['official_cgvqm']['commit'],'runtime':records[0]['runtime'],'configuration':records[0]['configuration'],
        'round_trip_mismatched_values':0,'fresh_standard_runs':4,'pixel_identical_source_reused_runs':4,'runs':jobs},indent=2))
    with (a.output/'cgvqm.csv').open('w',newline='') as f:
        fields=['scene','mode','window','score','delta_from_standard','reused_pixel_identical_source','verified_current_pixel_sha256','reference_pixel_sha256']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(jobs)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    colors=['#466b97','#c5a36b','#358b76']
    for j,scene in enumerate(('bistro','minecraft')):
        values=[comparison['performance'][scene]['metrics'][mode]['SMAA']['mean_ms'] for mode in IDS]
        spread=[comparison['performance'][scene]['metrics'][mode]['SMAA']['run_mean_stddev_ms'] for mode in IDS]
        ax=axes[j];bars=ax.bar(['Standard T2X-R','Source separate','Source integrated'],values,color=colors,yerr=spread,capsize=3)
        ax.bar_label(bars,fmt='%.3f ms',padding=4);ax.set_ylim(0,max(values)*1.23);ax.set_ylabel('Total AA GPU time (ms), lower is better');ax.set_title(scene.title());ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.suptitle('Original SMAA: Standard T2X vs recovered-source adaptation\nRTX 3060 Ti | 1920 x 1017 | 4,800 frames x 3 | error bars: SD of 3 run means',fontsize=12)
    fig.savefig(a.output/'aa-performance.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for j,scene in enumerate(('bistro','minecraft')):
        ax=axes[j]
        for i,mode in enumerate(('standard','integrated')):
            values=[next(r['score'] for r in jobs if (r['scene'],r['mode'],r['window'])==(scene,mode,w)) for w in ('central','transition')]
            bars=ax.bar([i*.36,1+i*.36],values,width=.32,color=colors[0 if i==0 else 2],label='Standard T2X-R' if i==0 else 'Source integrated (hash-bridged)')
            ax.bar_label(bars,fmt='%.2f',padding=3,fontsize=9)
        ax.set_xticks([.18,1.18],['Central motion','Motion to still']);ax.set_ylim(0,110);ax.set_ylabel('CGVQM-2, higher is better');ax.set_title(scene.title());ax.legend(fontsize=8,loc='lower left');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.suptitle('Supersample spatial-reference proxy; not temporal ground truth',fontsize=12)
    fig.savefig(a.output/'cgvqm-comparison.png',dpi=160);plt.close(fig)
    print('PASS: result bundle and figures written')
if __name__=='__main__':main()
