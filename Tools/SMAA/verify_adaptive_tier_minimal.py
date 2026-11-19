"""PNG identity of tooling/adaptive-tier-minimal against the research and base captures.

Every pair must hold frames 00000..00239 on both sides. A frame passes when the PNG files are
byte-identical. Otherwise every chunk CRC of both files is checked (a file whose CRC fails was damaged
after encoding and cannot show a rendering difference) and, when both files are intact, the decoded RGB
is compared. Any differing frame fails the pair.

  spatial  (SMAA 1X, same preset): A-1X/High/Medium/Low against the research A-U/H/M/L-T3-1p-E4
           (1% tiers, tier in an RGBA8 edge target), O-* against the research O-*;
  adaptive (temporal, Ultra): the three A- routes against the research +Tier1pRGBA8 modes;
  original (temporal, Ultra): the three Original routes against the base executable's capture,
           and also against the research capture's Original routes.

usage: verify_adaptive_tier_minimal.py --scene bistro --minimal <capture run dir> --minimal-spatial <run dir>
         --base <run dir> --research <run dir> --research-spatial <run dir> --out <json>
"""
import argparse, hashlib, json, struct, zlib
from pathlib import Path
import numpy as np
from PIL import Image

SEL = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
ROUTES = ['O-T2X-R', SEL, SEL + '+VelocityInEdge']
ADAPTIVE = [('A-T2X-R', 'A-T2X-R+Tier1pRGBA8'), ('A-' + SEL, 'A-' + SEL + '+Tier1pRGBA8'),
            ('A-' + SEL + '+VelocityInEdge', 'A-' + SEL + '+VelocityInEdge+Tier1pRGBA8')]
SPATIAL = [('A-1X', 'A-U-T3-1p-E4'), ('A-High', 'A-H-T3-1p-E4'), ('A-Medium', 'A-M-T3-1p-E4'), ('A-Low', 'A-L-T3-1p-E4'),
           ('O-1X', 'O-1X'), ('O-High', 'O-High'), ('O-Medium', 'O-Medium'), ('O-Low', 'O-Low')]
FRAMES = 240


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def crc_ok(p):
    """True when the PNG signature and every chunk CRC are valid."""
    data = p.read_bytes()
    if data[:8] != bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]):
        return False
    pos = 8
    while pos + 12 <= len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        body = data[pos + 4:pos + 8 + n]
        if pos + 12 + n > len(data) or zlib.crc32(body) & 0xffffffff != struct.unpack('>I', data[pos + 8 + n:pos + 12 + n])[0]:
            return False
        pos += 12 + n
    return pos == len(data)


def compare(group, a_dir, a_mode, b_dir, b_mode):
    a, b = Path(a_dir) / a_mode, Path(b_dir) / b_mode
    names = [f'frame_{i:05d}.png' for i in range(FRAMES)]
    missing = [n for n in names if not (a / n).is_file() or not (b / n).is_file()]
    extra = sorted(set(p.name for p in a.glob('frame_*.png')) ^ set(names)) + sorted(set(p.name for p in b.glob('frame_*.png')) ^ set(names))
    byte_same = rgb_same = 0
    differing = []
    for n in names:
        if n in missing:
            continue
        if sha(a / n) == sha(b / n):
            byte_same += 1; rgb_same += 1
            continue
        ok_a, ok_b = crc_ok(a / n), crc_ok(b / n)
        if not (ok_a and ok_b):
            differing.append(dict(frame=n, minimal_crc_ok=ok_a, reference_crc_ok=ok_b, rgb_identical=None))
            continue
        x = np.asarray(Image.open(a / n).convert('RGB')); y = np.asarray(Image.open(b / n).convert('RGB'))
        same = x.shape == y.shape and np.array_equal(x, y)
        rgb_same += same
        differing.append(dict(frame=n, minimal_crc_ok=True, reference_crc_ok=True, rgb_identical=bool(same),
                              changed_pixels=None if x.shape != y.shape else int((x != y).any(axis=2).sum())))
    row = dict(group=group, minimal=a_mode, reference=b_mode, reference_dir=str(b_dir), frames=FRAMES,
               missing=len(missing), extra=len(extra), byte_identical=byte_same, rgb_identical=rgb_same,
               damaged_files=sum(1 for d in differing if d['rgb_identical'] is None),
               differing=differing[:20], pass_=not missing and not extra and byte_same == FRAMES)
    print(f"{group:9} {a_mode[:60]:60} bytes {byte_same}/{FRAMES} rgb {rgb_same}/{FRAMES} damaged {row['damaged_files']} "
          f"{'PASS' if row['pass_'] else 'FAIL'}", flush=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'minimal', 'minimal-spatial', 'base', 'research', 'research-spatial', 'out'):
        ap.add_argument('--' + k, required=True)
    x = ap.parse_args()
    rows = [compare('spatial', x.minimal_spatial, m, x.research_spatial, r) for m, r in SPATIAL]
    rows += [compare('adaptive', x.minimal, m, x.research, r) for m, r in ADAPTIVE]
    rows += [compare('original', x.minimal, m, x.base, m) for m in ROUTES]
    rows += [compare('original', x.minimal, m, x.research, m) for m in ROUTES]
    res = dict(scene=x.scene, minimal=x.minimal, minimal_spatial=x.minimal_spatial, base=x.base, research=x.research,
               research_spatial=x.research_spatial, all_pass=all(r['pass_'] for r in rows), pairs=rows)
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(x.scene, 'ALL PASS' if res['all_pass'] else 'FAIL')


if __name__ == '__main__':
    main()
