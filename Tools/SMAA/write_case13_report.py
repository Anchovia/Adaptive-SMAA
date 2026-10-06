"""Assemble only completed and verified case13 evidence."""
import json,subprocess
from pathlib import Path
from analyze_case13_quality import ROOT,DOC,MODES,load
from edge_quality_inputs import sha

def main():
    for scene in ['bistro','minecraft']:
        for frames in [240,720]:
            media=load(DOC/f'{scene}-media-{frames}.json')
            assert media['frames']==frames and media['mode_order']==MODES
            assert len(media['rois'])==3
            outputs=[media['full_video']]
            for roi in media['rois']:
                assert roi['gif']['decoded_frames_verified']
                outputs.extend([roi['video'],roi['gif']])
            for output in outputs:
                assert output['frames']==frames and sha(Path(output['path']))==output['sha256']
    benchmarks={s:load(DOC/f'{s}-benchmark.json') for s in ['bistro','minecraft']}
    quality={s:load(DOC/f'{s}-capture.json') for s in benchmarks}
    cgvqm={s:load(DOC/f'{s}-cgvqm.json') for s in benchmarks}
    long={s:load(DOC/f'{s}-long-capture.json') for s in benchmarks}
    for group in [benchmarks,quality,cgvqm,long]:
        assert all(d['validation']=='PASS' for d in group.values())
    def metric(scene,case,name):
        return next(r for r in benchmarks[scene]['summary'] if r['mode']==MODES[{4:0,10:1,11:2,13:3}[case]] and r['metric']==name)
    lines=['# ⑬: history RGB 재구성 필터 단독 실험 결과','',
        '⑬은 ⑫ 개선이 아닌 독립 ablation이다. 별도 브랜치 `experiment/edge-history-catmull-rom-reconstruction`에서 ⑪과 후보 선택·혼합 비중·feedback을 같게 유지하고 history RGB 필터 하나만 바꿨다. ⑫의 clipping·높은 누적 비중은 넣지 않았다. 기본 연구 구현과 최종 8-case 설정도 변경하지 않았다.','',
        '이번 필터 교체만으로 선 소실과 반짝임이 해결됐다고 판정하지 않는다. 일부 Minecraft 이음선은 더 선명하지만 프레임별 강약·단절이 남고 Bistro 의자 구조의 개선도 제한적이다. GPU 정확성 통과와 시각적 품질 개선은 별개다.','',
        '## 구현과 대조군','',
        '| 번호 | 구현 | paired pattern | history RGB | 다음 history |',
        '|---|---|---|---|---|',
        '|④|Original SMAA + 원본 전체 화면 T2X-R|On|원본 point|현재 spatial 프레임|',
        '|⑩|Original SMAA + 현재 OR 재투영 직전 raw edge|Off|bilinear 1-fetch|현재 spatial 프레임|',
        '|⑪|⑩의 선택 영역·원본 가중치 유지|Off|bilinear 1-fetch|resolved RGB / current spatial alpha|',
        '|⑬|⑪의 필터만 교체|Off|normalized Catmull–Rom 5-fetch 근사|⑪과 동일|','',
        '모두 camera/depth reprojection On, object velocity Off다. ⑩·⑪·⑬의 실제 입력·edge 선택·GPU 저장 혼합 비중은 두 장면 43개 trace frame씩 byte 동일하다. 비선택=current spatial, history RGB=visible resolve, alpha=current spatial 및 history chain/reset을 확인했다. ④↔⑬은 pattern과 feedback까지 다르므로 순수 후보 선택 효과가 아니다.','',
        '⑬은 [MJP의 공개 구현과 작성자의 5-tap 설명](https://gist.github.com/TheRealMJP/c83b8c0f46b63f3a88a5986f4fa982b1)을 참고한다. 네 모서리를 생략한 근사를 남은 가중치 합으로 정규화하며 원본 Intel 포팅으로 부르지 않는다. 단색·픽셀 중심 보존과 경계를 actual shared helper의 GPU probe로 검증했지만 ideal CPU와 GPU bilinear는 byte-exact가 아니다. 정확한 16-fetch 필터도 아니다. Negative lobe의 ringing 가능성을 유지하며 별도 clipping은 넣지 않았다.','',
        '## 성능','',
        'RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off. 장면별 새 독립 프로세스에서 같은 네 mode를 정/역순 교차하여 300 warm-up + 4,800 frame×6회 측정했다. 진단 readback·pipeline query·PNG Off이며 pass timestamp는 On이다. 전후 CMAA2 잔류 프로세스 0개, 같은 바이너리 Smoke/Benchmark 모두 PASS다. 숨긴 창의 중간 GPU scope 비교이며 visible 최종 8-case/FPS 결과로 일반화하지 않는다.','',
        '음수는 시간 감소다. 비율은 같은 run의 대응 ④/⑪로 계산한 여섯 비율의 평균이다. 절대 시간 평균끼리 나눈 값과 미세하게 다를 수 있다. 전체 AA에는 공간·edge 선택·camera velocity·resolve를 포함한다.','',
        '|장면|번호|전체 AA ms|④ 대비|temporal ms|temporal ④ 대비|전체 AA ⑪ 대비|',
        '|---|---|---:|---:|---:|---:|---:|']
    for scene in benchmarks:
        for case in [4,10,11,13]:
            a=metric(scene,case,'SMAA');t=metric(scene,case,'SR_Resolve')
            lines.append(f'|{scene}|{case}|{a["mean_ms"]:.6f}|{a["native4_paired_percent"]:+.2f}%|{t["mean_ms"]:.6f}|{t["native4_paired_percent"]:+.2f}%|{a["case11_paired_percent"]:+.2f}%|')
    lines+=['','⑬−⑪ paired 95% Student-t 구간(df5, 다중 비교 보정 없음):', '']
    for scene in benchmarks:
        a=metric(scene,13,'SMAA');t=metric(scene,13,'SR_Resolve')
        lines.append(f'- {scene}: 전체 AA {a["case11_paired_percent"]:+.3f}% / 구간 {a["case11_paired_percent_95_interval"]}; temporal {t["case11_paired_percent"]:+.3f}% / 구간 {t["case11_paired_percent_95_interval"]}.')
    lines+=['','반복 여섯 개는 장면별 한 프로세스 안의 반복이며 독립 세션 여섯 개가 아니다. 상세 median/p95/p99/stddev/WholeFrame/wall과 각 run은 `*-benchmark.json`, `*-performance-runs.csv`에 있다. 새 production pass/copy/texture는 ⑪ 대비 0개이고 history RGB fetch만 1→5다. ⑪이 지닌 spatial MRT/현재 입력 및 feedback 저장 비용은 남으므로 ⑩ 수준 속도로 돌아간다고 해석하지 않는다.','',
        '## 품질','',
        '무손실 연속 PNG 직접 검사를 우선한다. 두 장면의 moving f126–131, transition f178–183, still f190–195를 nearest 2배로 열었고 전체 f130/f180 및 창살·식생 이동 6프레임도 확인했다. 검사 기록과 구체적 한계는 `inspection.md`다. raw 시간 차분에는 카메라 이동·흐림이 포함되므로 절대 반짝임 지표가 아니다. supersample reference도 spatial proxy이며 temporal ground truth가 아니다.','',
        '|장면·얇은 구조 ROI|번호|이동 reference RGB MAE ↓|raw luma 2차 시간 차분|',
        '|---|---|---:|---:|']
    for scene in quality:
        for case in [4,10,11,13]:
            r=next(x for x in quality[scene]['roi_metrics'] if x['roi'].startswith('thin-') and x['window']=='moving' and x['mode']==MODES[{4:0,10:1,11:2,13:3}[case]])
            lines.append(f'|{scene}|{case}|{r["reference_rgb_mae"]:.5f}|{r["luma_second_delta"]:.5f}|')
    lines+=['','CGVQM-2(높을수록 좋음)는 보조 지표다. 공식 model/30-frame patch를 수정하지 않고 60-frame 호출을 equal-patch 평균했다. 입력 RGB와 FFV1 decoded round trip을 검증하고, ④·⑩·⑪ 점수는 현재 RGB/reference와 byte hash bridge를 통과한 기존 결과만 재사용했다. ⑬ 자체의 full-window 모델 재실행은 없으며 기존 native pooling bridge와 별개다.','',
        '|장면|구간|④|⑩|⑪|⑬|','|---|---|---:|---:|---:|---:|']
    for scene,data in cgvqm.items():
        for window in data['windows']:
            values={r['case']:r['score'] for r in window['records']}
            lines.append(f'|{scene}|{window["window"]}|'+ '|'.join(f'{values[c]:.6f}' for c in [4,10,11,13])+'|')
    lines+=['','정지 구간의 whole RGB 마지막 변경 frame:', '']
    for scene in quality:lines.append(f'- {scene}: {quality[scene]["whole_rgb_last_change"]}.')
    lines+=['','안정적인 정지 hash는 이동 중 선 보존이나 반짝임 해결을 의미하지 않는다. Minecraft 고정 screen strip f126–138의 실제 출력 대비·선택·weight는 `minecraft-line-contrast.json`에 있다. 물체 추적이나 절대 고스팅 점수로 사용하지 않는다.','',
        '## 확인 자료','',
        '- [240-frame 비교: 4초 60fps / 9.6초 GIF](../../../../Deliverables/SMAA_13_Quality_20261006/comparison.html)',
        '- [실제 720-frame 비교: 12초 60fps / 28.8초 GIF](../../../../Deliverables/SMAA_13_Long_20261006/comparison.html)',
        '- 두 장면 각각 3개 ROI, 각 갤러리 GIF 6개·crop 영상 6개·전체 경로 영상 2개. 손실 확인용 영상/GIF와 무손실 연속 PNG를 구분한다. 모든 출력 프레임을 decode해 frame 수·PTS·GIF pixel hash를 검증했다.',
        '- 긴 캡처는 실제 새 720프레임(정지60+이동600+정지60)이다. 처음180 공통 pose frame×4mode×2scene=1,440 RGB bridge mismatch 0이다. 이후 경로에 대응하는 supersample reference는 없으며 긴 영상을 정량 ground truth로 사용하지 않는다. 화면 고정 ROI가 같은 물체를 계속 추적하지도 않는다.','',
        '## 보존과 판단','',
        '⑫ 브랜치·자료는 유지했다. 새 ⑬은 필터 교체의 비용과 부분 선명도 효과를 분리하는 실험 기록으로 보존하며, 선 소실·반짝임 해결이나 최종 연구 구현으로 채택한 성공 결과로 표시하지 않는다. 사용자의 영상 검토와 별개로 확인한 결함을 성공으로 축소하지 않는다. 이번 단독 결과로 edge-selective 전체의 불가능을 증명한 것도 아니다.','',
        '기준 커밋·명시적 dependency·출처는 `method.md`, `sources.json`, `case.json`; build/shader/reference/clean-process provenance는 `provenance.json`과 각 receipt에 있다. binary, raw capture, DDS, PNG, GIF/MP4 및 AutoBench raw CSV는 Git에 올리지 않는다.','']
    # Links resolve from the branch Docs directory to the shared Deliverables directory.
    for index,line in enumerate(lines):
        if 'Deliverables/SMAA_13_' in line:
            lines[index]=line.replace('../../../../Deliverables','C:/Users/USER/Desktop/research/Deliverables')
    (DOC/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    case=load(DOC/'case.json');case['status']='engineering correctness verified; performance and auxiliary quality measured; visual shimmer/structure issue unresolved; default off'
    case['implementation_commit']=subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','rev-parse','537540e'],cwd=ROOT,text=True).strip()
    case['quality_adopted']=False
    (DOC/'case.json').write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS completed report; no quality-success claim')

if __name__=='__main__':main()
