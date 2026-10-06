"""Exercise the actual shared GPU filter against an independent 16-point spline."""
import hashlib,json,os,struct,subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-History-Catmull-Rom-Reconstruction'
OUT=ROOT/'tmp/case13-filter-probe';OUT.mkdir(parents=True,exist_ok=True)
env={k.upper():v for k,v in os.environ.items()}
build=subprocess.run([r'C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe',str(ROOT/'Tools/SMAA/case13_filter_probe.vcxproj'),'/p:Configuration=Release','/p:Platform=x64','/v:minimal','/nologo'],env=env,capture_output=True,timeout=180)
(OUT/'build.log').write_bytes(build.stdout+build.stderr)
assert build.returncode==0,(build.stdout+build.stderr).decode(errors='replace')

def linear(a):
    c=a.astype(np.float64)/255
    return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)

def kernel(d):
    d=np.abs(d)
    return np.where(d<1,1+1.5*d**3-2.5*d**2,np.where(d<2,2-4*d+2.5*d**2-.5*d**3,0))

def reference(image,uv):
    h,w=image.shape[:2];pos=uv.astype(np.float64)*[w,h]-.5;base=np.floor(pos).astype(int)
    filtered=np.zeros((len(uv),3));full=np.zeros_like(filtered);total=np.zeros(len(uv));pixels=linear(image[:,:,:3])
    for y in range(-1,3):
        for x in range(-1,3):
            ix=base[:,0]+x;iy=base[:,1]+y
            weight=kernel(pos[:,0]-ix)*kernel(pos[:,1]-iy)
            color=pixels[iy.clip(0,h-1),ix.clip(0,w-1)]
            full+=weight[:,None]*color
            if abs(x-0.5)==1.5 and abs(y-0.5)==1.5:continue
            filtered+=weight[:,None]*color;total+=weight
    return filtered/total[:,None],full,total

W,H=17,13;y,x=np.mgrid[:H,:W];rng=np.random.default_rng(1306)
centers=np.stack(((x+.5)/W,(y+.5)/H),axis=-1).reshape(-1,2)
grid=np.array([((8.5+fx)/W,(6.5+fy)/H) for fy in np.linspace(0,1,33) for fx in np.linspace(0,1,33)])
edges=np.array([(u,v) for u in [-.1,0,.5/W,1-.5/W,1,1.1] for v in [-.1,0,.5/H,1-.5/H,1,1.1]])
uv=np.concatenate([centers,grid,edges,rng.uniform(-.1,1.1,(1024,2))]).astype('<f4')
images={}
constant=np.zeros((H,W,4),np.uint8);constant[:]=[64,128,200,255];images['constant']=constant
gradient=np.zeros_like(constant);gradient[:,:,0]=np.rint(x*255/(W-1));gradient[:,:,1]=np.rint(y*255/(H-1));gradient[:,:,2]=np.rint((x+y)*255/(W+H-2));gradient[:,:,3]=255;images['gradient']=gradient
line=np.full_like(constant,220);line[:,8,:3]=25;line[:,:,3]=255;images['vertical-line']=line
checker=np.full_like(constant,255);checker[:,:,:3]=np.where(((x+y)%2)[:,:,None],32,224);images['checker']=checker
random=rng.integers(0,256,(H,W,4),dtype=np.uint8);random[:,:,3]=255;images['random']=random
records=[];outputs={}
for name,image in images.items():
    src=OUT/(name+'.bin');dst=OUT/(name+'-result.bin')
    src.write_bytes(struct.pack('<3I',W,H,len(uv))+image.tobytes()+uv.tobytes())
    p=subprocess.run([str(OUT/'case13_filter_probe.exe'),str(src),str(dst),str(ROOT/'Tools/SMAA/case13_filter_probe.hlsl')],capture_output=True,timeout=30)
    assert p.returncode==0,p.stdout+p.stderr
    pair=np.frombuffer(dst.read_bytes(),'<f4').reshape(-1,2,4)
    result=pair[:,0,:3].copy();baseline=pair[:,1,:3].copy();outputs[name]=result
    ideal,full,total=reference(image,uv)
    assert np.isfinite(result).all() and np.min(total)>.98
    error=np.abs(result-ideal);center=np.abs(result[:len(centers)]-baseline[:len(centers)])
    center_decode=np.abs(baseline[:len(centers)]-linear(image[:,:,:3]).reshape(-1,3))
    assert center.max()<2e-5,(name,'texel center vs GPU baseline',center.max())
    # Conservative bound for normalized signed taps and minimum 8-bit filtering
    # fractions: 2/256 * (sum(abs(weights))/sum(weights)) < 0.013.
    # This finite-precision witness is not byte-exact CPU/GPU filtering.
    assert error.max()<1/64,(name,'GPU/ideal filter bound',error.max())
    if name=='constant':assert np.abs(result-baseline).max()<2e-6
    records.append(dict(fixture=name,samples=len(uv),gpu_vs_ideal_max_linear_error=float(error.max()),gpu_vs_ideal_mean_linear_error=float(error.mean()),texel_center_vs_gpu_baseline_max_linear_error=float(center.max()),gpu_srgb_decode_vs_ideal_max_linear_error=float(center_decode.max()),constant_vs_gpu_baseline_max_error=float(np.abs(result-baseline).max()) if name=='constant' else None,five_vs_exact16_max_linear_error=float(np.abs(ideal-full).max()),five_vs_exact16_mean_linear_error=float(np.abs(ideal-full).mean()),normalization_min=float(total.min()),input_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),output_sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))

# Independent spline symmetry check over reflected UV/image, including clamps.
sym=[]
for axis in [0,1]:
    reflected=uv.copy();reflected[:,axis]=1-reflected[:,axis]
    flipped=np.flip(random,axis=1-axis)
    a,_,_=reference(random,uv);b,_,_=reference(flipped,reflected)
    # UV arrays are float32; reflection rounds independently.
    err=float(np.abs(a-b).max());assert err<2e-5
    sym.append(dict(axis='x' if axis==0 else 'y',cpu_max_linear_error=err))
result=dict(validation='PASS',implementation='Actual shared production helper compiled into hardware DX11 CS; UNORM-sRGB input and linear-clamp sampler',fixtures=records,symmetry=sym,gpu_ideal_error_bound=1/64,limits=['Five taps approximate exact16; differences recorded','Hardware filtering vs ideal spline is bounded, not byte-exact','Negative lobes can overshoot; no neighborhood clamp introduced','Not a full renderer quality or speed test'])
(DOC/'filter-reference.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(validation='PASS',fixtures=len(records),samples_per_fixture=len(uv),max_gpu_ideal_error=max(r['gpu_vs_ideal_max_linear_error'] for r in records),max_16tap_approximation_error=max(r['five_vs_exact16_max_linear_error'] for r in records))))
