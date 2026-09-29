"""Compare every post-lifecycle-fix final PNG hash with the initial item-6 capture."""
import argparse,csv,json
from pathlib import Path
from analyze_spatial_first_edge import D,MODES,receipt,sha
def main(scene):
    rc,p,text=receipt(scene,'BridgeCapture');prior=json.loads((D/f'{scene}-capture.json').read_text());cap=Path(prior['capture'])
    rows=[[x.strip() for x in r] for r in csv.reader(text.splitlines()) if r and r[0].strip()=='bridge_hash']
    assert len(rows)==1200;differences=[]
    for mode in MODES:
        rr=[r for r in rows if r[1]==mode];assert [int(r[2]) for r in rr]==list(range(240))
        for r in rr:
            expected=sha(cap/mode/f'frame_{int(r[2]):05d}.png')
            if r[3]!=expected:differences.append(dict(mode=mode,frame=int(r[2]),expected=expected,actual=r[3]))
    assert not differences,differences[:5]
    out=dict(validation='PASS',scene=scene,receipt=rc,prior_capture=str(cap),png_byte_sha256_comparisons=len(rows),mismatches=0,
        note='Same WIC PNG encoding byte hashes match for every frame, hence RGB outputs unchanged after frame lifecycle fix. Old capture EXE differs; both provenance records retained.')
    (D/f'{scene}-frame-lifecycle-bridge.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: {scene} all 1200 final PNG SHA-256 values match across frame lifecycle fix')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--scene',choices=['bistro','minecraft'],required=True);main(ap.parse_args().scene)
