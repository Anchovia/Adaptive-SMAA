"""Independent float64 image reference for production recovered-source functions.

This is a numerical gate, not a rendered quality comparison or bit-exact source claim.
Run the hardware probe twice; both binaries must match before accepting results.
"""
import argparse, json
from pathlib import Path
import numpy as np

W,H=35,29
Y,X=np.mgrid[:H,:W]
def fixture(i):
    a=np.zeros((H,W,3),dtype=np.float64)
    if i==1:a[:]=.5
    if i==2:a[:,:,0]=1
    if i==3:a[:,:,2]=1
    if i==4:a=np.stack(((X*7+Y*3)%17,(X*5+Y*11)%17,(X*13+Y)%17),axis=-1)/16
    if i==5:a=np.stack(((X+Y)%2,X%2,Y%2),axis=-1).astype(float)
    if i==6:a=np.stack(((X*17+Y*11)%256,(X*43+Y*19)%256,(X*31+Y*53)%256),axis=-1)/255
    if i==7:a=np.stack(((X%7)*.01,(Y%5)*.03,(X%5)*.01),axis=-1)
    return a.astype(np.float32).astype(float)

def load(a,x,y):
    valid=(x>=0)&(x<W)&(y>=0)&(y<H)
    return a[np.clip(y,0,H-1),np.clip(x,0,W-1)]*valid[...,None]

def residual(a):
    def edge(x,y):
        c=load(a,x,y)*[.299,.587,.114]
        return np.maximum(np.stack((np.max(np.abs(c-load(a,x+1,y)*[.299,.587,.114]),axis=-1),
            np.max(np.abs(c-load(a,x,y+1)*[.299,.587,.114]),axis=-1)),axis=-1)-1/22,0)
    def lca(x,y):
        e=edge(x,y)
        u=(edge(x,y-1)[...,1]+e[...,1]+edge(x+1,y-1)[...,1]+edge(x+1,y)[...,1])/4
        v=(edge(x-1,y)[...,0]+e[...,0]+edge(x-1,y+1)[...,0]+edge(x,y+1)[...,0])/4
        return np.maximum(e-.5*np.stack((u,v),axis=-1),0)
    return np.concatenate((lca(X,Y),lca(X-1,Y)[...,:1],lca(X,Y-1)[...,1:]),axis=-1)

def bilinear(a,x,y):
    ix=np.floor(x).astype(int);iy=np.floor(y).astype(int)
    fx=(x-ix)[...,None];fy=(y-iy)[...,None]
    return (load(a,ix,iy)*(1-fx)+load(a,ix+1,iy)*fx)*(1-fy)+(load(a,ix,iy+1)*(1-fx)+load(a,ix+1,iy+1)*fx)*fy

def bicubic(a,x,y):
    # x/y are UV*size; source internally adds .5 before splitting pixel/fraction.
    tx=x+.5-np.floor(x+.5);ty=y+.5-np.floor(y+.5)
    px=np.floor(x+.5)-1;py=np.floor(y+.5)-1
    def weights(t):return (-.5*t**3+t*t-.5*t,1.5*t**3-2.5*t*t+1,-1.5*t**3+2*t*t+.5*t,.5*t**3-.5*t*t)
    wx=weights(tx);wy=weights(ty);sx=wx[1]+wx[2];sy=wy[1]+wy[2]
    mx=px+wx[2]/sx;my=py+wy[2]/sy
    A=bilinear(a,mx,py-1);B=bilinear(a,px-1,my);C=bilinear(a,mx,my);D=bilinear(a,px+2,my);E=bilinear(a,mx,py+2)
    w0,w1,w2,w3=[v[...,None] for v in wx];v0,v1,v2,v3=[v[...,None] for v in wy]
    return (.5*(A+B)*w0+A*(w1+w2)+.5*(A+B)*w3)*v0+(B*w0+C*(w1+w2)+D*w3)*(v1+v2)+(.5*(B+E)*w0+E*(w1+w2)+.5*(D+E)*w3)*v3

TO=np.array([[.25,.5,.25],[.5,0,-.5],[-.25,.5,-.25]])
FROM=np.array([[1,1,-1],[1,0,1],[1,-1,-1]])
def clip(a,history):
    neighbours=[load(a,X+x,Y+y)@TO.T for y in [-1,0,1] for x in [-1,0,1] if x or y]
    corners=(neighbours[0]+neighbours[2]+neighbours[5]+neighbours[7])/4
    c=a@TO.T;c=np.maximum(c+(c-corners)*.263157904,0)
    n=np.stack(neighbours+[c]);mu=n.mean(axis=0);sigma=np.sqrt(np.maximum((n*n).mean(axis=0)-mu*mu,0))
    low=(mu-sigma)@FROM.T;high=(mu+sigma)@FROM.T
    return np.minimum(np.maximum(history,low),high)

def main():
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('repeat');p.add_argument('output');a=p.parse_args()
    assert Path(a.input).read_bytes()==Path(a.repeat).read_bytes(),'GPU repeats differ'
    v=np.fromfile(a.input,dtype=np.float32).reshape(8,H,W,4,4)
    assert np.isfinite(v).all(),'nonfinite GPU value'
    rows=[]
    for i in range(8):
        c=fixture(i);h=c[:,::-1];edges=residual(c);filtered=bicubic(h,X+.87,Y+1.11)
        clipped=clip(c,filtered);hist0=clip(c,bicubic(h,X+.5,Y+.5))
        final=np.floor(np.clip(np.sqrt(.789473712*hist0**2+(1-.789473712)*c**2),0,1)*255+.5)/255
        maxe=np.max(edges,axis=-1);actual=np.max(v[i,:,:,0],axis=-1)
        # min16float implementation is allowed to evaluate at higher precision. Record all
        # predicate differences; only those farther than 0.001 from threshold are failures.
        mismatch=(actual>1/44)!=(maxe>1/44)
        row=dict(fixture=i,pixels=W*H,residual_max_error=float(np.max(abs(v[i,:,:,0]-edges))),
            candidate_mismatch=int(mismatch.sum()),candidate_mismatch_away_from_boundary=int((mismatch&(abs(maxe-1/44)>.001)).sum()),
            filter_max_error=float(np.max(abs(v[i,:,:,1,:3]-filtered))),
            clip_max_error=float(np.max(abs(v[i,:,:,2,:3]-clipped))),
            final_max_byte_error=float(np.max(abs(v[i,:,:,3,:3]-final)))*255)
        rows.append(row)
    passed=all(q['residual_max_error']<.001 and q['candidate_mismatch_away_from_boundary']==0 and q['filter_max_error']<.005 and q['clip_max_error']<.005 and q['final_max_byte_error']<=2.001 for q in rows)
    examples={name:{'filtered':v[i,14,17,1,:3].tolist(),
        'clipped':v[i,14,17,2,:3].tolist(),
        'final_rgb_bytes':np.rint(v[i,14,17,3,:3]*255).astype(int).tolist()}
        for i,name in [(1,'gray'),(2,'red'),(3,'blue')]}
    out=dict(passed=passed,finite=True,repeat_exact=True,classification='production-function GPU vs independent float64 image reference; minprecision/filter interpolation tolerances; not original full renderer exactness',rows=rows,
        flat_color_examples=examples,
        flat_color_scope='Function-only center pixel; uniform image interiors are normally noncandidates in the renderer')
    Path(a.output).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));assert passed
if __name__=='__main__':main()
