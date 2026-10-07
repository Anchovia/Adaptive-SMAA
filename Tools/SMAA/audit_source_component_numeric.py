"""Hardware fixtures for the real component helper, checked against independent CPU equations."""
from pathlib import Path
import json,subprocess,struct,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DOC=next(p for p in (ROOT/'Docs').glob('Edge-History-Source-*') if (p/'case.json').exists())
case=json.loads((DOC/'case.json').read_text())['case']
OUT=ROOT/f'tmp/case{case}-numeric';OUT.mkdir(parents=True,exist_ok=True)
probe=ROOT/'tmp/case13-filter-probe/case13_filter_probe.exe'
assert probe.exists()
uv=np.array([(x,y) for y in [-.1,0,.0625,.3,.5,.9,1,1.1] for x in np.linspace(-.1,1.1,33)],np.float32)
helper=(ROOT/'Projects/CMAA2/SMAA/SourceTemporalMath.hlsli').as_posix()
expr={15:'SourceClipHistory(tex,ss,p,float2(w,h),c,history)',16:'SourceSampleHistory(tex,ss,p,float2(w,h))',17:'SourceBlend(c,history,.8)'}[case]
shader=OUT/'probe.hlsl'
shader.write_text(f'#include "{helper}"\nTexture2D<float4> tex:register(t0);StructuredBuffer<float2> uv:register(t1);RWStructuredBuffer<float4> output:register(u0);SamplerState ss:register(s0);\n[numthreads(64,1,1)]void main(uint3 id:SV_DispatchThreadID){{uint n,stride;uv.GetDimensions(n,stride);if(id.x>=n)return;uint w,h;tex.GetDimensions(w,h);float2 p=uv[id.x];float3 c=tex.SampleLevel(ss,p,0).rgb;float3 history=float3(saturate(p.x),saturate(p.y),.8);output[2*id.x]=float4({expr},1);output[2*id.x+1]=float4(c,1);}}',encoding='utf-8')
def decode(v):v=np.asarray(v,np.float64)/255;return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
def bilinear(a,p):
 h,w=a.shape[:2];q=np.asarray(p)*[w,h]-.5;b=np.floor(q).astype(int);f=q-b
 x0=b[:,0].clip(0,w-1);x1=(b[:,0]+1).clip(0,w-1);y0=b[:,1].clip(0,h-1);y1=(b[:,1]+1).clip(0,h-1)
 return (a[y0,x0]*(1-f[:,0,None])+a[y0,x1]*f[:,0,None])*(1-f[:,1,None])+(a[y1,x0]*(1-f[:,0,None])+a[y1,x1]*f[:,0,None])*f[:,1,None]
def yc(c):return np.stack(((c[:,0]+2*c[:,1]+c[:,2])/4,(c[:,0]-c[:,2])/2,(-c[:,0]+2*c[:,1]-c[:,2])/4),axis=1)
def rgb(c):return np.stack((c[:,0]+c[:,1]-c[:,2],c[:,0]+c[:,2],c[:,0]-c[:,1]-c[:,2]),axis=1)
def expected(a,p):
 c=bilinear(a,p);hist=np.column_stack((p.clip(0,1),np.full(len(p),.8)))
 if case==15:
  n=np.stack([yc(bilinear(a,p+np.array([x,y])/8)) for y in [-1,0,1] for x in [-1,0,1]])
  mu=n.mean(0);sigma=n.std(0);return np.maximum(rgb(np.clip(yc(hist),mu-sigma,mu+sigma)),0)
 if case==16:
  pixel=p*8+.5;t=pixel-np.floor(pixel);P=(np.floor(pixel)-.5)/8
  w0=-.5*t**3+t**2-.5*t;w1=1.5*t**3-2.5*t**2+1;w2=-1.5*t**3+2*t**2+.5*t;w3=.5*t**3-.5*t**2
  s=w1+w2;m=P+w2/s/8;lo=P-.125;hi=P+.25
  A=bilinear(a,np.column_stack((m[:,0],lo[:,1])));B=bilinear(a,np.column_stack((lo[:,0],m[:,1])));C=bilinear(a,m);D=bilinear(a,np.column_stack((hi[:,0],m[:,1])));E=bilinear(a,np.column_stack((m[:,0],hi[:,1])))
  a0=((.5*w0[:,0]+s[:,0]+.5*w3[:,0])*w0[:,1])[:,None]
  b0=(.5*(w0[:,0]+w3[:,0])*w0[:,1]+w0[:,0]*s[:,1]+.5*w0[:,0]*w3[:,1])[:,None]
  return A*a0+B*b0+C*(s[:,0]*s[:,1])[:,None]+D*(w3[:,0]*s[:,1]+.5*w3[:,0]*w3[:,1])[:,None]+E*((.5*w0[:,0]+s[:,0]+.5*w3[:,0])*w3[:,1])[:,None]
 def encode(v):v=np.clip(v,0,1);return np.where(v<=.0031308,v*12.92,1.055*v**(1/2.4)-.055)
 out=np.sqrt(.2*encode(c)**2+.8*encode(hist)**2)
 return np.where(out<=.04045,out/12.92,((out+.055)/1.055)**2.4)
rows=[]
rng=np.random.default_rng(20261007)
textures={name:np.full((8,8,3),color,np.uint8) for name,color in [('red',[255,0,0]),('green',[0,255,0]),('blue',[0,0,255]),('gray',[128,128,128]),('black',[0,0,0]),('white',[255,255,255])]}
textures['random']=rng.integers(0,256,(8,8,3),np.uint8)
textures['thin-line']=np.zeros((8,8,3),np.uint8);textures['thin-line'][:,3]=255
for name,a in textures.items():
 inp=OUT/f'{name}.bin';out=OUT/f'{name}-gpu.bin';rgba=np.dstack((a,np.full((8,8),255,np.uint8)))
 inp.write_bytes(struct.pack('<3I',8,8,len(uv))+rgba.tobytes()+uv.tobytes())
 run=subprocess.run([str(probe),str(inp),str(out),str(shader)],capture_output=True,timeout=30)
 assert run.returncode==0,(name,run.stdout,run.stderr)
 got=np.frombuffer(out.read_bytes(),np.float32).reshape(-1,2,4)[:,0,:3]
 ideal=expected(decode(a),uv.astype(np.float64));err=np.abs(got-ideal)
 assert np.isfinite(got).all() and err.max()<.006,(name,float(err.max()))
 if case in [15,16] and name not in ['random','thin-line']:
  assert np.abs(got-decode(a)[0,0]).max()<.001,(name,'constant color not preserved')
 rows.append(dict(fixture=name,positions=len(uv),max_abs_linear_error=float(err.max()),mean_abs_linear_error=float(err.mean()),finite=True))
result=dict(validation='PASS',case=case,classification='hardware D3D11 helper fixtures; CPU ideal float sampling, hardware interpolation precision bounded',tested_positions=sum(r['positions'] for r in rows),max_abs_error=max(r['max_abs_linear_error'] for r in rows),tolerance=.006,fixtures=rows,production_helper_sha256=hashlib.sha256((ROOT/'Projects/CMAA2/SMAA/SourceTemporalMath.hlsli').read_bytes()).hexdigest())
(DOC/'numeric-gpu-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['validation','case','tested_positions','max_abs_error']}))
