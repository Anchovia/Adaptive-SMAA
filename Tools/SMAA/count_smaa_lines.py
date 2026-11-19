"""Line counts of Projects/CMAA2/SMAA between two commits (rule of Docs/Adaptive-Selected-Temporal).

Only .cpp .h .inl .hlsl .hlsli files count. Whitespace and blank-line changes are ignored
(git diff -w --ignore-blank-lines). "Code" counts the added lines that hold code in the new file:
blank lines, // comments and /* */ block comments are left out (a line with code and a trailing
comment is code).

usage: count_smaa_lines.py <from> <to> [<from> <to> ...] [--json out.json]
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTS = ('.cpp', '.h', '.inl', '.hlsl', '.hlsli')
SHADER = ('.hlsl', '.hlsli')


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), '-c', 'gc.auto=0', *args], capture_output=True, check=True,
                          text=True, encoding='utf-8', errors='replace').stdout


def code_lines(text):
    """Set of 1-based line numbers that hold code, with // and /* */ comments removed."""
    code, block = set(), False
    for no, line in enumerate(text.splitlines(), 1):
        i, has = 0, False
        while i < len(line):
            if block:
                j = line.find('*/', i)
                if j < 0:
                    i = len(line)
                else:
                    block, i = False, j + 2
                continue
            if line.startswith('//', i):
                break
            if line.startswith('/*', i):
                block, i = True, i + 2
                continue
            if line[i] == '"':                       # skip string literals
                j = i + 1
                while j < len(line) and line[j] != '"':
                    j += 2 if line[j] == '\\' else 1
                has, i = True, j + 1
                continue
            if not line[i].isspace():
                has = True
            i += 1
        if has:
            code.add(no)
    return code


def count(a, b):
    files = [f for f in git('diff', '--name-only', a, b, '--', 'Projects/CMAA2/SMAA').split() if f.endswith(EXTS)]
    rows = []
    for f in files:
        diff = git('diff', '-w', '--ignore-blank-lines', '-U0', a, b, '--', f)
        added, deleted, new_lines = 0, 0, []
        new_no = 0
        for line in diff.splitlines():
            m = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
            if m:
                new_no = int(m.group(1))
                continue
            if line.startswith('+++') or line.startswith('---'):
                continue
            if line.startswith('+'):
                added += 1; new_lines.append(new_no); new_no += 1
            elif line.startswith('-'):
                deleted += 1
        try:
            text = git('show', f'{b}:{f}')
        except subprocess.CalledProcessError:
            text = ''
        cl = code_lines(text)
        rows.append(dict(file=f[len('Projects/CMAA2/SMAA/'):], kind='shader' if f.endswith(SHADER) else 'cpp',
                         added=added, deleted=deleted, code=sum(1 for n in new_lines if n in cl)))
    tot = lambda rs, k: sum(r[k] for r in rs)
    summary = dict(added=tot(rows, 'added'), deleted=tot(rows, 'deleted'), code=tot(rows, 'code'))
    for kind in ('shader', 'cpp'):
        rs = [r for r in rows if r['kind'] == kind]
        summary[kind] = dict(added=tot(rs, 'added'), deleted=tot(rs, 'deleted'), code=tot(rs, 'code'))
    return dict(base=a, head=b, files=rows, **summary)


if __name__ == '__main__':
    args, out = sys.argv[1:], None
    if '--json' in args:
        k = args.index('--json'); out = args[k + 1]; del args[k:k + 2]
    res = [count(args[i], args[i + 1]) for i in range(0, len(args), 2)]
    for r in res:
        print(f"{r['base']}..{r['head']}: +{r['added']}/-{r['deleted']} code {r['code']}  "
              f"(shader +{r['shader']['added']}/-{r['shader']['deleted']} code {r['shader']['code']}, "
              f"C++ +{r['cpp']['added']}/-{r['cpp']['deleted']} code {r['cpp']['code']})")
        for f in r['files']:
            print(f"    {f['file']:28} {f['kind']:6} +{f['added']:4} -{f['deleted']:4} code {f['code']:4}")
    if out:
        Path(out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
