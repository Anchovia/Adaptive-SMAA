"""Whole-scene overview and original 1x case4/case17 review pairs."""
from analyze_all_case_remeasurement import BUILD,OUT,FONT,load,capture_paths,rgb
from PIL import Image,ImageDraw

def main():
 paths,_=capture_paths(load(BUILD/'manifest.json'),load(BUILD/'runs.json'))
 folder=OUT/'inspection';folder.mkdir(exist_ok=True)
 for scene in ('bistro','minecraft'):
  for f in (130,181,230):
   overview=Image.new('RGB',(1920,1495),(24,24,24));d=ImageDraw.Draw(overview)
   d.text((8,6),f'{scene} f{f}; all cases whole-frame overview at 0.25x nearest; fine detail judged in original-pixel crops',font=FONT)
   native=None;target=None
   for i,c in enumerate(range(1,18)):
    a=rgb(paths[scene,c]/f'frame_{f:05d}.png')
    if c==4:native=a
    if c==17:target=a
    x=(i%4)*480;y=40+(i//4)*291;d.text((x+8,y),f'case{c}; pattern '+('On' if c in (3,4) else 'Off'),font=FONT)
    overview.paste(Image.fromarray(a).resize((480,265),Image.Resampling.NEAREST),(x,y+22))
   overview.save(folder/f'{scene}-whole-all-f{f}.png')
   pair=Image.new('RGB',(3840,1093),(24,24,24));dd=ImageDraw.Draw(pair)
   dd.text((8,6),f'{scene} f{f}: case4 pattern On left | case17 pattern Off right; original 1x; no brightness adjustment',font=FONT)
   pair.paste(Image.fromarray(native),(0,32));pair.paste(Image.fromarray(target),(1920,32))
   pair.save(folder/f'{scene}-whole-4-vs-17-f{f}.png')
 print('PASS: whole-frame inspection evidence',flush=True)

if __name__=='__main__':main()
