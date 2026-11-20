"""Paired GPU timing of the Adaptive + selected route + (c') Cross5 modes: the history rejection timing
analysis with this branch's five temporal modes. Every mode is paired per repeat against native case 4,
the selected route, selected + Cross5 and Adaptive + selected route of the same process, so the table
holds the Adaptive effect on the same route (A-selected vs selected, A-cross5 vs cross5) and the Cross5
effect on the same spatial SMAA (cross5 vs selected, A-cross5 vs A-selected).

usage: analyze_adaptive_selected_cross5_timing.py --report bistro=<results.csv> --report minecraft=<results.csv> --out <json>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import analyze_selected_history_rejection_timing as t

SEL = t.SEL
X5 = '+HistoryVelocityPingPongCross5'
t.MODES = [('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('cross5', SEL + X5), ('A-selected', 'A-' + SEL), ('A-cross5', 'A-' + SEL + X5)]
t.CONTROLS = [('vs_native', 'O-T2X-R'), ('vs_selected', SEL), ('vs_cross5', SEL + X5), ('vs_A_selected', 'A-' + SEL)]

if __name__ == '__main__':
    t.main()
