"""Validate unchanged output and trace native resolve from exact input readbacks."""
import argparse,csv,hashlib,json,struct
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Thin-Line-Trace'
OUT=ROOT/'Projects/CMAA2/Captures/thin-line-trace-20261001'
A='ABL-Spatial-FirstEdge-Stencil-PatternOff-R';C='O-T2X-R'
ROIS={'bistro':{'chairs':(1190,530,1478,722),'window':(880,430,1168,622)},
      'minecraft':{'thin_edges':(780,460,1068,652)}}
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ph(a):return hashlib.sha256(a.tobytes()).hexdigest()
def rgb(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061)
        return np.asarray(im).copy()
def dds(p):
    b=Path(p).read_bytes();assert b[:4]==b'DDS ';h,w=struct.unpack_from('<2I',b,12);assert (w,h)==(1920,1061)
    if b[84:88]==b'DX10':
        fmt=struct.unpack_from('<I',b,128)[0];off=148
        typ,n={27:(np.uint8,4),28:(np.uint8,4),29:(np.uint8,4),34:(np.float16,2),61:(np.uint8,1)}[fmt]
    else:
        off=128;fourcc=struct.unpack_from('<I',b,84)[0];bits=struct.unpack_from('<I',b,88)[0]
        if fourcc==112:typ,n=np.float16,2
        elif bits==8:typ,n=np.uint8,1
        else:raise AssertionError(('unsupported DDS',p,fourcc,bits))
    a=np.frombuffer(b[off:],typ).reshape(h,w,n)
    return a[:,:,0] if n==1 else a
def edges(p):
    b=Path(p).read_bytes();assert b[:4]==b'EDG1' and struct.unpack_from('<2I',b,4)==(1920,1061)
    a=np.frombuffer(b[12:],np.uint8).reshape(1061,1920,2);assert np.isin(a,[0,255]).all()
    return a
def linear(a):
    c=a.astype(np.float32)/np.float32(255)
    return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
def encoded(a):
    c=np.clip(a,0,1);return np.rint(255*np.where(c<=.0031308,c*12.92,1.055*c**(1/2.4)-.055)).clip(0,255).astype(np.uint8)
def reconstruct(current,previous,v):
    h,w=v.shape[:2];y,x=np.mgrid[:h,:w]
    uv=np.stack(((x.astype(np.float32)+.5)/np.float32(w),(y.astype(np.float32)+.5)/np.float32(h)),axis=-1)
    coords=(uv-v.astype(np.float32))*np.array([w,h],np.float32)
    ix=np.floor(coords[:,:,0]).astype(np.int32).clip(0,w-1);iy=np.floor(coords[:,:,1]).astype(np.int32).clip(0,h-1)
    prev=previous[iy,ix];ca=current[:,:,3].astype(np.float32)/255;pa=prev[:,:,3].astype(np.float32)/255
    # Confirmed native DXBC mul(previous alpha squared) + fused mad.
    delta=(ca.astype(np.float64)**2-(pa*pa).astype(np.float64)).astype(np.float32)
    weight=np.float32(.5)*np.clip(1-np.sqrt(np.abs(delta)/np.float32(5))*np.float32(30),0,1)
    lc=linear(current[:,:,:3]);lp=linear(prev[:,:,:3]);mix=encoded(lc+(lp-lc)*weight[:,:,None])
    frac=coords-np.floor(coords);safe=np.all((frac>.01)&(frac<.99),axis=2)
    return dict(history=prev,weight=weight,coords=coords,safe=safe,full_resolve=mix)

# Input decoding/reconstruction only, reused from 756ff54. No renderer imported.
