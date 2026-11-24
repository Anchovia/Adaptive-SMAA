"""Markdown tables from the summary.json files of analyze_translation_stability.py.

usage: python translation_tables.py --analysis <dir with one sub-folder per run> --out <md>
"""
import argparse, json
from pathlib import Path

RUNS = [('minecraft35_h', 'Minecraft 3.5 수평'), ('minecraft35_v', 'Minecraft 3.5 수직'), ('minecraft35_y', 'Minecraft 3.5 yaw'),
        ('minecraft_h', 'Minecraft 2.0 수평'), ('minecraft_v', 'Minecraft 2.0 수직'), ('minecraft_y', 'Minecraft 2.0 yaw'),
        ('bistro_h', 'Bistro 수평'), ('bistro_v', 'Bistro 수직'), ('bistro_y', 'Bistro yaw')]
CONDS = ('fixed60', 'fixed300', 'fixedmean', 'recorded')


def pct(on, off):
    return f'{100 * (on / off - 1):+.1f}%'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    base = Path(a.analysis)
    lines = ['# 평행 이동 안정성 결과 표 (생성 파일)', '', 'tde60은 1/60초 떨어진 두 프레임의 변화 중 SSRef에 없는 변화(RGB 0~255 평균), 낮을수록 안정적이다. '
             '선택 화소는 그 프레임 WeightDebug의 G=255 화소, 깊이 경계는 4-이웃 상대 깊이 차 10% 이상, 질감 경계는 나머지 선택 화소다. '
             '조건마다 저장한 구간이 달라(fixed60은 0.5초 전체, 나머지는 마지막 0.1초) 조건 사이 절대값은 비교하지 않는다.', '']
    lines += ['## On과 Off의 tde60', '', '| 실행 | 조건 | 선택 Off | 선택 On | On/Off | 깊이 경계 On/Off | 질감 경계 On/Off | Fixed08/Off(선택) | Official1Tap/Off(선택) |', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    wl = ['## Cross5 가중치', '', '| 실행 | 조건 | 깊이 경계 w<0.4 | 깊이 경계 평균 w | 질감 경계 w<0.4 | 질감 경계 평균 w |', '|---|---|---:|---:|---:|---:|']
    for key, label in RUNS:
        p = base / key / 'summary.json'
        if not p.is_file():
            continue
        s = json.loads(p.read_text(encoding='utf-8'))
        for c in CONDS:
            if c not in s:
                continue
            m = s[c]['modes']
            g = lambda mode, k: m[mode][k]['tde60']
            lines.append(f"| {label} | {c} | {g('Off', 'selected'):.3f} | {g('On', 'selected'):.3f} | {pct(g('On', 'selected'), g('Off', 'selected'))} | "
                         f"{pct(g('On', 'depth_edge'), g('Off', 'depth_edge'))} | {pct(g('On', 'texture_edge'), g('Off', 'texture_edge'))} | "
                         f"{pct(g('Fixed08', 'selected'), g('Off', 'selected'))} | {pct(g('Official1Tap', 'selected'), g('Off', 'selected'))} |")
            w = s[c]['weights']
            wl.append(f"| {label} | {c} | {100 * w['depth_edge']['share_w_lt_0_4']:.1f}% | {w['depth_edge']['mean_weight']:.3f} | "
                      f"{100 * w['texture_edge']['share_w_lt_0_4']:.1f}% | {w['texture_edge']['mean_weight']:.3f} |")
    Path(a.out).write_text('\n'.join(lines + [''] + wl) + '\n', encoding='utf-8')
    print('\n'.join(lines + [''] + wl))


if __name__ == '__main__':
    main()
