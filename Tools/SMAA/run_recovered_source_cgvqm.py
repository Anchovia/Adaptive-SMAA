"""Run the established CGVQM-2 recipe on recovered-source 2x2 captures.

Requires the successful spatial control hash bridge in comparison.json first.
Run after GPU performance measurements, never concurrently with CMAA2.
"""
import argparse,json,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--comparison',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=json.loads(a.comparison.read_text());assert len(result['quality'])==2
    root=Path(__file__).resolve().parents[2];runner=root/'Tools/SMAA/run_cgvqm_png_sequences.py'
    jobs=[]
    for scene,data in result['quality'].items():
        assert data['spatial_control_pixel_hash_mismatch']==0
        ref=Path(data['reference'])/'SS_Reference'
        for i in range(4):
            run=data['runs'][f'{scene}-profile-{i}'];paths=list(Path(run['report']).rglob('*.png'));assert len(paths)==480
            directory=paths[0].parent;mode=directory.name.replace('_','-')
            for window,start,count in [('central',150,180),('transition',410,30)]:
                destination=a.output/scene/f'profile-{i}'/window
                destination.mkdir(parents=True,exist_ok=True)
                args=[sys.executable,str(runner),'--test-dir',str(directory),'--reference-dir',str(ref),
                    '--output-dir',str(destination),'--start-index',str(start),'--frames',str(count),
                    '--model','2','--device','cuda','--classification','formal','--scene',scene,
                    '--camera-profile','flythrough-wide-yaw-360','--test-mode',mode,'--patch-scale','4','--patch-pool','mean']
                # No silent cache reuse: every recorded run uses freshly checked input frames.
                processes=subprocess.run(['tasklist','/FI','IMAGENAME eq CMAA2.exe','/FO','CSV','/NH'],
                    capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
                assert b'cmaa2.exe' not in processes.stdout.lower(),'CMAA2 must be closed before CGVQM'
                print(f'Running CGVQM-2: {scene} profile={i} {window}',flush=True)
                with (destination/'execution.log').open('w',encoding='utf-8') as log:
                    subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800,cwd=root)
                output=destination/'CGVQM-Results.json';assert output.is_file()
                jobs.append({'scene':scene,'profile':i,'window':window,'result':str(output)})
                (a.output/'jobs.json').write_text(json.dumps(jobs,indent=2))
                print(f'PASS: {scene} profile={i} {window}',flush=True)
if __name__=='__main__':main()
