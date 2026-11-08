# Slow side-by-side GIF around the stop switch (f176-196): case 4 | selected | 22 seeded | 22 handoff, nearest zoom.
import glob
from PIL import Image,ImageDraw,ImageFont
C='D:/SMAAResearchCaptures/c22-still-switch-20261109/c22-c/capture';C0='D:/SMAAResearchCaptures/c22-still-switch-20261109/c22-a/capture'
out='D:/SMAAResearchCaptures/c22-still-switch-20261109/inspection-handoff'
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
SW='SWITCH-StillO-T2X-R-N4+MovingSelected'
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',16)
cols=[('④',C,'O-T2X-R'),('선택 경로',C,SEL),('22 초기화',C0,SW),('22번',C,SW)]
for scene,box,z in (('minecraft',(956,524,1020,620),3),('bistro',(1262,606,1326,656),4)):
    w,h=(box[2]-box[0])*z,(box[3]-box[1])*z;frames=[]
    for f in range(176,197):
        S=Image.new('RGB',(4*(w+6),h+50),(20,20,20));D=ImageDraw.Draw(S)
        route='선택' if f<=184 else '④'
        D.text((4,2),f'{scene} f{f}  (22번 경로: {route}, 카메라 정지 f181부터)',fill=(255,255,255),font=font)
        for i,(lab,root,m) in enumerate(cols):
            d=glob.glob(f'{root}/{scene}/*/')[0]
            S.paste(Image.open(f'{d}{m}/frame_{f:05d}.png').convert('RGB').crop(box).resize((w,h),Image.NEAREST),(i*(w+6),46))
            D.text((i*(w+6)+2,24),lab,fill=(220,220,220),font=font)
        frames.append(S)
    p=f'{out}/{scene}-stop-switch-f176-196-8fps.gif'
    frames[0].save(p,save_all=True,append_images=frames[1:],duration=125,loop=0)
    with Image.open(p) as g:print(p,g.n_frames,g.size)
