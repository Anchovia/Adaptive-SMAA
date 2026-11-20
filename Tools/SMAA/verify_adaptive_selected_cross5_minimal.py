"""PNG identity of tooling/adaptive-selected-cross5-minimal against the integration and minimal captures.

Every compared mode: frames 00000..00239, valid chunk CRCs in the new capture, and SHA-256 equal to the other
capture frame by frame.
  integration (c28 ac): O-1X, A-1X (from the SpatialCapture run), case 4, the selected route, + Cross5,
                        Adaptive + selected route, Adaptive + selected route + Cross5;
  minimal (c24-minimal): case 19, A-T2X-R and Adaptive case 19 (temporal), and O/A Low/Medium/High (1X).

usage: verify_adaptive_selected_cross5_minimal.py --scene bistro --capture <run> --spatial <run>
         --integration <c28 run> --minimal <minimal temporal run> --minimal-spatial <minimal 1X run> --out <json>
"""
import argparse, hashlib, json, struct, zlib
from pathlib import Path

SEL = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
X5 = '+HistoryVelocityPingPongCross5'
C19 = SEL + '+VelocityInEdge'


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


def bridge(a, b):
    frames = [f'frame_{i:05d}.png' for i in range(240)]
    present = all((a / f).is_file() for f in frames) and all((b / f).is_file() for f in frames)
    if not present:
        return dict(a=str(a), b=str(b), identical=0, crc_ok=0, pass_=False)
    same = sum(sha(a / f) == sha(b / f) for f in frames)
    good = sum(crc_ok(a / f) for f in frames)
    return dict(a=str(a), b=str(b), identical=same, crc_ok=good, pass_=same == 240 and good == 240)


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'capture', 'spatial', 'integration', 'minimal', 'minimal-spatial', 'out'):
        ap.add_argument('--' + k, required=True)
    x = ap.parse_args()
    cap, sp, it, mt, ms = map(Path, (x.capture, x.spatial, x.integration, x.minimal, x.minimal_spatial))
    pairs = {
        'O-1X vs integration': (sp / 'O-1X', it / 'O-1X'), 'A-1X vs integration': (sp / 'A-1X', it / 'A-1X'),
        'O-T2X-R vs integration': (cap / 'O-T2X-R', it / 'O-T2X-R'), 'selected vs integration': (cap / SEL, it / SEL),
        'selected+Cross5 vs integration': (cap / (SEL + X5), it / (SEL + X5)),
        'A-selected vs integration': (cap / ('A-' + SEL), it / ('A-' + SEL)),
        'A-selected+Cross5 vs integration': (cap / ('A-' + SEL + X5), it / ('A-' + SEL + X5)),
        'case19 vs minimal': (cap / C19, mt / C19), 'A-T2X-R vs minimal': (cap / 'A-T2X-R', mt / 'A-T2X-R'),
        'A-case19 vs minimal': (cap / ('A-' + C19), mt / ('A-' + C19)),
    }
    for p in ('Low', 'Medium', 'High'):
        for s in ('O', 'A'):
            pairs[f'{s}-{p} vs minimal'] = (sp / f'{s}-{p}', ms / f'{s}-{p}')
    res = dict(scene=x.scene, bridges={k: bridge(a, b) for k, (a, b) in pairs.items()})
    res['pass'] = all(b['pass_'] for b in res['bridges'].values())
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    for k, b in res['bridges'].items():
        print(f"{x.scene:9} {k:34} {b['identical']}/240 crc {b['crc_ok']}/240")
    print(x.scene, 'PASS' if res['pass'] else 'FAIL')


if __name__ == '__main__':
    main()
