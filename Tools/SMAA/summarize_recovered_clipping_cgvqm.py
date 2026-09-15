"""Freeze verified clipping scores and explicitly historical comparison controls."""
import hashlib, json
from pathlib import Path
from validate_recovered_clipping import NAMES

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Docs/Recovered-Clipping-Ablation-20260915'

def load_result(path,reference_hash):
    raw=path.read_bytes();r=json.loads(raw)
    assert r['classification']=='formal'
    assert r['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
    assert r['configuration']==dict(fps=60,patch_scale=4,patch_pool='mean',models=['2'],reference_index_offset=0)
    assert r['reference_sequence']['pixel_sha256']==reference_hash
    for side in ('test','reference'):
        trip=r[side+'_round_trip'];seq=r[side+'_sequence']
        assert trip['mismatched_values']==trip['max_absolute_difference']==0
        assert trip['decoded_frames']==seq['frame_count'] and trip['codec']=='ffv1' and trip['pixel_format']=='bgr0'
    return dict(result=str(path),result_sha256=hashlib.sha256(raw).hexdigest(),
        score=r['results']['CGVQM-2']['score_higher_is_better'],provenance=r['provenance'],runtime=r['runtime'],
        official_cgvqm=r['official_cgvqm'],configuration=r['configuration'],
        test_sequence=r['test_sequence'],reference_sequence=r['reference_sequence'],
        test_round_trip=r['test_round_trip'],reference_round_trip=r['reference_round_trip'])

def main():
    jobs=json.loads((ROOT/'tmp/recovered-clipping/cgvqm/jobs.json').read_text());assert len(jobs)==16
    keys={(r['scene'],r['window'],r['variant']) for r in jobs};assert len(keys)==16
    details=[];controls=[];effects=[]
    for scene in ('bistro','minecraft'):
        for window in ('central','transition'):
            rows=[next(r for r in jobs if (r['scene'],r['window'],r['variant'])==(scene,window,n)) for n in NAMES]
            assert len({r['reference_pixel_sha256'] for r in rows})==1
            refhash=rows[0]['reference_pixel_sha256']
            for r in rows:
                d=load_result(Path(r['result']),refhash)
                assert d['result_sha256']==r['result_sha256'] and d['score']==r['score']
                assert d['test_sequence']['pixel_sha256']==r['test_pixel_sha256']
                details.append(dict(scene=scene,window=window,variant=r['variant'],reused_baseline=r['reused_historical_baseline'],**d))
            x=[r['score'] for r in rows]
            effects.append(dict(scene=scene,window=window,signed_main=((x[1]-x[0])+(x[3]-x[2]))/2,
                domain_main=((x[2]-x[0])+(x[3]-x[1]))/2,interaction=x[3]-x[2]-x[1]+x[0],both_minus_source=x[3]-x[0]))
            for name,path in [
                ('O-T2X-R',ROOT/'tmp/integrated-source-cgvqm'/scene/'standard'/window/'CGVQM-Results.json'),
                ('O-ET2X-R-DocCandidate-DocKernel',ROOT/'tmp/source-comparison-cgvqm'/scene/'profile-0'/window/'CGVQM-Results.json'),
                ('O-ET2X-R-SourceCandidate-DocKernel',ROOT/'tmp/source-comparison-cgvqm'/scene/'profile-1'/window/'CGVQM-Results.json')]:
                d=load_result(path,refhash)
                assert d['provenance']==dict(scene=scene,camera_profile='flythrough-wide-yaw-360',test_mode=name,reference_id='SS-Reference')
                controls.append(dict(scene=scene,window=window,mode=name,historical_control=True,**d))
    OUT.mkdir(parents=True,exist_ok=True)
    result=dict(status='PASS',records=details,historical_controls=controls,effects=effects,
        scope='New clipping scores plus pixel-identical source reuse. Standard/document controls are previous validated captures, with matching reference hashes; not newly captured in this gate.')
    (OUT/'cgvqm.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(effects,indent=2))
if __name__=='__main__':main()
