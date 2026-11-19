"""ROI numbers and nearest sheets of the velocity ping-pong capture, reusing the history rejection tools.

usage: velocity_pingpong_roi_sheets.py roi --scene bistro --run <run> --reference <SS-Reference> --out <json>
       velocity_pingpong_roi_sheets.py sheets --scene bistro --run <run> --reference <SS-Reference> --out <dir> [sheet tool options]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import selected_history_rejection_roi as roi
import selected_history_rejection_sheets as sheets

SEL = roi.SEL
C19 = SEL + '+VelocityInEdge'
roi.MODES = [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('velocity', SEL + '+HistoryVelocityWeight'),
             ('pingpong', SEL + '+HistoryVelocityPingPong'), ('case19', C19), ('case19-pingpong', C19 + '+HistoryVelocityPingPong'),
             ('case19-pingpong-keep', C19 + '+HistoryVelocityPingPongKeepUnknown')]
sheets.COLS = [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('선택 경로', SEL), ('+(c) alpha', SEL + '+HistoryVelocityWeight'),
               ("+(c') ping-pong", SEL + '+HistoryVelocityPingPong'), ('19번', C19), ("19번+(c')", C19 + '+HistoryVelocityPingPong'),
               ('SS-Reference', None)]
# The ghost map shows the four filtered/unfiltered selected-route columns of COLS[2:6]; here: selected,
# (c), (c'), 19+(c') replaces 19 so the map compares the filters.
GHOST_COLS = [sheets.COLS[2], sheets.COLS[3], sheets.COLS[4], sheets.COLS[6]]
sheets.DEFAULT = {
    'bistro': [('window-band', (946, 466, 1074, 554), 4, [range(120, 126), range(178, 184), range(230, 236)]),
               ('chair-legs', (1230, 582, 1358, 670), 4, [range(120, 126), range(178, 184), range(230, 236)])],
    'minecraft': [('foliage', (7, 718, 135, 806), 4, [range(85, 91), range(178, 184), range(230, 236)]),
                  ('left-line', (0, 96, 96, 144), 6, [range(116, 122), range(120, 126), range(178, 184), range(230, 236)]),
                  ('seam', (956, 524, 1020, 620), 4, [range(126, 132), range(178, 184), range(230, 236)])],
}

if __name__ == '__main__':
    what = sys.argv.pop(1)
    if what == 'roi':
        roi.main()
    else:
        full = sheets.COLS
        _ghost = sheets.ghost_map
        def ghost_map(*args, **kw):
            sheets.COLS = full[:2] + GHOST_COLS
            try:
                _ghost(*args, **kw)
            finally:
                sheets.COLS = full
        sheets.ghost_map = ghost_map
        sheets.main()
