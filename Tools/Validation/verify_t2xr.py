"""PNG identity checks for the SMAA T2x-R option of the improved SMAA demo.

Identity is SHA-256 of the PNG file; every frame of the new capture must also pass the PNG chunk CRC check.
Required:
  T2xR-Ultra against O-T2X-R of c28 and c29 (the research T2x-R).
  SMAA 1X (O-1X, O-High, O-Medium, O-Low) against the SpatialCapture of c29.
  SMAA Adaptive + Temporal: AT-Ultra against the final combination of c28 and c29, AT-High/Medium/Low against the
      baseline capture c30; Temporal Off (ATOff-*) against Adaptive SMAA 1X of the same preset in c29.
  Switch runs (other option at frames 90..149): Switch-T2xR-AT and Switch-T2xR-O1X frames 0..89 equal T2xR-Ultra,
      90..149 equal AT-Reset90 (history restarted at 90) or O-1X, and 150..239 equal T2xR-Reset150 (history restarted
      at 150), so no jitter or history is carried over.
Informative: T2xR-High/Medium/Low against T2xR-Ultra; in the still frames 0..59 of T2xR-Ultra, how many frames equal
  the frame two before (the jitter pair repeats).

usage: python verify_t2xr.py --capture <run> --c28 <run> --c29-temporal <run> --c29-spatial <run> --c30 <run> --out <json>
"""
import argparse, functools, hashlib, json, struct, zlib
from pathlib import Path

FINAL = 'A-ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha+HistoryVelocityPingPongCross5'
PRESETS = (('Ultra', 'A-1X'), ('High', 'A-High'), ('Medium', 'A-Medium'), ('Low', 'A-Low'))


@functools.lru_cache(maxsize=None)
def crc_ok(p):
    data = Path(p).read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return False
    pos = 8
    while pos + 12 <= len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        if pos + 12 + n > len(data) or zlib.crc32(data[pos + 4:pos + 8 + n]) & 0xffffffff != struct.unpack('>I', data[pos + 8 + n:pos + 12 + n])[0]:
            return False
        pos += 12 + n
    return pos == len(data)


@functools.lru_cache(maxsize=None)
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bridge(new, ref, frames, ref_frames=None):
    frames = list(frames)
    ref_frames = list(ref_frames) if ref_frames is not None else frames
    pairs = [(new / f'frame_{a:05d}.png', ref / f'frame_{b:05d}.png') for a, b in zip(frames, ref_frames)]
    missing = sum(1 for a, b in pairs if not a.is_file() or not b.is_file())
    if missing:
        return dict(new=str(new), reference=str(ref), frames=len(pairs), missing=missing, identical=0, crc_ok=0, pass_=False)
    same = [a for a, b in pairs if sha(str(a)) == sha(str(b))]
    good = sum(crc_ok(str(a)) for a, _ in pairs)
    first = next((a.name for a, b in pairs if a not in same), None)
    return dict(new=str(new), reference=str(ref), first=frames[0], last=frames[-1], frames=len(pairs), missing=0, identical=len(same),
                crc_ok=good, first_different=first, pass_=len(same) == len(pairs) and good == len(pairs))


def main():
    ap = argparse.ArgumentParser()
    for k in ('capture', 'c28', 'c29-temporal', 'c29-spatial', 'c30', 'out'):
        ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    cap, c28, t29, s29, c30 = map(Path, (a.capture, a.c28, a.c29_temporal, a.c29_spatial, a.c30))
    every = range(240)
    req = {
        'T2xR-Ultra vs c28 O-T2X-R': bridge(cap / 'T2xR-Ultra', c28 / 'O-T2X-R', every),
        'T2xR-Ultra vs c29 O-T2X-R': bridge(cap / 'T2xR-Ultra', t29 / 'O-T2X-R', every),
    }
    for name in ('O-1X', 'O-High', 'O-Medium', 'O-Low'):
        req[f'{name} vs c29'] = bridge(cap / name, s29 / name, every)
    req['AT-Ultra vs c28 final combination'] = bridge(cap / 'AT-Ultra', c28 / FINAL, every)
    req['AT-Ultra vs c29 final combination'] = bridge(cap / 'AT-Ultra', t29 / FINAL, every)
    for preset in ('High', 'Medium', 'Low'):
        req[f'AT-{preset} vs c30 baseline'] = bridge(cap / f'AT-{preset}', c30 / f'AT-{preset}', every)
    for preset, ref in PRESETS:
        req[f'ATOff-{preset} vs c29 {ref}'] = bridge(cap / f'ATOff-{preset}', s29 / ref, every)
    for run, middle, mref in (('Switch-T2xR-AT', 'AT-Reset90', None), ('Switch-T2xR-O1X', 'O-1X', 'O-1X')):
        req[f'{run} 0..89 vs T2xR-Ultra'] = bridge(cap / run, cap / 'T2xR-Ultra', range(0, 90))
        req[f'{run} 90..149 vs {middle}'] = bridge(cap / run, cap / middle, range(90, 150))
        if mref:
            req[f'{run} 90..149 vs c29 {mref}'] = bridge(cap / run, s29 / mref, range(90, 150))
        req[f'{run} 150..239 vs T2xR-Reset150'] = bridge(cap / run, cap / 'T2xR-Reset150', range(150, 240))
    info = {
        'T2xR-Reset150 0..149 not saved; AT-Reset90 vs AT-Ultra 90..149 (should differ: restarted history)': bridge(cap / 'AT-Reset90', cap / 'AT-Ultra', range(90, 150)),
        'T2xR-Reset150 150..239 vs T2xR-Ultra (should differ: restarted history)': bridge(cap / 'T2xR-Reset150', cap / 'T2xR-Ultra', range(150, 240)),
    }
    for preset in ('High', 'Medium', 'Low'):
        info[f'T2xR-{preset} vs T2xR-Ultra'] = bridge(cap / f'T2xR-{preset}', cap / 'T2xR-Ultra', every)
    info['T2xR-Ultra still frames 2..59 vs the frame two before'] = bridge(cap / 'T2xR-Ultra', cap / 'T2xR-Ultra', range(2, 60), range(0, 58))
    info['T2xR-Ultra still frames 1..59 vs the frame before'] = bridge(cap / 'T2xR-Ultra', cap / 'T2xR-Ultra', range(1, 60), range(0, 59))
    summary = {'required_checks_pass': all(c['pass_'] for c in req.values()), 'required': req, 'informative': info}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    for k, v in list(req.items()) + list(info.items()):
        print(f"{k}: {v['identical']}/{v['frames']} identical, crc {v['crc_ok']}, first different {v.get('first_different')}")
    print('required_checks_pass', summary['required_checks_pass'])


if __name__ == '__main__':
    main()
