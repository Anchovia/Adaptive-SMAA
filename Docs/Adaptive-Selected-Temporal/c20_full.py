import glob
from PIL import Image,ImageDraw,ImageFont
CAP='D:/SMAAResearchCaptures/c20-adaptive-20261107/c20-a/capture'
out='D:/SMAAResearchCaptures/c20-adaptive-20261107/inspection-quality'
SEL='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',20)
for scene in ('bistro','minecraft'):
    d=glob.glob(f'{CAP}/{scene}/*/')[0]
    S=Image.new('RGB',(1920+8,1061+8+60),(20,20,20));D=ImageDraw.Draw(S)
    for i,f in enumerate((130,230)):
        for j,(lab,m) in enumerate((('④','O-T2X-R'),('20번','A-'+SEL))):
            im=Image.open(f'{d}{m}/frame_{f:05d}.png').convert('RGB').resize((960,530),Image.LANCZOS)
            x=j*968;y=30+i*(560);S.paste(im,(x,y));D.text((x+4,y-26),f'{lab} f{f} (전체 화면 1/2 축소)',fill=(255,255,255),font=font)
    p=f'{out}/{scene}-full-4-vs-20.png';S.save(p);print(p)
