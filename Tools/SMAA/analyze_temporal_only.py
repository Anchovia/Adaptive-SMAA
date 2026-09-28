"""Verify temporal-only against native no-blend shader and frozen baseline captures."""
import argparse,csv,hashlib,json,statistics,struct
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]; DOC=ROOT/'Docs/Temporal-Only-Control'
MODES=['AA-Off','O-1X','O-T2X-R','ABL-TemporalOnly-R','ABL-TemporalOnly-R-Repeat','REF-Native-ZeroWeights-R']
PROBES=[0,1,59,60,61,100,179,180,181,239]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def image(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(p,im.mode,im.size)
        return np.asarray(im).copy()
def dds(p):
    b=p.read_bytes();assert b[:4]==b'DDS ' and struct.unpack_from('<I',b,4)[0]==124
    h,w,pitch=struct.unpack_from('<3I',b,12);assert (w,h)==(1920,1061)
    fourcc=b[84:88];fmt=struct.unpack_from('<I',b,128)[0] if fourcc==b'DX10' else None
    offset=148 if fmt is not None else 128
    if fmt==34 or fourcc==struct.pack('<I',112): # DXGI R16G16_FLOAT / legacy D3DFMT_G16R16F
        a=np.frombuffer(b[offset:],dtype='<f2').reshape(h,w,2).astype(np.float32)
    elif fmt in (27,28,29,87,90,91) or (fmt is None and fourcc==b'\x00'*4):
        assert len(b)-offset==w*h*4
        a=np.frombuffer(b[offset:],dtype=np.uint8).reshape(h,w,4)
        if fmt in (87,90,91) or (fmt is None and struct.unpack_from('<I',b,92)[0]==0x00ff0000):a=a[:,:,[2,1,0,3]]
    else:raise AssertionError((str(p),fourcc,fmt,len(b)))
    return a,dict(format=fmt,fourcc=fourcc.decode('ascii',errors='replace'),width=w,height=h,pitch=pitch,sha256=sha(p))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scene',required=True,choices=['bistro','minecraft']);a=ap.parse_args()
    receipts=json.loads((ROOT/'tmp/temporal-only-runs.json').read_text(encoding='utf-8-sig'))
    receipt=[r for r in receipts if r['scene']==a.scene and r['phase']=='Capture'];assert len(receipt)==1;receipt=receipt[0]
    report=Path(receipt['report']);assert sha(report)==receipt['report_sha256'].lower()
    text=report.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    checks=[[x.strip() for x in r] for r in csv.reader(text.splitlines()) if r and r[0].strip()=='mode_check']
    assert len(checks)==1440
    for m in MODES:
        rows=[r for r in checks if r[1]==m];assert [int(r[2]) for r in rows]==list(range(240))
        temporal=m not in MODES[:2];assert all(r[3:6]==['TemporalOn' if temporal else 'TemporalOff','CameraR' if temporal else 'NoR','PASS'] for r in rows)
    capture=report.parent
    baseline=json.loads((ROOT/f'Docs/Baseline-Restart/{a.scene}-capture.json').read_text(encoding='utf-8'));basecap=Path(baseline['capture'])
    names=[f'frame_{i:05d}.png' for i in range(240)]
    for m in MODES:assert [p.name for p in sorted((capture/m).glob('*.png'))]==names
    hashes={m:[] for m in MODES[:4]};prev={};rows=[];mismatch={m:0 for m in MODES[:3]};repeat=reference=0
    for i,name in enumerate(names):
        ims={m:image(capture/m/name) for m in MODES[:4]}
        for m in MODES[:3]:mismatch[m]+=int(not np.array_equal(ims[m],image(basecap/m/name)))
        repeat+=int(not np.array_equal(ims[MODES[3]],image(capture/MODES[4]/name)))
        reference+=int(not np.array_equal(ims[MODES[3]],image(capture/MODES[5]/name)))
        for m,im in ims.items():
            hashes[m].append(hashlib.sha256(im.tobytes()).hexdigest())
            rows.append(dict(frame=i,mode=m,rgb_step=float(np.abs(im.astype(np.int16)-prev[m]).mean()) if m in prev else None,
                versus_spatial_t2xr_mae=float(np.abs(im.astype(np.int16)-ims['O-T2X-R'].astype(np.int16)).mean()) if m==MODES[3] else None))
            prev[m]=im.astype(np.int16)
        if i%60==59:print(f'{a.scene}: {i+1}/240 PNG verified',flush=True)
    assert sum(mismatch.values())==repeat==reference==0,(mismatch,repeat,reference)
    probes=[]
    for i in PROBES:
        prefix=f'frame_{i:05d}';data={};meta={}
        for m in MODES[3:]:
            data[m]={};meta[m]={}
            for kind in ['input','prepared','velocity']:
                data[m][kind],meta[m][kind]=dds(capture/m/f'{prefix}-{kind}.dds')
        raw=data[MODES[3]];prepared=raw['prepared'];vel=raw['velocity']
        assert np.isfinite(vel).all()
        rgb_bad=int(np.any(raw['input'][:,:,:3]!=prepared[:,:,:3],axis=2).sum())
        rgba_ref_bad=int(np.any(prepared!=data[MODES[5]]['prepared'],axis=2).sum())
        rgba_repeat_bad=int(np.any(prepared!=data[MODES[4]]['prepared'],axis=2).sum())
        # CPU point-centre diagnostic. Native-reference RGBA equality is authoritative
        # because shader uses bilinear level-zero and floating texture coordinates.
        alpha=np.clip(np.sqrt(5*np.linalg.norm(vel,axis=2)),0,1)*255
        alpha_error=np.abs(prepared[:,:,3].astype(np.float32)-np.rint(alpha))
        assert rgb_bad==rgba_ref_bad==rgba_repeat_bad==0,(i,rgb_bad,rgba_ref_bad,rgba_repeat_bad)
        assert float(alpha_error.max())<=1.0,(i,float(alpha_error.max()))
        for kind in ['input','velocity']:assert np.array_equal(raw[kind],data[MODES[5]][kind]) and np.array_equal(raw[kind],data[MODES[4]][kind])
        if i==0:assert np.array_equal(prepared[:,:,:3],image(capture/MODES[3]/f'{prefix}.png')),'First-frame seed differs'
        probes.append(dict(frame=i,rgb_input_mismatch_pixels=rgb_bad,rgba_native_reference_mismatch_pixels=rgba_ref_bad,
            rgba_repeat_mismatch_pixels=rgba_repeat_bad,velocity_alpha_cpu_max_lsb=float(alpha_error.max()),alpha_max=int(prepared[:,:,3].max()),files=meta))
    static={}
    for name,start,end in [('initial_still',20,60),('late_still',200,240)]:
        static[name]={m:dict(unique_rgb_frames=len(set(hashes[m][start:end])),mean_rgb_step=statistics.mean(r['rgb_step'] for r in rows if r['mode']==m and start<=r['frame']<end)) for m in MODES[:4]}
        for m in MODES[:4]:assert static[name][m]['unique_rgb_frames']==1,(name,m,static[name][m])
    result=dict(validation='PASS',scene=a.scene,receipt=receipt,capture=str(capture),baseline_capture=str(basecap),baseline_mismatches=mismatch,
        repeat_mismatches=repeat,native_zero_weight_reference_mismatches=reference,frames_per_comparison=240,static=static,probes=probes,
        note='Source/CPU state and image/DDS validation; not a GPU debugger draw capture. Temporal-only is not SMAA 1X or a quality improvement claim.')
    DOC.mkdir(exist_ok=True,parents=True);(DOC/f'{a.scene}-capture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (DOC/f'{a.scene}-frames.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(dict(scene=a.scene,baseline_mismatches=mismatch,repeat=repeat,reference=reference,static=static)),flush=True)
if __name__=='__main__':main()
