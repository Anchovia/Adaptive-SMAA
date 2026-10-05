"""Publish measured cases 4/6/9/10 with original-frame review evidence."""
import json
from datetime import datetime, timezone
from pathlib import Path

from analyze_edge_bilinear_history_rgb import DOC, MODES, ROIS, ROOT
from edge_quality_inputs import sha

CASES = [4, 6, 9, 10]
NAMES = {4: '원본 SMAA T2X-R', 6: '현재 edge 선택', 9: '현재+직전 raw edge 선택', 10: '⑨+history RGB bilinear'}


def main():
    scores = json.loads((DOC / 'quality-review-cgvqm.json').read_text(encoding='utf-8'))
    png = json.loads((DOC / 'quality-review-png.json').read_text(encoding='utf-8'))
    assert len(scores) == 16
    assert len({(v['scene'], v['window'], v['case']) for v in scores}) == 16
    for record in scores:
        assert sha(Path(record['result_json'])) == record['result_sha256']
    score = {(v['scene'], v['window'], v['case']): v['score'] for v in scores}
    table = ['| 구성 | Bistro 이동 | Bistro 전환 | Minecraft 이동 | Minecraft 전환 |',
             '|---|---:|---:|---:|---:|']
    for case in CASES:
        values = [score[(scene, window, case)] for scene in ['bistro', 'minecraft'] for window in ['moving', 'transition']]
        circle = {4:'④',6:'⑥',9:'⑨',10:'⑩'}[case]
        table.append('| ' + f'{circle} {NAMES[case]}' + ' | ' + ' | '.join(f'{v:.6f}' for v in values) + ' |')
    rows = ['| 장면 | 구성 | 이동 전체 RGB MAE ↓ | 이동 전체 PSNR dB ↑ | 얇은 선 ROI MAE ↓ |',
            '|---|---|---:|---:|---:|']
    for scene in ['bistro', 'minecraft']:
        entry = next(v for v in png if v['scene'] == scene)
        roi = 'chair' if scene == 'bistro' else 'wall-seam'
        for case in CASES:
            full = next(v for v in entry['metrics'] if v['case']==case and v['window']=='moving' and v['roi']=='full')
            narrow = next(v for v in entry['metrics'] if v['case']==case and v['window']=='moving' and v['roi']==roi)
            rows.append(f"| {scene} | {case} | {full['rgb_mae']:.6f} | {full['pooled_psnr']:.4f} | {narrow['rgb_mae']:.6f} |")
    media = ROOT / 'tmp/edge-bilinear-history-rgb-media'
    inspections = []
    for scene in ['bistro', 'minecraft']:
        capture = json.loads((DOC / f'{scene}-capture.json').read_text(encoding='utf-8-sig'))
        full = [dict(path=str(Path(capture['capture_root']) / m / 'frame_00131.png'),
                     sha256=sha(Path(capture['capture_root']) / m / 'frame_00131.png'),
                     case=c, frame=131, resolution=[1920,1061]) for c,m in zip(CASES, MODES)]
        roi = 'chair' if scene == 'bistro' else 'wall-seam'
        wide = 'chairs-wide' if scene == 'bistro' else 'seam-wide'
        windows = dict(move=list(range(130,136)), before=list(range(127,133)),
                       after=list(range(133,139)), transition=list(range(178,184)), still=list(range(190,196)))
        sheets = [dict(path=str(media / f'{scene}-{roi}-{window}.png'),
                       sha256=sha(media / f'{scene}-{roi}-{window}.png'),
                       frames=frames, roi=ROIS[scene][roi], scale=2, filter='nearest')
                  for window,frames in windows.items()]
        sheets.append(dict(path=str(media / f'{scene}-{wide}-move.png'),
                           sha256=sha(media / f'{scene}-{wide}-move.png'),
                           frames=windows['move'], roi=ROIS[scene][wide], scale=2, filter='nearest',
                           tool_display_note='Original saved pixels; oversized sheet was resized by tool display'))
        inspections.append(dict(scene=scene, recorded_utc=datetime.now(timezone.utc).isoformat(),
                                full_originals_opened=full, consecutive_sheets_opened=sheets,
                                tone_adjustment=False, mode_order=CASES,
                                playback_viewed=False,
                                observation=('Minecraft f131/f134: case10 still loses the upper thin seam; f127-138 appearance/disappearance persists. Late still case9/case10 identical.'
                                             if scene=='minecraft' else
                                             'Bistro f127-138: case10 has local smoothing but thin chair/floor structure differs from native4. No demonstrated general shimmer/ghosting fix.')))
    (DOC / 'quality-review-visual-inspection.json').write_text(json.dumps(inspections,indent=2),encoding='utf-8')
    bridges = [dict(scene=v['scene'], window=v['window'], **v['record']['native_full_window_bridge']) for v in scores if v['case']==4]
    summary = dict(validation='PASS', case_order=CASES, measured_windows=16, accepted_official_model_invocations=24,
                   original_pngs_hash_checked=1920, rgb_hash_mismatch=0, native_bridges=bridges,
                   algorithm_changed=False, performance_rerun=False,
                   storage_policy='Original capture/reference PNGs and test FFV1 retained; temporary PNG copies and redundant encoded reference copies removed after validation',
                   adoption_decision='Pending user review of GIF, original frames and measured results',
                   visual_limitations=['Case10 thin-line disappearance remains', 'No independent object-motion/disocclusion ghosting evaluation',
                                       'Native4 pattern On; 6/9/10 Off', 'Supersample spatial proxy is not temporal ground truth'],
                   score_table=table, spatial_error_table=rows)
    (DOC / 'quality-review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    text = '\n'.join([
        '# ④·⑥·⑨·⑩ 품질 재평가 및 사용자 비교 자료', '',
        '⑩는 `ABL-ET2X-R-PreviousRawEdge-BilinearRGB`다. 현재+재투영 직전 raw edge의 선택은 ⑨와 같고,',
        'history RGB filtering만 point→bilinear로 바뀐다. Point alpha와 원본 adaptive weight는 유지한다.',
        '이번 작업은 같은 독립 실험 브랜치의 품질 평가 보완이며 렌더러·AA 구현·기준선은 수정하지 않았다.',
        '최종 채택 여부는 사용자 영상·원본 프레임 검토 후 결정한다.', '',
        '## 실제 수행 범위', '',
        '- 기존 실제 GPU 캡처의 두 장면×240프레임×4구성=1,920 PNG를 읽어 저장 RGB hash와 일치 검증했다.',
        '- 전체 화면과 두 ROI의 RGB MAE·PSNR을 다시 계산했다. 새 GPU 캡처 또는 속도 재측정은 하지 않았다.',
        '- CGVQM-2 이동60–179와 전환160–219를 네 구성·두 장면에서 평가했다. 총16 window/24개 완료 모델 프로세스다.',
        '- 같은 frame131의 네 구성 원본 전체 PNG, 이동130–135·전후127–138·전환178–183·정지190–195의',
        '  nearest2× 연속 sheet를 이번 요청에서 직접 열었다. 넓은 ROI의 이동 sheet도 검사했다.',
        '- ④·⑥·⑨·⑩ 순서의 GIF25FPS/7.2초와 MP4 60FPS/3초를 재생성하고 decode로 길이·순서·PTS를 검증했다.',
        '  실제 실시간 재생을 시청했다고 표현하지 않는다. 직접 관찰은 원본 PNG와 연속 sheet에 근거한다.', '',
        '## CGVQM-2', '',
        '높을수록 좋다. 전체 화면의 보조 지표이며 얇은 선의 연속성이나 고스팅만을 평가하는 점수가 아니다.', '',
        *table, '',
        '## Supersample spatial proxy 대비 오차', '',
        '동일 pose/index의 spatial proxy를 사용한다. 절대 temporal ground truth가 아니다. RGB MAE는 8-bit level이다.', '',
        *rows, '',
        '## 원본 프레임 관찰', '',
        '- Minecraft f131/f134의 ⑩에는 얇은 세로선 상단의 단절·소실이 남는다. f127–138 출현·소멸도 관찰된다.',
        '  이를 단순 선명도 차이로 축소하지 않는다. 대표 f131(971,544)의 ⑨ RGB=(142,140,131),',
        '  ⑩=(150,148,138)로 이 위치에서는 선이 더 약해진다. f134에는 반대 방향의 변화도 있다.',
        '- Bistro 의자/바닥 ROI에서는 국소적인 filtering 변화가 있지만 원본④의 얇은 구조를 모두 회복하지 못한다.',
        '- 두 장면 f190–239에서 ⑨·⑩ RGB는50프레임 모두 같았다. 정지 안정성과 이동 품질은 구분한다.',
        '- 독립 object-motion/disocclusion 장면을 이번에 평가하지 않았으므로 전역 고스팅 개선을 확정하지 않는다.',
        '- ④는 jitter/subsample On, ⑥·⑨·⑩는 Off다. RGB filter 효과의 직접 대조는⑨↔⑩다.',
        '- 수치가 높거나 오차가 작더라도, 위 선 소실을 품질 동등·개선 성공으로 덮지 않는다.', '',
        '## 공식 평가 경계 및 제외 실행', '',
        'Intel 공식 CGVQM commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`과 CUDA/patch_scale4/mean pooling을 사용했다.',
        '모델과 공식 소스를 수정하지 않았다. 긴120프레임 실행의 CPU 메모리 부족 후, 기존 절차의60프레임',
        '독립 호출을 사용했다. 공식30프레임 temporal patch 경계를 유지하며 동일 patch 수의 mean score를 합친다.',
        '부동소수 reduction 순서 차이를 고려해 두 장면의④ 이동/전환을 기존 full-window score와2e-5 이내로 검증했다.',
        '모든 완료 호출에서 test/reference FFV1 decoded RGB mismatch0이다. 원본 해상도1920×1061 및 공식 spatial padding은 유지했다.',
        '최종 PNG만 포함한 입력은 원본 파일을 바이트 그대로 복사하고 SHA-256을 비교했다. 진단 PNG는 평가 입력에 넣지 않았다.',
        '완료된 장면의 임시 PNG 복사본과 반복 생성한 참조 FFV1 복사본은 저장 공간을 위해 제거했다.',
        '원본 test/reference PNG, test FFV1, 결과·로그 및 해시 불일치 제외 실행은 보존했다. 참조 FFV1은 원본 PNG로 재생성할 수 있다.',
        '120프레임 OOM, 진단 PNG 이름 검증 실패, 일부 번호만 복사한 초기 입력 집합 검증 실패는 점수 없이 제외했다.',
        'Minecraft⑨ 전환의 최초 모델 결과는 입력 metadata hash가 원본/복사본의 hash와 달라 별도로 보존하고 제외했다.',
        '독립 재읽기는 두 환경에서 같은 원본 hash를 냈지만 최초 불일치 원인은 확정하지 않았다. 새 프로세스에서 재평가한 검증 결과만 채택했다.',
        '각 실패는 평가 입력 준비 단계이며 AA 코드를 수정한 것이 아니다.', '',
        '## 비교 자료', '',
        f'- [Bistro GIF25FPS]({(media / "bistro-sampler-slow.gif").as_posix()})',
        f'- [Minecraft GIF25FPS]({(media / "minecraft-sampler-slow.gif").as_posix()})',
        f'- [Bistro MP4 60FPS]({(media / "bistro-sampler-60fps.mp4").as_posix()})',
        f'- [Minecraft MP4 60FPS]({(media / "minecraft-sampler-60fps.mp4").as_posix()})',
        'GIF 공통256색 palette와 H.264는 표시 보조 자료다. 평가는 원본 PNG로 수행했다.', '',
    ])
    (DOC / 'quality-review.md').write_text(text, encoding='utf-8')
    media_info=json.loads((DOC/'media.json').read_text(encoding='utf-8'))
    for v in media_info: v['case_order']=CASES
    (DOC/'media.json').write_text(json.dumps(media_info,indent=2),encoding='utf-8')
    print('\n'.join(table),flush=True)
    print('QUALITY_REVIEW_PASS: measured outputs and inspected images; adoption pending user review',flush=True)


if __name__=='__main__': main()
