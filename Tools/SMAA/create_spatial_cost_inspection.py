"""Lossless nearest-neighbor sheets for direct inspection; no quality metric claim."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont

R=Path(__file__).resolve().parents[2];D=R/'Docs/Edge-Persistence-Spatial-Cost';out=R/'tmp/spatial-cost-inspection';out.mkdir(exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
modes=[('E-PreviousRawEdge-FirstStencil','E: existing case 8'),('F-EagerPreviousFetch','F: eager lookup'),('G-DepthMask-CurrentWeights','G: current-only weights')]
windows={'moving':range(130,136),'transition':range(178,184),'still':range(190,196)}
records=[]
for scene,roi,scale in [('bistro',(1230,582,1358,670),2),('minecraft',(956,524,1020,620),3)]:
    result=json.loads((D/f'{scene}-capture.json').read_text());base=Path(result['capture_root'])
    w=(roi[2]-roi[0])*scale;h=(roi[3]-roi[1])*scale
    for phase,frames in windows.items():
        sheet=Image.new('RGB',(6*(w+4)+8,3*(h+54)+8),(20,22,25));draw=ImageDraw.Draw(sheet)
        for row,(mode,label) in enumerate(modes):
            y=8+row*(h+54);draw.text((8,y),label,fill='white',font=font)
            for col,f in enumerate(frames):
                x=8+col*(w+4);draw.text((x,y+23),str(f),fill='white',font=font)
                with Image.open(base/mode/f'frame_{f:05d}.png') as im:tile=im.crop(roi).resize((w,h),Image.Resampling.NEAREST)
                sheet.paste(tile,(x,y+48))
        p=out/f'{scene}-{phase}.png';sheet.save(p)
        records.append(dict(path=str(p),scene=scene,roi=roi,scale=scale,frames=list(frames),modes=[x[0] for x in modes],sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    records.append(dict(full_frame=str(base/modes[0][0]/'frame_00131.png'),scene=scene))
(D/'inspection-manifest.json').write_text(json.dumps(dict(original_colors=True,resize='nearest',sheets=records,visual_inspection_completed=False),indent=2)+'\n')
print(out)
