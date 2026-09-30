"""Original-color GPU GIFs and lossless six-frame/full-frame review artifacts."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont,ImageSequence
import numpy as np
from analyze_edge_persistence_gpu import ROOT,DOC,A,B,C,receipt
from edge_persistence_trace_inputs import sha,dump

OUT=ROOT/'Projects/CMAA2/Captures/edge-persistence-gpu-20261001'
FONT=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',17)
SMALL=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',14)
LABELS=[('⑥ 현재 edge','GPU / Pattern Off'),('직전 raw edge 유지','GPU / Pattern Off'),('④ 원본 T2X-R','GPU / Pattern On'),('고해상도 참조','spatial proxy')]

def paths(scene):
    _,_,root=receipt(scene,'Capture')
    reference=ROOT/'Projects/CMAA2/AutoBench'/('20260917_140856' if scene=='bistro' else '20260917_141121')/'SS-Reference'
    return [root/A,root/B,root/C,reference]

def panel(dirs,frame,roi,scale,title):
    w=(roi[2]-roi[0])*scale;h=(roi[3]-roi[1])*scale;cw=max(w,212)+12
    canvas=Image.new('RGB',(cw*4,76+h+34),(20,23,25));d=ImageDraw.Draw(canvas)
    d.text((8,5),title+f' | f{frame} | nearest {scale}×',font=SMALL,fill='white')
    for i,(folder,label) in enumerate(zip(dirs,LABELS)):
        with Image.open(folder/f'frame_{frame:05d}.png') as im:crop=im.crop(roi).resize((w,h),Image.Resampling.NEAREST).convert('RGB')
        x=i*cw+6;d.text((x,28),label[0],font=FONT,fill='white');d.text((x,51),label[1],font=SMALL,fill=(195,205,210))
        canvas.paste(crop,(x,76))
    d.text((8,82+h),'원본 RGB · 지터 조건 차이 포함 · GIF: 10 fps (원래 60 fps의 1/6 속도)',font=SMALL,fill='white')
    return canvas

def encode_gif(panels,path):
    # One palette and one quantization operation across the entire sequence.
    # Independently quantizing frames could add palette-induced shimmer.
    w,h=panels[0].size
    atlas=Image.new('RGB',(w,h*len(panels)))
    for i,im in enumerate(panels):atlas.paste(im,(0,i*h))
    atlas=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    indexed=[atlas.crop((0,i*h,w,(i+1)*h)) for i in range(len(panels))]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=100,loop=0,disposal=2,optimize=False)

def verify_sheets_and_extend():
    checks=[]
    for m in json.loads((DOC/'media.json').read_text(encoding='utf8')):
        scene=m['scene'];name=m['name'];window=name.rsplit('-',1)[1]
        region=name[len(scene)+1:-(len(window)+1)];roi=tuple(m['roi']);scale=m['scale']
        title=f'{scene} / {region} / {window} / ROI {roi}'
        with Image.open(m['sheet']) as sheet:
            for i,f in enumerate(m['six_frames']):
                original=panel(paths(scene),f,roi,scale,title)
                row=sheet.crop((0,i*original.height,original.width,(i+1)*original.height))
                assert np.array_equal(np.array(row),np.array(original)),name
        checks.append({'sheet':m['sheet'],'sha256':sha(m['sheet']),'rows_pixel_exact':6})
    scene='minecraft';roi=(956,524,1020,620);scale=3
    title=f'{scene} / thin-line / extended / ROI {roi}'
    frames=list(range(136,142));parts=[panel(paths(scene),f,roi,scale,title) for f in frames]
    sheet=Image.new('RGB',(parts[0].width,parts[0].height*6))
    for i,im in enumerate(parts):sheet.paste(im,(0,i*im.height))
    sheet.save(OUT/'minecraft-thin-line-extended-six.png')
    dump(DOC/'sheet-audit.json',{'validation':'PASS','sheets':checks,'extended_frames':frames})

def main():
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    configs=[('minecraft','thin-line',(956,524,1020,620),3),
             ('bistro','chairs',(1230,582,1358,670),2),
             ('bistro','window',(906,470,1034,558),2)]
    for scene,name,roi,scale in configs:
        dirs=paths(scene)
        for window,frames,six in [('moving',list(range(126,156)),list(range(130,136))),
                                  ('stop',list(range(172,196)),list(range(178,184))),
                                  ('still',list(range(190,196)),list(range(190,196)))]:
            stem=f'{scene}-{name}-{window}';title=f'{scene} / {name} / {window} / ROI {roi}'
            panels=[panel(dirs,f,roi,scale,title) for f in frames]
            # Each frame gets an explicit frame label, preserving even identical still colors.
            encode_gif(panels,OUT/(stem+'.gif'))
            panels[0].save(OUT/(stem+'.webp'),save_all=True,append_images=panels[1:],duration=100,loop=0,lossless=True,method=4)
            strip=[panel(dirs,f,roi,scale,title) for f in six]
            sheet=Image.new('RGB',(strip[0].width,strip[0].height*6),(20,23,25))
            for i,im in enumerate(strip):sheet.paste(im,(0,i*im.height))
            sheet.save(OUT/(stem+'-six.png'))
            max_err=0;mae=[]
            with Image.open(OUT/(stem+'.gif')) as gif:
                assert gif.n_frames==len(frames)
                total=0
                for i,im in enumerate(ImageSequence.Iterator(gif)):
                    total+=im.info['duration'];e=np.abs(np.array(im.convert('RGB'),dtype=np.int16)-np.array(panels[i],dtype=np.int16))
                    max_err=max(max_err,int(e.max()));mae.append(float(e.mean()))
                assert total==len(frames)*100
            with Image.open(OUT/(stem+'.webp')) as lossless:
                assert lossless.n_frames==len(frames)
                for i,im in enumerate(ImageSequence.Iterator(lossless)):assert np.array_equal(np.array(im.convert('RGB')),np.array(panels[i]))
            records.append({'scene':scene,'name':stem,'roi':roi,'scale':scale,'frames':frames,'six_frames':six,
                            'duration_ms':100,'source_fps':60,'playback_fps':10,'gif':str(OUT/(stem+'.gif')),
                            'sheet':str(OUT/(stem+'-six.png')),'lossless':str(OUT/(stem+'.webp')),
                            'gif_palette':'single sequence-wide palette; no dithering',
                            'gif_quantization_mean_rgb_error':float(np.mean(mae)),'gif_max_rgb_error':max_err})
            print(stem,'media roundtrip PASS',flush=True)
    for scene in ['bistro','minecraft']:
        dirs=paths(scene)
        for f in [131,180,192]:
            # Preserve all original pixels. Open the individual PNGs too.
            canvas=Image.new('RGB',(1920*2,1105*2),(20,23,25));draw=ImageDraw.Draw(canvas)
            for i,(folder,label) in enumerate(zip(dirs,LABELS)):
                x=(i%2)*1920;y=(i//2)*1105
                draw.text((x+8,y+8),f'{label[0]} / {label[1]} / {scene} f{f}',font=FONT,fill='white')
                with Image.open(folder/f'frame_{f:05d}.png') as im:canvas.paste(im.convert('RGB'),(x,y+44))
            canvas.save(OUT/f'{scene}-full-f{f}.png')
    (DOC/'media.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    verify_sheets_and_extend()

if __name__=='__main__':main()
