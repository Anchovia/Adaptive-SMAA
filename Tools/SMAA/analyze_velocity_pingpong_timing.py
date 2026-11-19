"""Paired GPU timing of the velocity ping-pong modes: the history rejection timing analysis with this
branch's six temporal modes and case 19 as a third control.

usage: analyze_velocity_pingpong_timing.py --report bistro=<results.csv> --report minecraft=<results.csv> --out <json>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import analyze_selected_history_rejection_timing as t

SEL = t.SEL
C19 = SEL + '+VelocityInEdge'
t.MODES = [('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('velocity', SEL + '+HistoryVelocityWeight'),
           ('pingpong', SEL + '+HistoryVelocityPingPong'), ('case19', C19), ('case19-pingpong', C19 + '+HistoryVelocityPingPong')]
t.CONTROLS = [('vs_native', 'O-T2X-R'), ('vs_selected', SEL), ('vs_velocity', SEL + '+HistoryVelocityWeight'), ('vs_case19', C19)]

if __name__ == '__main__':
    t.main()
