"""Use bundled image libraries with the existing research PyAV dependency.
All source-frame and decoded-media verification remains mandatory.
"""
from pathlib import Path
import argparse,sys,runpy
import PIL,numpy
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--comparison',action='store_true');p.add_argument('--frames',choices=[240,720],type=int,default=240);p.add_argument('--output',type=Path)
a=p.parse_args()
try:
 import av
except ModuleNotFoundError:
 dependency_root=next((root for root in [ROOT,*ROOT.parents] if (root/'.research-tools/quality-venv/Lib/site-packages/av').exists()),None)
 if dependency_root is None:raise RuntimeError('PyAV is unavailable; run with a Python environment providing PyAV')
 # Append after importing bundled PIL/numpy; do not replace verified image libraries.
 sys.path.append(str(dependency_root/'.research-tools/quality-venv/Lib/site-packages'))
 import av
print('Media runtime:',PIL.__version__,numpy.__version__,av.__version__,flush=True)
sys.path.insert(0,str(ROOT/'Tools/SMAA'))
script=ROOT/'Tools/SMAA'/('create_source_component_comparison.py' if a.comparison else 'create_source_component_playback.py')
sys.argv=[str(script)]
if not a.comparison:
 if a.output is None:p.error('--output is required for individual media')
 sys.argv+=['--frames',str(a.frames),'--output',str(a.output)]
runpy.run_path(str(script),run_name='__main__')
