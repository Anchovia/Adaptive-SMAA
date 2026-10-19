"""Fail closed on incomplete captures and compare every candidate to case18 and original records."""
import argparse, hashlib, json, csv
from pathlib import Path
import verify_color_blend_optimization as v
CASE18=v.CASE17+'+OPT-NeighborhoodNoDepth+PresentHistory'
MODES=[v.NATIVE,v.CASE17,CASE18,'ABL-ET2X-R-Case19-EdgeRGBA8','ABL-ET2X-R-Case19-GatherLuma','ABL-ET2X-R-Case19-EdgeRGBA8-GatherLuma']
def verify(label,scene,baseline_runs,record):
    r,root,text=v.receipt(label,scene,'Case19');v.validate_phases(text,MODES)
    states=[]
    for row in csv.reader(text.splitlines()):
        row=[x.strip() for x in row]
        if row and row[0]=='edge_storage':states.append(row)
    v.require(len(states)==len(MODES) and {row[1] for row in states}==set(MODES),'Missing/duplicate actual edge formats')
    for row in states:
        expected=28 if 'Case19-EdgeRGBA8' in row[1] else 49
        v.require(int(row[2])==expected and row[3]=='PASS',f'Wrong actual edge format: {row}')
    refs=json.loads(Path(baseline_runs).read_text(encoding='utf-8-sig'))
    refs=[x for x in refs if x['harness']=='Optimization' and x['scene']==scene and x['phase']=='Capture' and x['label']=='opt-d']
    v.require(len(refs)==1,'Expected one preserved case18 capture');rr=refs[0]
    v.require(hashlib.sha256(Path(rr['report']).read_bytes()).hexdigest().upper()==rr['report_sha256'].upper(),'Preserved report changed')
    baseline=v.hashes(Path(rr['capture_root']),CASE18)
    record=Path(record);doc=json.loads(record.read_text(encoding='utf-8-sig'))
    v.require(doc['validation']=='PASS' and doc['receipt']['scene']==scene,'Wrong original capture record')
    hashes={m:v.hashes(root,m) for m in MODES};rows=[]
    for mode in MODES:
        ref=v.NATIVE if mode==v.NATIVE else v.CASE17
        original=v.compare_hashes(hashes[mode],doc['rgb_hashes'][ref])
        same=[] if mode==v.NATIVE else v.compare_hashes(hashes[mode],hashes[CASE18])
        previous=[] if mode==v.NATIVE else v.compare_hashes(hashes[mode],baseline)
        rows.append(dict(mode=mode,vs_same_run_case18=same,vs_preserved_case18=previous,vs_original_record=original,
            mismatch_details=v.mismatch_details(root,mode,root,CASE18,same)))
    ok=all(not any(row[k] for k in ['vs_same_run_case18','vs_preserved_case18','vs_original_record']) for row in rows)
    return dict(validation='PASS' if ok else 'MISMATCH',scene=scene,frames_per_mode=240,expected_modes=len(MODES),
        receipt=r,preserved_case18_receipt=rr,record=str(record),record_sha256=hashlib.sha256(record.read_bytes()).hexdigest(),
        actual_edge_formats=states,modes=rows,rgb_hashes=hashes,scope='Decoded RGB; no new quality improvement or universal all-scene equivalence claim')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('label');ap.add_argument('--scene',required=True);ap.add_argument('--baseline-runs',required=True)
    ap.add_argument('--record',required=True);ap.add_argument('--out',required=True);x=ap.parse_args()
    try:result=verify(x.label,x.scene,x.baseline_runs,x.record)
    except (OSError,ValueError,KeyError,TypeError) as e:result=dict(validation='FAIL',error=str(e))
    Path(x.out).write_text(json.dumps(result,indent=1)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['validation','scene','frames_per_mode','expected_modes','error'] if k in result}))
    raise SystemExit(0 if result['validation']=='PASS' else 1)
if __name__=='__main__':main()
