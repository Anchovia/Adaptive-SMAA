import numpy as np,struct
H=1061
d=np.fromfile('rows.bin',dtype=np.float32);vf,vs=d[:H],d[H:]
y=np.arange(H,dtype=np.float32)+0.5
print('vf[:4]',[float(x) for x in vf[:4]],'vs[:4]',[float(x) for x in vs[:4]])
base=np.float32(1.0/H)
best=[]
for k in range(-64,65):
    c=np.frombuffer(struct.pack('<i',struct.unpack('<i',struct.pack('<f',base))[0]+k),dtype=np.float32)[0]
    best.append((int((y*c!=vf).sum()),int((y*c!=vs).sum()),k,float(c)))
print('min mismatch F',min(best)[:3], 'min mismatch S',min(best,key=lambda t:t[1])[:3])
# Hardware-style: barycentric in limited precision? differences vs exact in units of ulp
ex=(np.arange(H)+.5)/H
ulp=np.spacing(vf)
r=(vf-ex)/ulp
print('F error in ulp: mean',r.mean(),'min',r.min(),'max',r.max())
r2=(vs-ex)/np.spacing(vs);print('S error in ulp: mean',r2.mean(),'min',r2.min(),'max',r2.max())
# F = 2*j, S = 1-2*i ; test expressions from the other triangle
one=np.float32(1)
print('vf==1-(1-vs)',int((one-(one-vs)!=vf).sum()))
for name,e in [('2*(vs/2)',2*(vs/2)),('vs',vs)]:print(name,int((e!=vf).sum()))
# step analysis
dv=np.diff(vf.astype(np.float64));print('F step range',dv.min(),dv.max(),'1/H',1/H)
# fixed-point guess: j quantised to 2^-n of something
for n in range(16,34):
    q=np.round(ex*2**n)/2**n
    t=np.float32(q);m=int((t!=vf).sum());
    if m<H: print('round quant',n,m)
    q=np.floor(ex*2**n)/2**n;t=np.float32(q);m=int((t!=vf).sum())
    if m<H: print('floor quant',n,m)
