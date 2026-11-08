# Nearest-zoom sheets around the case 22 route switches: case 4, selected route, case 22, reference.
import os,glob
from PIL import Image,ImageDraw,ImageFont
CAP='D:/SMAAResearchCaptures/c22-still-switch-20261109/c22-c/capture'
CAP0='D:/SMAAResearchCaptures/c22-still-switch-20261109/c22-a/capture'
REF='D:/SMAAResearchCaptures/c20-adaptive-20261107/c20-ref/reference'
out='D:/SMAAResearchCaptures/c22-still-switch-20261109/inspection-handoff';os.makedirs(out,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',15)
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
ROWS=[('④',('cap','O-T2X-R')),('선택 경로',('cap',SEL)),('22 초기화',('cap0','SWITCH-StillO-T2X-R-N4+MovingSelected')),('22번',('cap','SWITCH-StillO-T2X-R-N4+MovingSelected')),('기준 영상',('ref','SS-Reference'))]
def root(scene,kind):
    d=glob.glob(f'{ {"cap":CAP,"cap0":CAP0,"ref":REF}[kind]}/{scene}/*/');assert len(d)==1;return d[0]
def sheet(scene,frames,box,z,name,title,labels=None):
    w,h=(box[2]-box[0])*z,(box[3]-box[1])*z;gap=5;lab=20;left=90
    S=Image.new('RGB',(left+len(frames)*(w+gap),28+len(ROWS)*(h+lab)),(20,20,20));D=ImageDraw.Draw(S);D.text((6,4),title,fill=(255,255,255),font=font)
    for i,(label,(kind,mode)) in enumerate(ROWS):
        yy=28+i*(h+lab);D.text((4,yy+lab+4),label,fill=(255,255,255),font=font)
        for j,f in enumerate(frames):
            im=Image.open(f'{root(scene,kind)}{mode}/frame_{f:05d}.png').convert('RGB').crop(box)
            S.paste(im.resize((w,h),Image.NEAREST),(left+j*(w+gap),yy+lab))
            if i==0:D.text((left+j*(w+gap),yy+1),f'f{f}'+(f' {labels[j]}' if labels else ''),fill=(220,220,220),font=font)
    p=f'{out}/{name}.png';S.save(p);print(p,S.size)
seam=(956,524,1020,620);legs=(1262,606,1326,656)
# 22 routes: selected f0-4, native f5-61, selected f62-184, native f185-239 (verified from the report rows).
def lab(fr):return ['④' if (5<=f<=61 or f>=185) else '선택' for f in fr]
for tag,fr in [('move-start',range(58,64)),('stop',range(180,186)),('to-native',range(184,190)),('settled',range(226,232))]:
    fr=list(fr)
    sheet('minecraft',fr,seam,2,f'mc-seam-{tag}',f'Minecraft 이음매 {seam}, {tag} f{fr[0]}-{fr[-1]}, 2배 nearest, 프레임 옆은 22번이 그린 경로',lab(fr))
    sheet('bistro',fr,legs,4,f'bi-legs-{tag}',f'Bistro 의자 다리 {legs}, {tag} f{fr[0]}-{fr[-1]}, 4배 nearest, 프레임 옆은 22번이 그린 경로',lab(fr))
