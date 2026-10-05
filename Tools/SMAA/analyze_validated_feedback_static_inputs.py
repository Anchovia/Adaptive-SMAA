"""Compare captured static inputs without assuming exact-zero velocity."""
import hashlib,json
from pathlib import Path
from analyze_edge_validated_rgb_feedback import DOC,MODES,load

records=[]
for scene in ('bistro','minecraft'):
    evidence=DOC/f'{scene}-capture.json'
    data=load(evidence)
    assert data['validation']=='PASS'
    cap=Path(data['capture_root'])
    for mode in MODES[5:7]:
        for suffix in ('current.dds','raw.dds','velocity.dds','edge.rg8'):
            files=[]
            for frame in range(190,196):
                path=cap/mode/f'frame_{frame:05d}-{suffix}'
                files.append(dict(frame=frame,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            records.append(dict(scene=scene,mode=mode,resource=suffix,unique_file_hashes=len({r['sha256'] for r in files}),files=files,capture_evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest()))
assert all(r['unique_file_hashes']==1 for r in records)
(DOC/'static-input-hashes.json').write_text(json.dumps(dict(validation='PASS',frames=[190,195],records=records,scope='Exact stored input content is unchanged; this does not assert float-zero velocity or a universal cause for settling.'),indent=2)+'\n')
print('PASS unchanged static inputs:',len(records),'resource sequences')
