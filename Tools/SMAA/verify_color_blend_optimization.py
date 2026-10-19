"""Check that case-17 optimization candidates keep the case-17 RGB output.

Within one Optimization capture every candidate must match the case-17 mode
frame by frame; case 17 and native case 4 must also match a reference
Preservation capture (cleanup build) and the original case-17 capture record.
Hashes are SHA-256 of decoded RGB arrays, as in verify_color_blend_preservation.
"""
import argparse,csv,hashlib,json,os,re
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
RUNS=[ROOT/'tmp/color-blend-preservation-runs.json']+[Path(x) for x in os.environ.get('COLOR_BLEND_RUNS','').split(os.pathsep) if x]
CASE17='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend'
NATIVE='O-T2X-R'
MODES=[CASE17,CASE17+'+OPT-DepthStencilClear',CASE17+'+OPT-NeighborhoodNoDepth',
       CASE17+'+OPT-PresentHistory',CASE17+'+OPT-NeighborhoodNoDepth+PresentHistory',NATIVE]
FRAME_COUNT=240
SIZE=(1920,1061)

def require(ok,message):
    if not ok:raise ValueError(message)

def runs():
    seen={}
    for p in RUNS:
        if p.exists():
            for r in json.loads(p.read_text(encoding='utf-8-sig')):seen[r['report']]=r
    return list(seen.values())
def receipt(label,scene,harness):
    r=[x for x in runs() if x['label']==label and x['scene']==scene and x['phase']=='Capture' and x.get('harness','Preservation')==harness]
    require(len(r)==1,f'{label}/{scene}/{harness}: expected one receipt, got {len(r)}');r=r[0];report=Path(r['report'])
    require(hashlib.sha256(report.read_bytes()).hexdigest().upper()==r['report_sha256'].upper(),f'Report hash changed: {report}')
    text=report.read_text(encoding='utf-8-sig')
    require(re.search(r'^\s*Aggregate:\s*PASS\s*$',text,re.M) is not None and re.search(r'\bFAIL\b',text) is None,f'Incomplete/failed report: {report}')
    require(f'Scene: {scene}' in text,f'Report scene mismatch: {report}')
    require(re.search(rf'Resolution:\s*{SIZE[0]}\s*x\s*{SIZE[1]}\b',text) is not None,f'Report resolution mismatch: {report}')
    return r,Path(r['capture_root']),text

def validate_phases(text,modes):
    checks={}
    for row in csv.reader(text.splitlines()):
        row=[x.strip() for x in row]
        if not row or row[0]!='mode_check':continue
        require(len(row)>=6,f'Malformed mode_check: {row}')
        mode,frame=row[1],int(row[2]);key=(mode,frame)
        require(key not in checks,f'Duplicate mode_check: {key}')
        expected=((.25,.25) if frame%2==0 else (-.25,-.25)) if mode==NATIVE else (0.,0.)
        jitter=(float(row[3]),float(row[4]))
        require(jitter==expected and row[5]=='PASS',f'Invalid phase/state: {key}: {row[3:6]}')
        checks[key]=jitter
    expected={(m,f) for m in modes for f in range(FRAME_COUNT)}
    missing,extra=expected-checks.keys(),checks.keys()-expected
    require(not missing and not extra,f'Incomplete mode/frame checks: missing={sorted(missing)[:8]}, extra={sorted(extra)[:8]}')

def rgb(p):
    with Image.open(p) as im:
        require(im.mode=='RGB' and im.size==SIZE,f'Unexpected PNG format/size: {p}: {im.mode} {im.size}')
        return np.asarray(im).copy()
def hashes(root,mode):
    files=sorted((root/mode).glob('frame_*.png'))
    require([p.name for p in files]==[f'frame_{f:05d}.png' for f in range(FRAME_COUNT)],f'Incomplete/unexpected PNG indices: {root/mode} ({len(files)})')
    return [hashlib.sha256(rgb(p).tobytes()).hexdigest() for p in files]

def compare_hashes(a,b):
    require(len(a)==len(b)==FRAME_COUNT,'Hash record frame count is incomplete')
    return [f for f,(x,y) in enumerate(zip(a,b)) if x.lower()!=y.lower()]

def mismatch_details(root,mode,other,base,frames):
    details=[]
    for f in frames[:20]:
        a=rgb(root/mode/f'frame_{f:05d}.png').astype(np.int16)
        b=rgb(other/base/f'frame_{f:05d}.png').astype(np.int16)
        d=np.abs(a-b);ys,xs=np.nonzero(d.max(axis=2))
        details.append(dict(frame=f,changed_pixels=len(xs),max_channel_error=int(d.max()),
                            bbox=[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]))
    return details

def verify(label,reference,record_path,scene):
    r,root,text=receipt(label,scene,'Optimization');validate_phases(text,MODES)
    rr,ref,reftext=receipt(reference,scene,'Preservation');validate_phases(reftext,[CASE17,NATIVE])
    record_path=Path(record_path);doc=json.loads(record_path.read_text(encoding='utf-8-sig'))
    require(doc.get('validation')=='PASS','Original capture record is not PASS')
    require(doc.get('receipt',{}).get('scene')==scene,'Original capture record scene mismatch')
    record=doc['rgb_hashes'];h={m:hashes(root,m) for m in MODES}
    ref_h={m:hashes(ref,m) for m in [CASE17,NATIVE]};rows=[]
    for m in MODES:
        base=NATIVE if m==NATIVE else CASE17
        same=compare_hashes(h[m],h[CASE17]) if base==CASE17 else []
        cleanup=compare_hashes(h[m],ref_h[base]);original=compare_hashes(h[m],record[base])
        rows.append(dict(mode=m,frames=FRAME_COUNT,vs_case17_same_run=len(same) if base==CASE17 else None,
            vs_reference_capture=len(cleanup),vs_original_record=len(original),
            mismatch_frames=dict(same_run=same,reference=cleanup,original_record=original),
            mismatch_details=dict(same_run=mismatch_details(root,m,root,CASE17,same),reference=mismatch_details(root,m,ref,base,cleanup))))
    ok=all(row['vs_case17_same_run'] in (0,None) and row['vs_reference_capture']==row['vs_original_record']==0 for row in rows)
    return dict(scene=scene,label=label,executable_sha256=r['executable_sha256'],reference=reference,
        reference_executable_sha256=rr['executable_sha256'],report=r['report'],report_sha256=r['report_sha256'],
        record=str(record_path),record_sha256=hashlib.sha256(record_path.read_bytes()).hexdigest(),
        resolution=list(SIZE),expected_modes=len(MODES),frames_per_mode=FRAME_COUNT,
        comparison='decoded RGB only; alpha equality and quality improvement are not certified',
        modes=rows,validation='PASS' if ok else 'MISMATCH')

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('label');ap.add_argument('--reference',required=True);ap.add_argument('--record',required=True)
    ap.add_argument('--scene',required=True,choices=['bistro','minecraft']);ap.add_argument('--out');x=ap.parse_args(argv)
    try:res=verify(x.label,x.reference,x.record,x.scene)
    except (OSError,ValueError,KeyError,TypeError) as error:
        res=dict(scene=x.scene,label=x.label,validation='FAIL',error=str(error))
    txt=json.dumps(res,indent=1);print(txt)
    if x.out:Path(x.out).parent.mkdir(parents=True,exist_ok=True);Path(x.out).write_text(txt+'\n',encoding='utf-8')
    return 0 if res['validation']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
