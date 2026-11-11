# Nearest-zoom sheets for reprojection On/Off: T2X-R, T2X, ET2X-R, ET2X and the reference.
import os,glob,sys
from PIL import Image,ImageDraw,ImageFont
CAP='D:/SMAAResearchCaptures/c23-reprojection-off-20261111/c23-b/capture'
REF='D:/SMAAResearchCaptures/c20-adaptive-20261107/c20-ref/reference'
out='D:/SMAAResearchCaptures/c23-reprojection-off-20261111/inspection';os.makedirs(out,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',15)
SEL='ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
SELOFF=SEL.replace('ET2X-R-','ET2X-')
def rows(prefix):
    a='A-' if prefix=='A' else ''
    return [(f'{prefix}-T2X-R',('cap',f'{prefix}-T2X-R')),(f'{prefix}-T2X',('cap',f'{prefix}-T2X')),(f'{prefix}-ET2X-R',('cap',a+'ABL-'+SEL)),(f'{prefix}-ET2X',('cap',a+'ABL-'+SELOFF)),('기준 영상',('ref','SS-Reference'))]
def root(scene,kind):
    d=glob.glob(f'{CAP if kind=="cap" else REF}/{scene}/*/');assert len(d)==1;return d[0]
def sheet(scene,frames,box,z,name,title,rws):
    w,h=(box[2]-box[0])*z,(box[3]-box[1])*z;gap=5;lab=20;left=90
    S=Image.new('RGB',(left+len(frames)*(w+gap),28+len(rws)*(h+lab)),(20,20,20));D=ImageDraw.Draw(S);D.text((6,4),title,fill=(255,255,255),font=font)
    for i,(label,(kind,mode)) in enumerate(rws):
        yy=28+i*(h+lab);D.text((4,yy+lab+4),label,fill=(255,255,255),font=font)
        for j,f in enumerate(frames):
            S.paste(Image.open(f'{root(scene,kind)}{mode}/frame_{f:05d}.png').convert('RGB').crop(box).resize((w,h),Image.NEAREST),(left+j*(w+gap),yy+lab))
            if i==0:D.text((left+j*(w+gap),yy+1),f'f{f}',fill=(220,220,220),font=font)
    p=f'{out}/{name}.png';S.save(p);print(p,S.size)
seam=(956,524,1020,620);legs=(1262,606,1326,656);win=(950,460,1110,588)
for pre in ('O','A'):
    for tag,fr in (('moving',range(126,132)),('stop',range(180,186))):
        fr=list(fr)
        sheet('minecraft',fr,seam,2,f'{pre}-mc-seam-{tag}',f'{pre} Minecraft 이음매 {seam}, {tag} f{fr[0]}-{fr[-1]}, 2배 nearest',rows(pre))
        sheet('bistro',fr,legs,4,f'{pre}-bi-legs-{tag}',f'{pre} Bistro 의자 다리 {legs}, {tag} f{fr[0]}-{fr[-1]}, 4배 nearest',rows(pre))
sheet('bistro',list(range(126,132)),win,1,'O-bi-windows-moving',f'O Bistro 창문 {win}, moving f126-131, 1배',rows('O'))
# Half-scale full frames, moving f130: O-T2X-R | O-T2X | O-ET2X-R | O-ET2X
for scene in ('bistro','minecraft'):
    S=Image.new('RGB',(1926,2*531+60),(20,20,20));D=ImageDraw.Draw(S)
    for i,(lab,(kind,m)) in enumerate(rows('O')[:4]):
        x=(i%2)*966;y=30+(i//2)*561;S.paste(Image.open(f'{root(scene,kind)}{m}/frame_00130.png').convert('RGB').resize((960,531),Image.LANCZOS),(x,y));D.text((x+4,y-26),f'{lab} f130 (1/2 축소)',fill=(255,255,255),font=font)
    S.save(f'{out}/{scene}-full-f130.png');print(f'{out}/{scene}-full-f130.png')
