"""PNG identity of baseline/improved-smaa-demo captures against the research captures.

Every compared frame must pass the PNG chunk CRC check in the new capture; identity is SHA-256 of the PNG file.
  SMAA 1X (existing option): O-1X, O-High, O-Medium, O-Low, frames 0..239, against the SpatialCapture of
      tooling/adaptive-selected-cross5-minimal (c29), which also matched the integration branch (c28).
  SMAA Adaptive + Temporal at Ultra (AT-Ultra), frames 0..239, against the final combination
      (Adaptive + selected route + Cross5) of c29 and c28.
  SMAA Adaptive + Temporal at High/Medium/Low have no temporal reference. In the still frames 0..59 the
      camera does not move, so the expected output is Adaptive SMAA 1X of the same preset (c29 A-High/
      A-Medium/A-Low); the moving frames are reported as differing or not from that 1X capture.

usage: python verify_improved_smaa_demo.py --capture <run> --c29-temporal <run> --c29-spatial <run>
           --c28-temporal <run> --out <json>
"""
import argparse, hashlib, json, struct, zlib
from pathlib import Path

FINAL = 'A-ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha+HistoryVelocityPingPongCross5'


def crc_ok(p):
    data = p.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return False
    pos = 8
    while pos + 12 <= len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        if pos + 12 + n > len(data) or zlib.crc32(data[pos + 4:pos + 8 + n]) & 0xffffffff != struct.unpack('>I', data[pos + 8 + n:pos + 12 + n])[0]:
            return False
        pos += 12 + n
    return pos == len(data)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def bridge(new, ref, frames):
    names = [f'frame_{i:05d}.png' for i in frames]
    missing = [n for n in names if not (new / n).is_file() or not (ref / n).is_file()]
    if missing:
        return dict(new=str(new), reference=str(ref), frames=len(names), missing=len(missing), identical=0, crc_ok=0, pass_=False)
    same = [n for n in names if sha(new / n) == sha(ref / n)]
    good = sum(crc_ok(new / n) for n in names)
    return dict(new=str(new), reference=str(ref), frames=len(names), missing=0, identical=len(same), crc_ok=good,
                first_different=next((n for n in names if n not in same), None), pass_=len(same) == len(names) and good == len(names))


def main():
    ap = argparse.ArgumentParser()
    for k in ('capture', 'c29-temporal', 'c29-spatial', 'c28-temporal', 'out'):
        ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    cap, t29, s29, t28 = map(Path, (a.capture, a.c29_temporal, a.c29_spatial, a.c28_temporal))
    all_frames, still, moving = range(240), range(60), range(60, 240)
    checks = {}
    for name in ('O-1X', 'O-High', 'O-Medium', 'O-Low'):
        checks[f'{name} vs c29'] = bridge(cap / name, s29 / name, all_frames)
    checks['AT-Ultra vs c29 final combination'] = bridge(cap / 'AT-Ultra', t29 / FINAL, all_frames)
    checks['AT-Ultra vs c28 final combination'] = bridge(cap / 'AT-Ultra', t28 / FINAL, all_frames)
    info = {}
    for preset, ref in (('Ultra', 'A-1X'), ('High', 'A-High'), ('Medium', 'A-Medium'), ('Low', 'A-Low')):
        info[f'AT-{preset} still frames vs c29 {ref}'] = bridge(cap / f'AT-{preset}', s29 / ref, still)
        info[f'AT-{preset} moving frames vs c29 {ref}'] = bridge(cap / f'AT-{preset}', s29 / ref, moving)
    summary = {'required_checks_pass': all(c['pass_'] for c in checks.values()), 'required': checks, 'informative': info}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    for k, v in list(checks.items()) + list(info.items()):
        print(f"{k}: {v['identical']}/{v['frames']} identical, crc {v['crc_ok']}, first different {v.get('first_different')}")
    print('required_checks_pass', summary['required_checks_pass'])


if __name__ == '__main__':
    main()
