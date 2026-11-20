"""Expand the Iris shader pack sources the way Iris prepares them for compilation (minimal subset).

- `#include "/x"` resolves from the pack's shaders/ folder, `#include "x"` from the including file.
- Option defaults in lib/settings.glsl are replaced by the requested values, as Iris rewrites them when
  the user changes shader settings (`#define AA_MODE 6` -> value, `//#define TIERS_AT_MAX` -> enabled).
Iris additionally runs its own preprocessor and source transformer; this script only gives the GLSL
compilers the same program text.

usage (module): expand(shaders_dir, program_file, {'AA_MODE': 6, 'DEBUG_VIEW': 0, 'TIERS_AT_MAX': False})
"""
import re
from pathlib import Path

PROGRAMS = ['composite', 'composite1', 'composite2', 'composite3', 'composite4', 'final']
INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"\s*$')


def apply_options(text, options):
    for name, value in options.items():
        if isinstance(value, bool):
            pattern = re.compile(r'^(\s*)(//\s*)?#define\s+' + name + r'\b.*$', re.M)
            if len(pattern.findall(text)) != 1:
                raise ValueError(f'option {name} not found once')
            text = pattern.sub(lambda m: m.group(1) + ('' if value else '//') + '#define ' + name, text)
        else:
            pattern = re.compile(r'^(\s*#define\s+' + name + r'\s+)(\S+)(.*)$', re.M)
            if len(pattern.findall(text)) != 1:
                raise ValueError(f'option {name} not found once')
            text = pattern.sub(lambda m: m.group(1) + str(value) + m.group(3), text)
    return text


def expand(shaders_dir, path, options, seen=None):
    shaders_dir = Path(shaders_dir)
    path = Path(path)
    seen = [] if seen is None else seen
    if path in seen:
        raise ValueError(f'include cycle at {path}')
    text = path.read_text(encoding='ascii')
    if path.name == 'settings.glsl':
        text = apply_options(text, options)
    out = []
    for line in text.split('\n'):
        m = INCLUDE.match(line)
        if m:
            target = m.group(1)
            resolved = shaders_dir / target.lstrip('/') if target.startswith('/') else path.parent / target
            out.append(expand(shaders_dir, resolved, options, seen + [path]).rstrip('\n'))
        else:
            out.append(line)
    return '\n'.join(out) + '\n'


def variants():
    for mode in range(7):
        for debug in range(5):
            for tiers in (False, True):
                yield {'AA_MODE': mode, 'DEBUG_VIEW': debug, 'TIERS_AT_MAX': tiers}
