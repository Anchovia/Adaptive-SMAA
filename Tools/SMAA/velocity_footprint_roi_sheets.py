"""ROI numbers and nearest sheets of the velocity footprint capture, reusing the history rejection tools.

Two column sets keep the sheets as wide as before:
  sel: O-1X, O-T2X-R, selected, +(c), +(c'), +(c') Cross5, +(c') Footprint12, SS-Reference
  c19: O-1X, selected +(c'), case 19, 19 +(c'), 19 + Cross5, 19 + Footprint12, SS-Reference
The ghost map shows (c'), Cross5, Footprint12 and 19 + Footprint12.

usage: velocity_footprint_roi_sheets.py roi --scene bistro --run <run> --reference <SS-Reference> --out <json>
       velocity_footprint_roi_sheets.py sheets --set sel --scene bistro --run <run> --reference <SS-Reference> --out <dir> [sheet tool options]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import selected_history_rejection_roi as roi
import selected_history_rejection_sheets as sheets

SEL = roi.SEL
C19 = SEL + '+VelocityInEdge'
PP, X5, F12 = '+HistoryVelocityPingPong', '+HistoryVelocityPingPongCross5', '+HistoryVelocityPingPongFootprint12'
roi.MODES = [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('velocity', SEL + '+HistoryVelocityWeight'),
             ('pingpong', SEL + PP), ('cross5', SEL + X5), ('footprint12', SEL + F12), ('case19', C19),
             ('case19-pingpong', C19 + PP), ('case19-cross5', C19 + X5), ('case19-footprint12', C19 + F12)]
roi.ROIS['minecraft']['left-line-late'] = ((0, 96, 96, 144), range(120, 129))
SETS = {
    'sel': [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('선택 경로', SEL), ('+(c) alpha', SEL + '+HistoryVelocityWeight'),
            ("+(c') ping-pong", SEL + PP), ("+(c') Cross5", SEL + X5), ("+(c') Footprint12", SEL + F12), ('SS-Reference', None)],
    'c19': [('O-1X', 'O-1X'), ("선택 경로+(c')", SEL + PP), ('19번', C19), ("19번+(c')", C19 + PP),
            ("19번+(c') Cross5", C19 + X5), ("19번+(c') Footprint12", C19 + F12), ('SS-Reference', None)],
}
# ghost_map draws COLS[2:6]: here (c'), Cross5, Footprint12 and 19 + Footprint12.
GHOST_COLS = [("+(c') ping-pong", SEL + PP), ("+(c') Cross5", SEL + X5), ("+(c') Footprint12", SEL + F12),
              ("19번+(c') Footprint12", C19 + F12)]
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
        i = sys.argv.index('--set'); name = sys.argv[i + 1]; del sys.argv[i:i + 2]
        sheets.COLS = SETS[name]
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
