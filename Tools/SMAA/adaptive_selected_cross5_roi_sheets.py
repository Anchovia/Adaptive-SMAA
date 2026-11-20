"""ROI numbers and nearest sheets of the Adaptive + selected route + (c') Cross5 capture, reusing the history
rejection tools. Sheet columns: O-1X, A-1X, O-T2X-R, selected, selected + Cross5, Adaptive + selected,
Adaptive + selected + Cross5, SS-Reference. The ghost map shows the four selected-route columns.

usage: adaptive_selected_cross5_roi_sheets.py roi --scene bistro --run <run> --reference <SS-Reference> --out <json>
       adaptive_selected_cross5_roi_sheets.py sheets --scene bistro --run <run> --reference <SS-Reference> --out <dir> [sheet tool options]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import selected_history_rejection_roi as roi
import selected_history_rejection_sheets as sheets

SEL = roi.SEL
X5 = '+HistoryVelocityPingPongCross5'
roi.MODES = [('O-1X', 'O-1X'), ('A-1X', 'A-1X'), ('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('cross5', SEL + X5),
             ('A-selected', 'A-' + SEL), ('A-cross5', 'A-' + SEL + X5)]
roi.ROIS['minecraft']['left-line-late'] = ((0, 96, 96, 144), range(120, 129))
sheets.COLS = [('O-1X', 'O-1X'), ('A-1X', 'A-1X'), ('O-T2X-R', 'O-T2X-R'), ('선택 경로', SEL), ("+(c') Cross5", SEL + X5),
               ('A+선택 경로', 'A-' + SEL), ("A+선택 경로+Cross5", 'A-' + SEL + X5), ('SS-Reference', None)]
GHOST_COLS = sheets.COLS[3:7]
MOVE, TRANS, SETTLED = range(120, 126), range(178, 184), range(230, 236)
sheets.DEFAULT = {
    'bistro': [('window-band', (946, 466, 1074, 554), 4, [MOVE, TRANS, SETTLED]),
               ('chair-legs', (1230, 582, 1358, 670), 4, [MOVE, range(150, 156), TRANS, SETTLED])],
    'minecraft': [('foliage', (7, 718, 135, 806), 4, [range(85, 91), TRANS, SETTLED]),
                  ('left-line', (0, 96, 96, 144), 6, [range(117, 123), range(121, 127), TRANS, SETTLED]),
                  ('seam', (956, 524, 1020, 620), 4, [range(126, 132), range(150, 156), TRANS, SETTLED])],
}

if __name__ == '__main__':
    what = sys.argv.pop(1)
    if what == 'roi':
        roi.main()
    else:
        _ghost = sheets.ghost_map

        def ghost_map(*args, **kw):
            full = sheets.COLS
            sheets.COLS = full[:2] + GHOST_COLS
            try:
                _ghost(*args, **kw)
            finally:
                sheets.COLS = full
        sheets.ghost_map = ghost_map
        sheets.main()
