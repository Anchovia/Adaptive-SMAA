import numpy as np,os,json
from PIL import Image,ImageDraw,ImageFont
stats=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'c20_stats.json')))
out='D:/SMAAResearchCaptures/c20-adaptive-20261107/inspection';os.makedirs(out,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',16)
B='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory'
MODES={'4':('O-T2X-R','A-T2X-R','4번 O','4번 A'),'sel':(B+'+NoVelocityAlpha','A-'+B+'+NoVelocityAlpha','선택 경로','20번'),'19':(B+'+NoVelocityAlpha+VelocityInEdge','A-'+B+'+NoVelocityAlpha+VelocityInEdge','19번','21번')}
def sheet(scene,key,frames,box,z,name,title):
    d=stats[scene]['dir'];o,a,lo,la=MODES[key]
    w,h=(box[2]-box[0])*z,(box[3]-box[1])*z;gap=6;lab=22;left=86
    S=Image.new('RGB',(left+len(frames)*(w+gap),30+3*(h+lab)),(20,20,20));D=ImageDraw.Draw(S);D.text((6,5),title,fill=(255,255,255),font=font)
    for j,f in enumerate(frames):
        x=Image.open(f'{d}/{o}/frame_{f:05d}.png').convert('RGB').crop(box);y=Image.open(f'{d}/{a}/frame_{f:05d}.png').convert('RGB').crop(box)
        e=np.abs(np.array(x).astype(int)-np.array(y).astype(int)).max(2);diff=Image.fromarray(np.uint8(np.clip(e*8,0,255))).convert('RGB')
        for i,(im,l) in enumerate([(x,lo),(y,la),(diff,'차이x8')]):
            yy=30+i*(h+lab);S.paste(im.resize((w,h),Image.NEAREST),(left+j*(w+gap),yy+lab))
            D.text((left+j*(w+gap),yy+2),f'f{f} max {int(e.max())}',fill=(220,220,220),font=font)
            if j==0:D.text((4,yy+lab+4),l,fill=(255,255,255),font=font)
    p=f'{out}/{name}.png';S.save(p);print(p,S.size)
def cb(x,y,r):
    x=min(max(x,r),1920-r);y=min(max(y,r),1061-r);return (x-r,y-r,x+r,y+r)
sheet('bistro','4',list(range(153,159)),cb(985,484,24),5,'bi-4-worst','Bistro (985,484) 4번 Original/Adaptive, 5배 nearest')
sheet('bistro','sel',list(range(180,186))+[234,239],cb(1031,487,24),5,'bi-sel-still','Bistro (1031,487) 선택 경로/20번, 이동 끝과 정지 구간')
sheet('minecraft','sel',list(range(158,164)),cb(1669,962,24),5,'mc-sel-worst','Minecraft (1669,962) 선택 경로/20번, 5배 nearest')
sheet('minecraft','4',list(range(133,139)),cb(1613,892,24),5,'mc-4-worst','Minecraft (1613,892) 4번 Original/Adaptive')
sheet('minecraft','sel',list(range(126,132)),(956,524,1020,620),3,'mc-sel-seam','Minecraft 이음매 ROI 선택 경로/20번, 3배 nearest')
sheet('minecraft','sel',list(range(178,184)),(956,524,1020,620),3,'mc-sel-seam-stop','Minecraft 이음매 ROI 이동에서 정지로, 선택 경로/20번')
sheet('bistro','sel',list(range(126,132)),(1230,582,1358,670),2,'bi-sel-chair','Bistro 의자 ROI 선택 경로/20번, 2배 nearest')
sheet('minecraft','19',list(range(158,164)),cb(1669,962,24),5,'mc-19-worst','Minecraft (1669,962) 19번/21번')
