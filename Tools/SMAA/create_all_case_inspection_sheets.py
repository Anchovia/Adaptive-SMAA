"""Original-pixel review grids; user-facing media remain two-way comparisons."""
from analyze_all_case_remeasurement import ROOT,BUILD,OUT,ROIS,FONT,load,capture_paths,rgb
from PIL import Image,ImageDraw
from pathlib import Path

def main():
 paths,_=capture_paths(load(BUILD/'manifest.json'),load(BUILD/'runs.json'))
 folder=OUT/'inspection';folder.mkdir(exist_ok=True)
 groups=[[4,1,2,3,5,6,7,8,9],[4,10,11,12,13,14,15,16,17]]
 for scene,roi,scale in [('bistro','thin-chair',1),('minecraft','thin-seam',2)]:
  x0,y0,x1,y1=ROIS[scene][roi];w,h=(x1-x0)*scale,(y1-y0)*scale
  for phase,start in [('moving',126),('transition',178)]:
   for n,cases in enumerate(groups):
    sheet=Image.new('RGB',(w*6+16,(h+26)*len(cases)+40),(24,24,24));d=ImageDraw.Draw(sheet)
    d.text((8,6),f'{scene} {roi}; {phase} f{start}..{start+5}; nearest {scale}x; 4 pattern On; 3 On, others Off',font=FONT)
    for row,c in enumerate(cases):
     y=40+row*(h+26);d.text((8,y),f'case {c}: f{start}, {start+1}, {start+2}, {start+3}, {start+4}, {start+5}',font=FONT)
     for col,f in enumerate(range(start,start+6)):
      a=rgb(paths[scene,c]/f'frame_{f:05d}.png')[y0:y1,x0:x1]
      sheet.paste(Image.fromarray(a).resize((w,h),Image.Resampling.NEAREST),(8+col*w,y+22))
    sheet.save(folder/f'{scene}-{roi}-{phase}-group{n+1}.png')
 for scene,roi in [('bistro','windows'),('minecraft','leaves'),('minecraft','grass-seam')]:
  cases=[4,6,11,14,15,16,17];x0,y0,x1,y1=ROIS[scene][roi];w,h=x1-x0,y1-y0
  for phase,start in [('moving',126),('transition',178)]:
   sheet=Image.new('RGB',(w*6+16,(h+26)*len(cases)+40),(24,24,24));d=ImageDraw.Draw(sheet)
   d.text((8,6),f'{scene} {roi}; {phase}; original 1x; 4 pattern On, others Off',font=FONT)
   for row,c in enumerate(cases):
    y=40+row*(h+26);d.text((8,y),f'case{c}: f{start}..{start+5}',font=FONT)
    for col,f in enumerate(range(start,start+6)):
     a=rgb(paths[scene,c]/f'frame_{f:05d}.png')[y0:y1,x0:x1];sheet.paste(Image.fromarray(a),(8+col*w,y+22))
   sheet.save(folder/f'{scene}-{roi}-{phase}.png')
 reference=load(ROOT/'Docs/Baseline-Restart/reused-reference-provenance.json')
 for scene,roi in [('bistro','thin-chair'),('minecraft','thin-seam')]:
  x0,y0,x1,y1=ROIS[scene][roi];w,h=(x1-x0)*3,(y1-y0)*3
  for start in (124,129):
   cases=[4,14,17,'reference'];sheet=Image.new('RGB',(w*4+16,(h+26)*5+40),(24,24,24));d=ImageDraw.Draw(sheet)
   d.text((8,6),f'{scene} {roi}; extended f{start}..{start+4}; 4 / 14 / 17 / spatial proxy; nearest3x',font=FONT)
   for row,f in enumerate(range(start,start+5)):
    y=40+row*(h+26);d.text((8,y),f'f{f}: 4 | 14 | 17 | spatial reference proxy',font=FONT)
    for col,c in enumerate(cases):
     p=Path(reference[scene]['reference']) if c=='reference' else paths[scene,c]
     a=rgb(p/f'frame_{f:05d}.png')[y0:y1,x0:x1];sheet.paste(Image.fromarray(a).resize((w,h),Image.Resampling.NEAREST),(8+col*w,y+22))
   sheet.save(folder/f'{scene}-{roi}-extended-{start}.png')
  w,h=(x1-x0)*2,(y1-y0)*2;sheet=Image.new('RGB',(w*5+16,(h+26)*4+40),(24,24,24));d=ImageDraw.Draw(sheet)
  d.text((8,6),f'{scene} {roi}; settled f230; all cases; nearest2x; 3/4 pattern On',font=FONT)
  for i,c in enumerate(range(1,18)):
   x=8+(i%5)*w;y=40+(i//5)*(h+26);d.text((x,y),f'case {c}',font=FONT)
   a=rgb(paths[scene,c]/'frame_00230.png')[y0:y1,x0:x1];sheet.paste(Image.fromarray(a).resize((w,h),Image.Resampling.NEAREST),(x,y+22))
  sheet.save(folder/f'{scene}-{roi}-settled-all.png')
 print('PASS: original-pixel contiguous inspection sheets',flush=True)

if __name__=='__main__':main()
