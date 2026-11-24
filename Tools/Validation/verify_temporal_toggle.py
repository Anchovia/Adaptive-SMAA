"""PNG identity checks for the Temporal checkbox of SMAA Adaptive + Temporal.

Identity is SHA-256 of the PNG file; every frame of the new capture must also pass the PNG chunk CRC check.
Required:
  SMAA 1X (O-1X, O-High, O-Medium, O-Low) against the SpatialCapture of tooling/adaptive-selected-cross5-minimal
      (c29): the original SMAA path is unchanged.
  Temporal On (AT-Ultra, AT-High, AT-Medium, AT-Low) against the baseline/improved-smaa-demo capture (c30), and
      AT-Ultra against the final combination (Adaptive + selected route + Cross5) of c29 and c28.
  Temporal Off (ATOff-Ultra ... ATOff-Low) against Adaptive SMAA 1X of the same preset in c29 (A-1X, A-High,
      A-Medium, A-Low).
  AT-Toggle (Off at frame 90, On at frame 150): frames 0..89 equal AT-Ultra, 90..149 equal ATOff-Ultra and c29 A-1X,
      150..239 equal AT-Reset150 (history restarted at 150 without switching). AT-Reset150 frames 0..149 equal
      AT-Ultra.
Informative: AT-Toggle frame 150 (the seed) against ATOff-Ultra, AT-Toggle 151..239 against ATOff-Ultra, and
  AT-Reset150 150..239 against AT-Ultra.

usage: python verify_temporal_toggle.py --capture <run> --c30 <run> --c29-temporal <run> --c29-spatial <run>
           --c28-temporal <run> --out <json>
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


def bridge(new, ref, frames):
    names = [f'frame_{i:05d}.png' for i in frames]
    missing = [n for n in names if not (new / n).is_file() or not (ref / n).is_file()]
    if missing:
        return dict(new=str(new), reference=str(ref), frames=len(names), missing=len(missing), identical=0, crc_ok=0, pass_=False)
    same = [n for n in names if sha(str(new / n)) == sha(str(ref / n))]
    good = sum(crc_ok(str(new / n)) for n in names)
    return dict(new=str(new), reference=str(ref), first=frames[0], last=frames[-1], frames=len(names), missing=0, identical=len(same),
                crc_ok=good, first_different=next((n for n in names if n not in same), None), pass_=len(same) == len(names) and good == len(names))


def main():
    ap = argparse.ArgumentParser()
    for k in ('capture', 'c30', 'c29-temporal', 'c29-spatial', 'c28-temporal', 'out'):
        ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    cap, c30, t29, s29, t28 = map(Path, (a.capture, a.c30, a.c29_temporal, a.c29_spatial, a.c28_temporal))
    every = range(240)
    req = {}
    for name in ('O-1X', 'O-High', 'O-Medium', 'O-Low'):
        req[f'{name} vs c29'] = bridge(cap / name, s29 / name, every)
    for preset, ref in PRESETS:
        req[f'AT-{preset} (On) vs c30 baseline'] = bridge(cap / f'AT-{preset}', c30 / f'AT-{preset}', every)
    req['AT-Ultra (On) vs c29 final combination'] = bridge(cap / 'AT-Ultra', t29 / FINAL, every)
    req['AT-Ultra (On) vs c28 final combination'] = bridge(cap / 'AT-Ultra', t28 / FINAL, every)
    for preset, ref in PRESETS:
        req[f'ATOff-{preset} vs c29 {ref}'] = bridge(cap / f'ATOff-{preset}', s29 / ref, every)
    req['AT-Toggle 0..89 vs AT-Ultra'] = bridge(cap / 'AT-Toggle', cap / 'AT-Ultra', range(0, 90))
    req['AT-Toggle 90..149 vs ATOff-Ultra'] = bridge(cap / 'AT-Toggle', cap / 'ATOff-Ultra', range(90, 150))
    req['AT-Toggle 90..149 vs c29 A-1X'] = bridge(cap / 'AT-Toggle', s29 / 'A-1X', range(90, 150))
    req['AT-Toggle 150..239 vs AT-Reset150'] = bridge(cap / 'AT-Toggle', cap / 'AT-Reset150', range(150, 240))
    req['AT-Reset150 0..149 vs AT-Ultra'] = bridge(cap / 'AT-Reset150', cap / 'AT-Ultra', range(0, 150))
    info = {
        'AT-Toggle 150 (seed) vs ATOff-Ultra': bridge(cap / 'AT-Toggle', cap / 'ATOff-Ultra', range(150, 151)),
        'AT-Toggle 151..239 vs ATOff-Ultra': bridge(cap / 'AT-Toggle', cap / 'ATOff-Ultra', range(151, 240)),
        'AT-Reset150 150..239 vs AT-Ultra': bridge(cap / 'AT-Reset150', cap / 'AT-Ultra', range(150, 240)),
    }
    summary = {'required_checks_pass': all(c['pass_'] for c in req.values()), 'required': req, 'informative': info}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    for k, v in list(req.items()) + list(info.items()):
        print(f"{k}: {v['identical']}/{v['frames']} identical, crc {v['crc_ok']}, first different {v.get('first_different')}")
    print('required_checks_pass', summary['required_checks_pass'])


if __name__ == '__main__':
    main()
