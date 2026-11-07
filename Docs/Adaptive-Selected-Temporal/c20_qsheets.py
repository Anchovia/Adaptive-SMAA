# Nearest-zoom ROI sheets: case 4, A-4, selected route, 20, 21 and the supersample reference, same frames.
import numpy as np,os,glob
from PIL import Image,ImageDraw,ImageFont
CAP='D:/SMAAResearchCaptures/c20-adaptive-20261107/c20-a/capture'
REF='D:/SMAAResearchCaptures/c20-adaptive-20261107/c20-ref/reference'
out='D:/SMAAResearchCaptures/c20-adaptive-20261107/inspection-quality';os.makedirs(out,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',15)
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
ROWS=[('④',('cap','O-T2X-R')),('A-④',('cap','A-T2X-R')),('선택 경로',('cap',SEL)),('20번',('cap','A-'+SEL)),('21번',('cap','A-'+SEL+'+VelocityInEdge')),('기준 영상',('ref','SS-Reference'))]
def root(scene,kind):
    d=glob.glob(f'{CAP if kind=="cap" else REF}/{scene}/*/');assert len(d)==1;return d[0]
def sheet(scene,frames,box,z,name,title):
    w,h=(box[2]-box[0])*z,(box[3]-box[1])*z;gap=5;lab=20;left=90
    S=Image.new('RGB',(left+len(frames)*(w+gap),28+len(ROWS)*(h+lab)),(20,20,20));D=ImageDraw.Draw(S);D.text((6,4),title,fill=(255,255,255),font=font)
    for i,(label,(kind,mode)) in enumerate(ROWS):
        yy=28+i*(h+lab);D.text((4,yy+lab+4),label,fill=(255,255,255),font=font)
        for j,f in enumerate(frames):
            im=Image.open(f'{root(scene,kind)}{mode}/frame_{f:05d}.png').convert('RGB').crop(box)
            S.paste(im.resize((w,h),Image.NEAREST),(left+j*(w+gap),yy+lab))
            if i==0:D.text((left+j*(w+gap),yy+1),f'f{f}',fill=(220,220,220),font=font)
    p=f'{out}/{name}.png';S.save(p);print(p,S.size)
chair=(1230,582,1358,670);seam=(956,524,1020,620);windows=(950,460,1110,588);leaves=(1420,590,1580,718)
if not os.environ.get('TIGHT'):
  for tag,fr in [('moving',range(126,132)),('transition',range(178,184)),('settled',range(226,232))]:
    sheet('bistro',list(fr),chair,2,f'bi-chair-{tag}',f'Bistro 의자 ROI {chair}, {tag} f{fr[0]}-{fr[-1]}, 2배 nearest')
    sheet('minecraft',list(fr),seam,2,f'mc-seam-{tag}',f'Minecraft 이음매 ROI {seam}, {tag} f{fr[0]}-{fr[-1]}, 2배 nearest')
sheet('bistro',list(range(126,132)),windows,1,'bi-windows-moving',f'Bistro 창문 ROI {windows}, moving f126-131, 1배')
sheet('minecraft',list(range(126,132)),leaves,1,'mc-leaves-moving',f'Minecraft 잎 ROI {leaves}, moving f126-131, 1배')

# Tighter views (4 rows) for the thin chair legs.
def sheet4(scene,frames,box,z,name,title):
    global ROWS
    keep=ROWS;ROWS=[r for r in keep if r[0] in ('④','선택 경로','20번','기준 영상')]
    try:sheet(scene,frames,box,z,name,title)
    finally:ROWS=keep
if __name__=='__main__' and os.environ.get('TIGHT'):
    legs=(1262,606,1326,656)
    sheet4('bistro',list(range(126,132)),legs,4,'bi-legs-moving',f'Bistro 의자 다리 {legs}, moving f126-131, 4배 nearest')
    sheet4('bistro',list(range(178,184)),legs,4,'bi-legs-transition',f'Bistro 의자 다리 {legs}, transition f178-183, 4배 nearest')
    sheet4('bistro',list(range(226,232)),legs,4,'bi-legs-settled',f'Bistro 의자 다리 {legs}, settled f226-231, 4배 nearest')
