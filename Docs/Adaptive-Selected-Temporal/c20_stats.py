import numpy as np,os,json,sys
from PIL import Image
root='D:/SMAAResearchCaptures/c20-adaptive-20261107/c20-a/capture'
B='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory'
S=B+'+NoVelocityAlpha';V=S+'+VelocityInEdge'
pairs=[('O-T2X-R','A-T2X-R','4'),(S,'A-'+S,'sel'),(V,'A-'+V,'19')]
out={}
for scene in ('bistro','minecraft'):
    base=f'{root}/{scene}';d=os.path.join(base,sorted(os.listdir(base))[-1])
    print(scene,sorted(os.listdir(d))[:1],len(os.listdir(d)))
    out[scene]={'dir':d}
    for o,a,lab in pairs:
        rows=[];worst=[]
        for f in range(240):
            x=np.array(Image.open(f'{d}/{o}/frame_{f:05d}.png').convert('RGB')).astype(np.int16)
            y=np.array(Image.open(f'{d}/{a}/frame_{f:05d}.png').convert('RGB')).astype(np.int16)
            e=np.abs(x-y);m=e.max(2)
            rows.append(dict(f=f,px=int((m>0).sum()),gt4=int((m>4).sum()),gt16=int((m>16).sum()),max=int(m.max()),mae=float(e.mean())))
            if m.max()>0:
                yy,xx=np.unravel_index(m.argmax(),m.shape);worst.append((int(m.max()),f,int(xx),int(yy)))
        worst.sort(reverse=True)
        mv=[r for r in rows if 61<=r['f']<=180];st=[r for r in rows if r['f']>=200];pre=[r for r in rows if r['f']<60]
        su=lambda rs:dict(px_mean=round(float(np.mean([r['px'] for r in rs])),1),px_pct=round(float(np.mean([r['px'] for r in rs]))/(1920*1061)*100,4),gt16_mean=round(float(np.mean([r['gt16'] for r in rs])),2),max=max(r['max'] for r in rs),mae=round(float(np.mean([r['mae'] for r in rs])),5))
        out[scene][lab]=dict(pre=su(pre),moving=su(mv),still=su(st),worst=worst[:8])
        print(f' {lab:3} pre {su(pre)}\n     move {su(mv)}\n     still {su(st)}\n     worst {worst[:5]}')
json.dump(out,open(sys.argv[1],'w'),indent=1)
