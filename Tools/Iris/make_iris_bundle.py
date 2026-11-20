"""Assemble the Iris shader pack bundle for the user.

  <out>/AdaptiveSMAA-Iris.zip   the pack (shaders/ at the zip root), put into Minecraft's shaderpacks folder
  <out>/README-ko.txt           install, modes, screenshots, removal (Fabric and Iris come from their sites)
  <out>/MANIFEST-sha256.txt     hashes of the bundle files and of every file inside the zip

The pack is Tools/Iris/AdaptiveSMAA-Iris plus the files make_iris_assets.py derives from the repository
(lib/SMAA.glsl, AreaTex/SearchTex PNGs and .mcmeta) and the SMAA licence. The zip has fixed timestamps
and sorted entries, so the same sources give the same bytes.

usage: python make_iris_bundle.py <repo root> <out dir> [--replace]
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXT_SUFFIXES = {'.fsh', '.vsh', '.glsl', '.properties', '.lang', '.txt', '.mcmeta'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    repo, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    if out.exists():
        if '--replace' not in sys.argv:
            raise SystemExit(f'{out} exists; pass --replace to rebuild it')
        if not (out / 'MANIFEST-sha256.txt').is_file():
            raise SystemExit(f'{out} does not look like a bundle built by this script; not removing it')
        shutil.rmtree(out)
    with tempfile.TemporaryDirectory() as tmp:
        pack = Path(tmp) / 'AdaptiveSMAA-Iris'
        shutil.copytree(HERE / 'AdaptiveSMAA-Iris', pack)
        subprocess.run([sys.executable, str(HERE / 'make_iris_assets.py'), str(repo), str(pack)], check=True, capture_output=True)
        shutil.copy(repo / 'Projects/CMAA2/SMAA/LICENSE.txt', pack / 'shaders' / 'LICENSE-SMAA.txt')
        entries = sorted(p for p in pack.rglob('*') if p.is_file())
        out.mkdir(parents=True)
        zip_path = out / 'AdaptiveSMAA-Iris.zip'
        manifest = []
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for path in entries:
                rel = path.relative_to(pack).as_posix()
                data = path.read_bytes()
                # core.autocrlf checkouts have CRLF text; the pack always ships LF.
                if path.suffix in TEXT_SUFFIXES:
                    data = data.replace(b'\r\n', b'\n')
                info = zipfile.ZipInfo(rel, date_time=(2026, 11, 21, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, data)
                manifest.append(f'{sha256(data)}  {len(data):>9}  AdaptiveSMAA-Iris.zip:{rel}')
    readme = (HERE / 'README-ko.txt').read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    (out / 'README-ko.txt').write_bytes(readme)
    for name in ('AdaptiveSMAA-Iris.zip', 'README-ko.txt'):
        data = (out / name).read_bytes()
        manifest.insert(0, f'{sha256(data)}  {len(data):>9}  {name}')
    (out / 'MANIFEST-sha256.txt').write_bytes(('\r\n'.join(manifest) + '\r\n').encode('utf-8'))
    print('\n'.join(manifest))


if __name__ == '__main__':
    main()
