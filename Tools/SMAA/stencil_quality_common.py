"""Pinned independent captures for the six-case stencil quality assessment."""
import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/First-Edge-Stencil-Quality'
OUT=Path('D:/SMAAResearchCaptures/first-edge-stencil-quality-20260929')
SCENES=['bistro','minecraft']
WINDOWS={'moving':(60,180),'transition':(160,220)}
SOURCE_RECORDS={}
LABELS={'AA-Off':'1 AA-Off','O-1X':'2 Original SMAA 1X',
        'ABL-TemporalOnly-R':'3 Full temporal / no spatial',
        'O-T2X-R':'4 Original SMAA T2X-R',
        'Raw-Edge-Stencil-Off-R':'5 Edge temporal / no spatial',
        'Spatial-Edge-Stencil-Off-R':'6 SMAA + edge temporal',
        'Raw-Full-Off-R':'Control raw full / jitter Off',
        'Spatial-Full-Off-R':'Control SMAA full / jitter Off'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(None)
def source(rev,path):
    commit=subprocess.check_output(['git','rev-parse',rev],cwd=ROOT,text=True).strip()
    raw=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
    value=json.loads(raw)
    if isinstance(value,dict) and 'validation' in value:assert value['validation']=='PASS',(rev,path)
    SOURCE_RECORDS[commit+':'+path]=dict(commit=commit,path=path,sha256=hashlib.sha256(raw).hexdigest())
    return value


def manifest(scene):
    base=source('e14f122',f'Docs/Baseline-Restart/{scene}-capture.json')
    raw=source('e2bbf87',f'Docs/Temporal-Only-Control/{scene}-capture.json')
    raw_stencil=source('ba1761d',f'Docs/First-Edge-Temporal-Only-Stencil/{scene}-capture.json')
    spatial=source('53ff61d',f'Docs/Spatial-First-Edge-Stencil/{scene}-capture.json')
    iso=source('53ff61d',f'Docs/Spatial-First-Edge-Stencil/{scene}-isolation-capture.json')
    for gate in [raw_stencil,spatial,iso]:assert not any(gate['mismatches'].values())
    assert not any(raw['baseline_mismatches'].values())
    cap=Path(raw['capture']);p5=Path(raw_stencil['capture']);p6=Path(spatial['capture'])
    sequences={m:cap/m for m in ['AA-Off','O-1X','ABL-TemporalOnly-R','O-T2X-R']}
    sequences.update({
        'Raw-Edge-Stencil-Off-R':p5/'ABL-FirstEdge-TemporalOnly-Stencil-PatternOff-R',
        'Spatial-Edge-Stencil-Off-R':p6/'ABL-Spatial-FirstEdge-Stencil-PatternOff-R',
        'Raw-Full-Off-R':p5/'ABL-FirstEdge-TemporalOnly-Full-PatternOff-R',
        'Spatial-Full-Off-R':p6/'ABL-Spatial-FullTemporal-PatternOff-R'})
    for folder in [*sequences.values(),Path(base['reference'])]:
        assert all((folder/f'frame_{i:05d}.png').is_file() for i in range(240)),folder
    return dict(scene=scene,reference=Path(base['reference']),sequences=sequences,
                raw_edge=sequences['Raw-Edge-Stencil-Off-R'],spatial_edge=sequences['Spatial-Edge-Stencil-Off-R'],
                original_baseline=Path(base['capture']))


def cached_scores(scene,window):
    native=source('e14f122',f'Docs/Baseline-Restart/{scene}-cgvqm.json')['results'][window]
    raw=source('2e3ac6c',f'Docs/First-Edge-Pattern-Off/{scene}-cgvqm.json')['results'][window]
    spatial=source('556f226',f'Docs/Spatial-First-Edge-Pattern-Off/{scene}-cgvqm.json')['results'][window]
    if window=='moving':
        for v in [raw,spatial]:
            assert abs(v['native_bridge_score_difference'])<=0.00002
    return {'O-1X':native['one_x_record'],'O-T2X-R':native['native_record'],
            'Raw-Edge-Stencil-Off-R':raw['records']['ABL-FirstEdge-TemporalOnly-PatternOff-R'],
            'Raw-Full-Off-R':raw['records']['ABL-FirstEdge-TemporalOnly-Full-PatternOff-R'],
            'Spatial-Edge-Stencil-Off-R':spatial['records']['ABL-Spatial-FirstEdge-PatternOff-R'],
            'Spatial-Full-Off-R':spatial['records']['ABL-Spatial-FullTemporal-PatternOff-R']}


def write_sources(name):
    DOC.mkdir(parents=True,exist_ok=True)
    (DOC/name).write_text(json.dumps(list(SOURCE_RECORDS.values()),indent=2)+'\n')
