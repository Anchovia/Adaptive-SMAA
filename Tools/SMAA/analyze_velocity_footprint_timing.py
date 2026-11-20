"""Paired GPU timing of the velocity footprint modes: the history rejection timing analysis with this
branch's ten temporal modes. Every mode is paired per repeat against native case 4, the selected route,
selected + (c), selected + (c') and case 19 of the same process. "outside" is SMAA minus the camera
velocity, spatial and resolve scopes (for case 19 + ping-pong modes it holds the sentinel clear).

usage: analyze_velocity_footprint_timing.py --report bistro=<results.csv> --report minecraft=<results.csv> --out <json>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import analyze_selected_history_rejection_timing as t

SEL = t.SEL
C19 = SEL + '+VelocityInEdge'
PP, X5, F12 = '+HistoryVelocityPingPong', '+HistoryVelocityPingPongCross5', '+HistoryVelocityPingPongFootprint12'
t.MODES = [('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('velocity', SEL + '+HistoryVelocityWeight'), ('pingpong', SEL + PP),
           ('cross5', SEL + X5), ('footprint12', SEL + F12), ('case19', C19), ('case19-pingpong', C19 + PP),
           ('case19-cross5', C19 + X5), ('case19-footprint12', C19 + F12)]
t.CONTROLS = [('vs_native', 'O-T2X-R'), ('vs_selected', SEL), ('vs_velocity', SEL + '+HistoryVelocityWeight'),
              ('vs_pingpong', SEL + PP), ('vs_case19', C19)]

if __name__ == '__main__':
    t.main()
