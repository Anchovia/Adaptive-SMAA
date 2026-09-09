"""Check matched tier final/spatial/mask sequences and pre-change defaults.

Manifest: high/medium_high/low each {final, mask}, spatial, default, before,
default_short (same warm-up as the tier captures).
Default may be shorter than the earlier reference (compares matching prefix).
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
from validate_temporal_capture_repeatability import inspect
from validate_contrast_tier_masks import mask


def rgb(path):
    with Image.open(path) as image:
        return np.array(image.convert('RGB'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args()
    data=json.loads(args.manifest.read_text())
    spatial=inspect(Path(data['spatial']))
    baseline=inspect(Path(data['before']))
    current=inspect(Path(data['default']))
    short=inspect(Path(data['default_short']))
    assert not short['phase_failures']
    assert (short['warmup'],short['frames'])==(spatial['warmup'],spatial['frames'])
    assert baseline['warmup']==current['warmup']
    assert baseline['frames']>=current['frames']
    assert baseline['mode_dirs']==current['mode_dirs']
    assert not baseline['phase_failures'] and not current['phase_failures']
    for name, digest in current['hashes'].items():
        assert baseline['hashes'][name]==digest, ('default regression', name)
    rows=[]
    for policy in ('high', 'medium_high', 'low'):
        final=inspect(Path(data[policy]['final']))
        masks=inspect(Path(data[policy]['mask']))
        for run in (spatial, final, masks):
            assert not run['phase_failures'] and run['prelude']>0
            assert (run['frames'],run['warmup'],run['mode_dirs']) == (spatial['frames'],spatial['warmup'],spatial['mode_dirs'])
        for name in final['hashes']:
            if 'ET2X' not in name:
                assert final['hashes'][name]==short['hashes'][name], (policy,name)
                continue
            f=rgb(Path(final['root'])/name)
            s=rgb(Path(spatial['root'])/name)
            m=mask(Path(masks['root'])/name)
            assert f.shape==s.shape and f.shape[:2]==m.shape
            different=np.any(f!=s,axis=2)
            violations=int(np.count_nonzero(different & ~m))
            assert violations==0,(policy,name,violations)
            rows.append({'policy':policy,'image':name,'changed_candidate_pixels':int(np.count_nonzero(different)),
                         'noncandidate_mismatch':violations})
    report={'status':'PASS','scope':'short engineering output regression, not quality evaluation',
            'default_images_identical':len(current['hashes']),'records':rows,'manifest':data}
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','default_images_identical':len(current['hashes']),
                      'policy_images_checked':len(rows),'noncandidate_mismatch':0}))


if __name__=='__main__':
    main()
