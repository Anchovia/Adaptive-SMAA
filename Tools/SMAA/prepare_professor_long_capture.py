"""Prepare isolated presentation-only capture branches without renderer edits."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = {
    'audit': ('9e8461a', 'tooling/persistence-long-capture', 'EdgePersistenceCostAudit.inl'),
    '1': ('eb1d05a', 'tooling/aa-off-long-capture', 'StencilLifecycleVerification.inl'),
    '2': ('15fb796', 'tooling/smaa-1x-long-capture', 'StencilLifecycleVerification.inl'),
    '3': ('3274633', 'tooling/temporal-only-long-capture', 'StencilLifecycleVerification.inl'),
    '5': ('0b41914', 'tooling/edge-temporal-only-long-capture', 'StencilLifecycleVerification.inl'),
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    key = argparse.ArgumentParser()
    key.add_argument('case', choices=ITEMS)
    case = key.parse_args().case
    base, branch, name = ITEMS[case]
    assert not git('status', '--porcelain', '--untracked-files=no'), 'Tracked work must be clean'
    git('switch', '-c', branch, base)
    path = ROOT / 'Projects/CMAA2' / name
    text = path.read_text(encoding='utf-8')
    if case == 'audit':
        text = replace_once(text, 'm_capture?(m_shortCapture?6:240):m_measureFrames',
                             'm_capture?(m_shortCapture?6:480):m_measureFrames')
        text = replace_once(text, 'const bool diagnostic=m_capture&&c.diagnostics&&TraceFrame();',
                             'const bool diagnostic=m_capture&&m_shortCapture&&c.diagnostics&&TraceFrame();')
        text = replace_once(text, 'if(c.diagnostics&&TraceFrame()) {',
                             'if(m_shortCapture&&c.diagnostics&&TraceFrame()) {')
        text = text.replace('Capture: A/B/E/O 240 frames each.',
                             'Presentation long capture: A/B/E/O 480 frames each; final PNG only.')
    else:
        text = replace_once(text, 'm_capture?240:m_measureFrames', 'm_capture?480:m_measureFrames')
        lines = text.splitlines()
        assert sum('if(capture)m_modes.push_back' in line for line in lines) == 1
        text = '\n'.join(line for line in lines if 'if(capture)m_modes.push_back' not in line) + '\n'
        text = text.replace('Capture: target/control + target repeat; 240 frames each;',
                             'Presentation long capture: target/control; 480 frames each;')
    text = replace_once(text, 'm_frame%240', 'm_frame%(m_capture?480:240)')
    text = replace_once(text, 'vaMath::Clamp(phase-60,0,120)', 'vaMath::Clamp(phase-60,0,m_capture?360:120)')
    text = text.replace('still60/move120/still60;', 'capture still60/move360/still60; timing still60/move120/still60;')
    text = replace_once(text, 'tool.ReportStart();',
        'tool.ReportStart();\n            tool.ReportAddRowValues({"presentation_timeline",m_capture?"480":"240","60",m_capture?"360":"120","60","60fps"});')
    path.write_text(text, encoding='utf-8')
    changed = git('diff', '--name-only').splitlines()
    assert changed == ['Projects/CMAA2/' + name], changed
    doc = ROOT / 'Docs/Professor-Long-Capture'
    doc.mkdir(parents=True, exist_ok=True)
    record = dict(case=case, branch=branch, base=git('rev-parse', base),
                  changed_harness='Projects/CMAA2/' + name,
                  renderer_modified=False, frames=480, source_fps=60,
                  initial_still=60, moving=360, final_still=60,
                  motion='native flythrough time 2..8 at 1/60 per frame; first 180 frames match original 240-frame path',
                  modes='4/6/7/8' if case=='audit' else f'{case} plus independent native 4 control',
                  scope='presentation capture only; no new timing or CGVQM claim')
    (doc / 'method.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    git('diff', '--check')
    git('add', str(path.relative_to(ROOT)), str(doc.relative_to(ROOT)))
    git('commit', '-m', 'test(smaa): extend isolated presentation capture to eight seconds', '-m',
        'Preserve the renderer and shader equations. Capture 60 still, 360 moving and 60 still frames with unchanged camera speed; retain the native T2X-R control and the original 180-frame prefix for validation. Keep benchmark timing and preserved experiment branches unchanged.')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
