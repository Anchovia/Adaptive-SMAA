"""Inspect the case12 settled-window hash exception without changing captures."""
from analyze_all_case_remeasurement import BUILD,OUT,ROIS,FONT,load,capture_paths,rgb,dump
from PIL import Image,ImageDraw
import numpy as np

def main():
 paths,_=capture_paths(load(BUILD/'manifest.json'),load(BUILD/'runs.json'))
 results=[]
 for scene,roi in [('bistro','thin-chair'),('minecraft','thin-seam')]:
  frames=[rgb(paths[scene,12]/f'frame_{f:05d}.png') for f in range(220,240)]
  diffs=[np.abs(b.astype(np.int16)-a.astype(np.int16)) for a,b in zip(frames,frames[1:])]
  results.append(dict(scene=scene,case=12,frames=list(range(220,240)),
   mean_adjacent_rgb_difference=float(np.mean([d.mean() for d in diffs])),
   maximum_adjacent_channel_difference=int(max(d.max() for d in diffs)),
   mean_changed_pixel_fraction=float(np.mean([(d!=0).any(axis=2).mean() for d in diffs])),
   interpretation='Output not invariant; tiny differences alone do not prove visible flicker or its cause'))
  x0,y0,x1,y1=ROIS[scene][roi];w,h=(x1-x0)*2,(y1-y0)*2
  im=Image.new('RGB',(w*6+16,(h+28)*2+40),(24,24,24));draw=ImageDraw.Draw(im)
  draw.text((8,6),f'{scene}; settled f234..239; case4 On / case12 Off; nearest2x',font=FONT)
  for row,c in enumerate([4,12]):
   y=40+row*(h+28);draw.text((8,y),f'case{c}: f234 / 235 / 236 / 237 / 238 / 239',font=FONT)
   for col,f in enumerate(range(234,240)):
    a=rgb(paths[scene,c]/f'frame_{f:05d}.png')[y0:y1,x0:x1]
    im.paste(Image.fromarray(a).resize((w,h),Image.Resampling.NEAREST),(8+col*w,y+22))
  im.save(OUT/'inspection'/f'{scene}-case12-settled-234-239.png')
 dump(OUT/'settling-exception.json',results)
 print(results)
if __name__=='__main__':main()
