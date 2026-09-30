"""Validate isolated coverage control inputs, native bridge and execution masks."""
import argparse,csv,hashlib,json,struct,subprocess
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Coverage-Pattern-Control'
BASE='304f7493c6a5e53fa3cfac5dfd084ce0e86ca459'
A='ABL-Spatial-FirstEdge-Stencil-PatternOff-R'
B='ABL-Spatial-FullScreen-PatternOff-R'
C='O-T2X-R';D='ABL-Native-FullScreen-PatternOff-R';E=B+'-Repeat'
MODES=[A,B,C,D,E];TOTAL=1920*1061

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def rgb(p):
    with Image.open(p) as im:
        assert im.size==(1920,1061) and im.mode=='RGB',(p,im.size,im.mode)
        return np.asarray(im).copy()
def rhash(a):return hashlib.sha256(a.tobytes()).hexdigest()
def dds_bytes(p):
    b=Path(p).read_bytes();assert b[:4]==b'DDS ' and struct.unpack_from('<2I',b,12)==(1061,1920)
    return b[148 if b[84:88]==b'DX10' else 128:]
def coverage(p):
    a=np.frombuffer(dds_bytes(p),np.uint8).reshape(1061,1920);assert np.isin(a,[0,255]).all();return a>0
def edge(p):
    b=Path(p).read_bytes();assert b[:4]==b'EDG1' and struct.unpack_from('<2I',b,4)==(1920,1061)
    a=np.frombuffer(b[12:],np.uint8).reshape(1061,1920,2);assert np.isin(a,[0,255]).all();return np.any(a>0,axis=2)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',required=True,choices=['bistro','minecraft']);p.add_argument('--phase',choices=['smoke','capture'],default='capture');args=p.parse_args()
    scene,phase=args.scene,args.phase;n=6 if phase=='smoke' else 240
    rec=json.loads((DOC/f'{scene}-{phase}-run.json').read_text(encoding='utf-8-sig'))
    assert sha(rec['report'])==rec['report_sha256'].lower()
    source=json.loads((DOC/'source-audit.json').read_text());assert source['executable_sha256']==rec['executable_sha256'].lower()==sha(ROOT/'Projects/CMAA2/CMAA2.exe')
    text=Path(rec['report']).read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[[x.strip() for x in row if x.strip()] for row in csv.reader(text.splitlines()) if row]
    root=Path(next(r[1] for r in rows if r[0]=='capture_root'))
    checks=[r for r in rows if r[0]=='mode_check'];assert len(checks)==len(MODES)*n
    ih={}
    for mode in MODES:
        rr=[r for r in checks if r[1]==mode];assert [int(r[2]) for r in rr]==list(range(n)) and all(r[-1]=='PASS' for r in rr)
        assert all(r[3]==('PatternOn' if mode==C else 'PatternOff') for r in rr)
        records=[r for r in rows if r[:2]==['input_hashes',mode]]
        assert [int(r[2]) for r in records]==list(range(1,n)) and all(r[-1]=='PASS' for r in records)
        ih[mode]={int(r[2]):r[3:6] for r in records}
        for f in range(2,n):assert ih[mode][f][1]==ih[mode][f-1][0],(mode,f,'history not previous spatial')
    for mode in (B,D,E):assert ih[mode]==ih[A],(mode,'current/previous/velocity mismatch')
    expected=json.loads(subprocess.check_output(['git','show',BASE+f':Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json'],cwd=ROOT))
    hashes={m:[] for m in MODES};frames=[];mask_frames=range(n) if phase=='smoke' else range(60,220)
    for f in range(n):
        ims={m:rgb(root/m/f'frame_{f:05d}.png') for m in MODES}
        for mode in MODES:hashes[mode].append(rhash(ims[mode]))
        for mode in (A,C):assert hashes[mode][-1]==expected[mode][f],(mode,f,'baseline RGB mismatch')
        for mode in (D,E):assert np.array_equal(ims[B],ims[mode]),(mode,f,'full native/repeat mismatch')
        if f in mask_frames:
            paths={m:root/m/f'frame_{f:05d}' for m in (A,B)}
            ma,mb=[coverage(str(paths[m])+'-coverage.dds') for m in (A,B)]
            ea,eb=[edge(str(paths[m])+'-edge.rg8') for m in (A,B)]
            assert np.array_equal(ma,ea) and np.array_equal(ea,eb) and mb.all()
            for mode,mask in [(A,ma),(B,mb)]:
                row=[r for r in rows if r[:3]==['execution',mode,str(f)]]
                assert len(row)==1 and row[0][-1]=='PASS'
                assert list(map(int,row[0][3:5]))==[int(mask.sum())]*2,(mode,f,'execution count')
            ca,cb=[rgb(str(paths[m])+'-current.png') for m in (A,B)]
            assert np.array_equal(ca,cb),(f,'current RGB mismatch')
            assert np.array_equal(ims[A][ma],ims[B][ma]),(f,'selected output mismatch')
            assert np.array_equal(ims[A][~ma],ca[~ma]),(f,'nonselected not current')
            diff=np.max(np.abs(ims[B].astype(np.int16)-ims[A].astype(np.int16)),axis=2)
            frames.append(dict(frame=f,selected=int(ma.sum()),coverage_percent=float(ma.mean()*100),
                outside_changed_pixels=int(np.count_nonzero(diff[~ma])),outside_changed_percent=float(np.mean(diff[~ma]>0)*100),
                outside_delta_mean_max_rgb=float(diff[~ma].mean()),outside_delta_max_rgb=int(diff[~ma].max()),
                inside_mismatch_pixels=0,nonselected_current_mismatch_pixels=0))
        if f%60==0:print(scene,phase,'validated frame',f,flush=True)
    probe_frames=[1] if phase=='smoke' else [100,179,180,190];probes=[]
    for f in probe_frames:
        for suffix in ('current','previous','velocity'):
            paths={m:root/m/f'frame_{f:05d}-{suffix}.dds' for m in (A,B,D,E)}
            data=dds_bytes(paths[A]);assert all(dds_bytes(p)==data for p in paths.values()),(f,suffix,'probe mismatch')
            probes.append(dict(frame=f,texture=suffix,payload_sha256=hashlib.sha256(data).hexdigest(),matching_modes=[A,B,D,E]))
    static={m:len(set(hashes[m][200:240])) for m in MODES} if phase=='capture' else {}
    if static:assert all(v==1 for v in static.values())
    result=dict(validation='PASS',scene=scene,phase=phase,base=BASE,receipt=rec,capture=str(root),frames_per_mode=n,
        baseline_rgb_frames=2*n,native_full_off_bridge_frames=n,diagnostic_off_repeat_frames=n,
        input_hash_algorithm='XXH64 seed0, raw row texels excluding row padding; frame0 seed excluded',
        input_hashes=ih,input_equality_frames=n-1,history_previous_spatial_link_frames=n-2,
        probe_byte_equality=probes,mask_frames=len(frames),frames=frames,late_still_unique_rgb=static,
        rgb_hashes=hashes,scope='Coverage-only validation and pattern controls. No timing or automatic quality interpretation.')
    dump(DOC/f'{scene}-{phase}-validation.json',result)
    print('PASS',scene,phase,'baseline, inputs, same-edge output, full native bridge, coverage and repeat',flush=True)

if __name__=='__main__':main()
