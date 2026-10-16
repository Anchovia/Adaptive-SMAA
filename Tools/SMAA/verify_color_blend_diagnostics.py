"""Check case-17 internal-state invariants and compare diagnostic captures byte-for-byte.

Per diagnostic frame of case 17 (coverage = stencil-selected resolve pixels):
  * selected weight is exactly float32(0.8), unselected weight stays 0
  * next-history alpha equals the current spatial alpha everywhere
  * next-history RGB and visible RGB equal the current spatial RGB where unselected
  * visible RGB equals next-history RGB where selected
  * every current raw edge pixel is selected (selection = current OR reprojected previous)
Native case 4 frames only record their next history/spatial/velocity.
Between two labels every saved file must match byte-for-byte.
"""
import argparse,os,hashlib,json,struct
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
# Receipts from this worktree plus any extra files listed in COLOR_BLEND_RUNS (os.pathsep separated).
RUNS=[ROOT/'tmp/color-blend-preservation-runs.json']+[Path(x) for x in os.environ.get('COLOR_BLEND_RUNS','').split(os.pathsep) if x]
CASE17='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend'
NATIVE='O-T2X-R'
FORMATS={27:(np.uint8,4),28:(np.uint8,4),29:(np.uint8,4),34:(np.float16,2),41:(np.float32,1),61:(np.uint8,1),35:(np.uint16,2)}

def capture_root(label,scene):
    seen={x['report']:x for p in RUNS if p.exists() for x in json.loads(p.read_text(encoding='utf-8-sig'))}
    r=[x for x in seen.values() if x['label']==label and x['scene']==scene and x['phase']=='Diagnostic']
    assert len(r)==1,(label,scene,len(r));r=r[0]
    report=Path(r['report']);assert hashlib.sha256(report.read_bytes()).hexdigest().upper()==r['report_sha256']
    text=report.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text
    return r,Path(r['capture_root']),text
def dds(p):
    b=Path(p).read_bytes();assert b[:4]==b'DDS ';h,w=struct.unpack_from('<2I',b,12)
    if b[84:88]==b'DX10':fmt=struct.unpack_from('<I',b,128)[0];typ,n=FORMATS[fmt];off=148
    else:
        # Legacy headers written for R8 (8-bit luminance), R16G16F (FourCC 112) and R32F (FourCC 114).
        fourcc,bits=struct.unpack_from('<2I',b,84);off=128
        fmt={112:34,114:41}.get(fourcc,61 if fourcc==0 and bits==8 else None);assert fmt,(p,fourcc,bits);typ,n=FORMATS[fmt]
    a=np.frombuffer(b[off:],typ).reshape(h,w,n);return a,fmt
def edges(p):
    b=Path(p).read_bytes();assert b[:4]==b'EDG1';w,h=struct.unpack_from('<2I',b,4)
    return np.frombuffer(b[12:],np.uint8).reshape(h,w,2)
def png(p):
    with Image.open(p) as im:assert im.mode=='RGB';return np.asarray(im).copy()
def frames(root,mode):return sorted(int(p.name[6:11]) for p in (root/mode).glob('frame_?????-next-history.dds'))
def invariants(root):
    out=[]
    for f in frames(root,CASE17):
        d=root/CASE17;pre=f'frame_{f:05d}'
        cov,_=dds(d/f'{pre}-coverage.dds');weight,_=dds(d/f'{pre}-weight.dds');nxt,fmt=dds(d/f'{pre}-next-history.dds')
        cur,_=dds(d/f'{pre}-current.dds');vis=png(d/f'{pre}.png');edge=edges(d/f'{pre}-edge.rg8')
        sel=cov[:,:,0]>0;w=weight[:,:,0]
        row=dict(frame=f,selected_pixels=int(sel.sum()),selected_percent=float(100*sel.mean()),next_history_format=fmt,
            selected_weight_exact=bool(np.all(w[sel]==np.float32(0.8))),unselected_weight_zero=bool(np.all(w[~sel]==0)),
            history_alpha_is_spatial_alpha=bool(np.array_equal(nxt[:,:,3],cur[:,:,3])),
            unselected_history_rgb_is_spatial=bool(np.array_equal(nxt[~sel][:,:3],cur[~sel][:,:3])),
            unselected_visible_rgb_is_spatial=bool(np.array_equal(vis[~sel],cur[~sel][:,:3])),
            selected_visible_rgb_is_history=bool(np.array_equal(vis[sel],nxt[sel][:,:3])),
            current_edges_selected=bool(np.all(sel[np.any(edge>0,axis=2)])),
            current_edge_pixels=int(np.any(edge>0,axis=2).sum()),
            selected_changed_vs_spatial=int(np.any(nxt[sel][:,:3]!=cur[sel][:,:3],axis=1).sum()))
        row['pass']=all(row[k] for k in ['selected_weight_exact','unselected_weight_zero','history_alpha_is_spatial_alpha','unselected_history_rgb_is_spatial',
            'unselected_visible_rgb_is_spatial','selected_visible_rgb_is_history','current_edges_selected'])
        out.append(row)
    return out
def byte_compare(root_a,root_b):
    out=[];total=0;bad=0
    for mode in [CASE17,NATIVE]:
        names=sorted(p.name for p in (root_a/mode).iterdir());names_b=sorted(p.name for p in (root_b/mode).iterdir())
        assert names==names_b,(mode,len(names),len(names_b))
        for n in names:
            total+=1
            if (root_a/mode/n).suffix=='.png':
                same=np.array_equal(png(root_a/mode/n),png(root_b/mode/n))
            else:
                same=(root_a/mode/n).read_bytes()==(root_b/mode/n).read_bytes()
            if not same:bad+=1;out.append(f'{mode}/{n}')
    return dict(files=total,mismatch_files=bad,mismatches=out[:50])
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('a');ap.add_argument('b',nargs='?');ap.add_argument('--scene',required=True);ap.add_argument('--out')
    x=ap.parse_args()
    ra,root_a,_=capture_root(x.a,x.scene);inv=invariants(root_a)
    res=dict(scene=x.scene,a=x.a,a_executable=ra['executable_sha256'],diagnostic_frames=[r['frame'] for r in inv],invariants=inv,
        invariants_pass=all(r['pass'] for r in inv))
    if x.b:
        rb,root_b,_=capture_root(x.b,x.scene);res.update(b=x.b,b_executable=rb['executable_sha256'],b_invariants_pass=all(r['pass'] for r in invariants(root_b)),
            byte_compare=byte_compare(root_a,root_b))
    res['validation']='PASS' if res['invariants_pass'] and res.get('b_invariants_pass',True) and res.get('byte_compare',{}).get('mismatch_files',0)==0 else 'FAIL'
    txt=json.dumps(res,indent=2);print(json.dumps({k:v for k,v in res.items() if k!='invariants'},indent=1)[:3000])
    if x.out:Path(x.out).parent.mkdir(parents=True,exist_ok=True);Path(x.out).write_text(txt+'\n',encoding='utf-8')
