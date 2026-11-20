"""Assemble the ReShade Original/Adaptive SMAA test bundle.

The third-party files are taken from hash-pinned local copies (ReShade 6.8.0 installer payload extracted
without running the installer, crosire/reshade-shaders slim fd00221, CeeJayDK/SweetFX 93ddf39) and are
never stored in Git. The bundle layout is:

  <out>/README-ko.txt
  <out>/MANIFEST-sha256.txt
  <out>/game-folder/...        everything here goes next to the game's .exe
  <out>/other-games/ReShade32.dll
  <out>/licenses/...

usage: python -I make_reshade_bundle.py --reshade <dir> --reshade-shaders <dir> --sweetfx <dir> --out <dir> [--replace]
"""
import argparse
import hashlib
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

PINNED = {
    'reshade': {
        'ReShade64.dll': 'b2945c29e7095491a901746b400e58db9b1592ab092bacf2a888ce37f02d08da',
        'ReShade32.dll': '538998f66c0197adcdeadfe8e5ea19dd6ca3253e40399476d291f385ce518b88',
    },
    'reshade_shaders': {
        'Shaders/ReShade.fxh': '6dabfbbaf968c3871905d2ea17f96572ff7b1cec01310b5d0e5252b66b30174f',
        'Shaders/ReShadeUI.fxh': '78adf672df47460297eb9fe6dd238d2aafa24510b52b84feb1a745dff70eb901',
    },
    'sweetfx': {
        'Shaders/SweetFX/SMAA.fx': 'fd6591eeb70ff584ac4d774ed3c79af5efac34f5de1a36f8f873e959259c0007',
        'Shaders/SweetFX/SMAA.fxh': 'ee18b0f376585338cdb477a0900757cebac86d3c476ef99955348b55818c8310',
        'Textures/SweetFX/AreaTex.png': '0044e6b420a8d98a9dc6a60bedbd43f75cd15ac6052fdedfb2f2f55d3077beed',
        'Textures/SweetFX/SearchTex.png': '55a97853ab64174245701accf315ab63d41776c9cb2aa14c675e653684fd96f3',
        'LICENSE': '9b2e0b3ff53493f211e39390947716cd16ee559303dac0713ad4b12228dbce51',
    },
}

# (source group, relative source path, bundle path)
LAYOUT = [
    ('reshade', 'ReShade64.dll', 'game-folder/dxgi.dll'),
    ('reshade', 'ReShade32.dll', 'other-games/ReShade32.dll'),
    ('repo', 'Config/ReShade.ini', 'game-folder/ReShade.ini'),
    ('repo', 'Config/Presets/Original-SMAA-Ultra.ini', 'game-folder/ReShade-AdaptiveSMAA-Presets/Original-SMAA-Ultra.ini'),
    ('repo', 'Config/Presets/Adaptive-SMAA-Ultra.ini', 'game-folder/ReShade-AdaptiveSMAA-Presets/Adaptive-SMAA-Ultra.ini'),
    ('reshade_shaders', 'Shaders/ReShade.fxh', 'game-folder/reshade-shaders/Shaders/ReShade.fxh'),
    ('reshade_shaders', 'Shaders/ReShadeUI.fxh', 'game-folder/reshade-shaders/Shaders/ReShadeUI.fxh'),
    ('sweetfx', 'Shaders/SweetFX/SMAA.fx', 'game-folder/reshade-shaders/Shaders/SweetFX/SMAA.fx'),
    ('sweetfx', 'Shaders/SweetFX/SMAA.fxh', 'game-folder/reshade-shaders/Shaders/SweetFX/SMAA.fxh'),
    ('repo', 'Shaders/AdaptiveSMAA.fx', 'game-folder/reshade-shaders/Shaders/AdaptiveSMAA/AdaptiveSMAA.fx'),
    ('repo', 'Shaders/AdaptiveSMAA.fxh', 'game-folder/reshade-shaders/Shaders/AdaptiveSMAA/AdaptiveSMAA.fxh'),
    ('sweetfx', 'Textures/SweetFX/AreaTex.png', 'game-folder/reshade-shaders/Textures/SweetFX/AreaTex.png'),
    ('sweetfx', 'Textures/SweetFX/SearchTex.png', 'game-folder/reshade-shaders/Textures/SweetFX/SearchTex.png'),
    ('sweetfx', 'LICENSE', 'licenses/SweetFX-LICENSE.txt'),
    ('repo', 'README-ko.txt', 'README-ko.txt'),
    ('repo', 'THIRD-PARTY-ko.txt', 'licenses/THIRD-PARTY-ko.txt'),
]
CRLF_SUFFIXES = {'.ini', '.txt'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reshade', type=Path, required=True)
    parser.add_argument('--reshade-shaders', type=Path, required=True)
    parser.add_argument('--sweetfx', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    roots = {'reshade': args.reshade, 'reshade_shaders': args.reshade_shaders, 'sweetfx': args.sweetfx, 'repo': HERE}

    files = {}
    for group, rel, dest in LAYOUT:
        data = (roots[group] / rel).read_bytes()
        if group != 'repo' and sha256(data) != PINNED[group][rel]:
            raise SystemExit(f'{group}/{rel}: SHA-256 {sha256(data)} does not match the pinned value')
        if Path(dest).suffix.lower() in CRLF_SUFFIXES and group == 'repo':
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        files[dest] = data

    out = args.out
    if out.exists():
        if not args.replace:
            raise SystemExit(f'{out} exists; pass --replace to rebuild it')
        if not (out / 'MANIFEST-sha256.txt').is_file():
            raise SystemExit(f'{out} does not look like a bundle built by this script; not removing it')
        shutil.rmtree(out)
    for dest, data in files.items():
        path = out / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    lines = [f'{sha256(data)}  {len(data):>9}  {dest}' for dest, data in sorted(files.items())]
    (out / 'MANIFEST-sha256.txt').write_bytes(('\r\n'.join(lines) + '\r\n').encode('utf-8'))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
