"""Check that case-17 optimization candidates keep the case-17 RGB output.

Within one Optimization capture every candidate must match the case-17 mode
frame by frame; case 17 and native case 4 must also match a reference
Preservation capture (cleanup build) and the original case-17 capture record.
Hashes are SHA-256 of decoded RGB arrays, as in verify_color_blend_preservation.
"""
import argparse,hashlib,json,os,re
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
RUNS=[ROOT/'tmp/color-blend-preservation-runs.json']+[Path(x) for x in os.environ.get('COLOR_BLEND_RUNS','').split(os.pathsep) if x]
CASE17='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend'
NATIVE='O-T2X-R'

def runs():
    seen={}
    for p in RUNS:
        if p.exists():
            for r in json.loads(p.read_text(encoding='utf-8-sig')):seen[r['report']]=r
    return list(seen.values())
def receipt(label,scene,harness):
    r=[x for x in runs() if x['label']==label and x['scene']==scene and x['phase']=='Capture' and x.get('harness','Preservation')==harness]
    assert len(r)==1,(label,scene,harness,len(r));r=r[0];report=Path(r['report'])
    assert hashlib.sha256(report.read_bytes()).hexdigest().upper()==r['report_sha256']
    text=report.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and not re.search(r',\s*FAIL\s*(?:,|$)',text,re.M)
    return r,Path(r['capture_root']),text
def rgb(p):
    with Image.open(p) as im:assert im.mode=='RGB' and im.size==(1920,1061);return np.asarray(im).copy()
def hashes(root,mode):
    files=sorted((root/mode).glob('frame_?????.png'));assert [int(p.stem[6:]) for p in files]==list(range(240)),(mode,len(files))
    return [hashlib.sha256(rgb(p).tobytes()).hexdigest() for p in files]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('label');ap.add_argument('--reference',required=True);ap.add_argument('--record',required=True)
    ap.add_argument('--scene',required=True);ap.add_argument('--out');x=ap.parse_args()
    r,root,text=receipt(x.label,x.scene,'Optimization');modes=sorted({m.group(1).strip() for m in re.finditer(r'^mode_check,\s*([^,]+),',text,re.M)})
    assert all(m.split('+')[0] in (CASE17,NATIVE) for m in modes),modes
    h={m:hashes(root,m) for m in modes}
    _,ref,_=receipt(x.reference,x.scene,'Preservation');record=json.loads(Path(x.record).read_text(encoding='utf-8'))['rgb_hashes']
    rows=[]
    for m in modes:
        base=CASE17 if m.startswith(CASE17) else NATIVE
        rows.append(dict(mode=m,frames=240,
            vs_case17_same_run=sum(a!=b for a,b in zip(h[m],h[CASE17])) if base==CASE17 else None,
            vs_reference_capture=sum(a!=b for a,b in zip(h[m],hashes(ref,base))),
            vs_original_record=sum(a!=b for a,b in zip(h[m],record[base]))))
    ok=all(v in (0,None) for row in rows for k,v in row.items() if k.startswith('vs_'))
    res=dict(scene=x.scene,label=x.label,executable_sha256=r['executable_sha256'],reference=x.reference,record=x.record,modes=rows,validation='PASS' if ok else 'MISMATCH')
    txt=json.dumps(res,indent=1);print(txt)
    if x.out:Path(x.out).parent.mkdir(parents=True,exist_ok=True);Path(x.out).write_text(txt+'\n',encoding='utf-8')
if __name__=='__main__':main()
