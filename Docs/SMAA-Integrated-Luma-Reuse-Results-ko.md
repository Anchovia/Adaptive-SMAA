# Integrated first-pass luma 재사용 검증

작성일: 2026-09-09. 분류: 출력 보존 최적화의 engineering gate. 최종 성능 결론이 아니다.

## 1. 목적과 변경 범위

기준 커밋은 `0a699ddcc026f3806cf8cf1ac1c56d884a9138e3`이다.
Integrated first-pass는 별도 full-screen edge pass를 실행하지 않지만, 후보 함수가
이미 계산한 중심·좌·상·우·하 luma를 다시 Load하고 있었다.
`Projects/CMAA2/SMAA/SMAAWrapper.hlsl`에서 이 다섯 값을 함수 인자로 전달하도록 변경했다.
좌상·좌하·우상 세 대각선 Load만 남긴다.

후보 판정 수식, threshold, removal, expansion, compact/indirect, spatial search,
jitter, reprojection, sampling, clipping, history weight와 feedback은 변경하지 않았다.
이는 새로운 후보 알고리즘이나 공식 TSCMAA 재현이 아니라 기존 SMAA adaptation의
중복 texture 읽기 제거다. Local-contrast tier 기반 새 후보 정책은 이번 범위가 아니다.

## 2. 재사용의 전제

현재 full-resolution edge draw에서 point/clamp sampler로 읽은 다섯 값과 기존 mip-0
integer Load는 동일 source SRV와 pixel을 가리킨다. RGB luma 계수와 raw-luma 경로도
각각 일치한다. 따라서 현재의 동일 해상도·pixel-center 경로에서 재사용한다.
임의 viewport, 서로 다른 입력 해상도 또는 다른 mip 설정까지 보증하는 결과는 아니다.

## 3. 셰이더 컴파일 검증

`Tools/SMAA/validate_integrated_luma_reuse.py`로 변경 전후 wrapper를 FXC 10.0.26100.0,
Ultra, `/O3 /Ges /WX`에서 비교했다. Integrated는 ps_5_0, 기존 spatial entry는 ps_4_1이다.
Original/Adaptive × RGB/raw × Integrated/기존 spatial의 8 variant가 모두 통과했다.

| Integrated variant | 추가 Load 전→후 | sample 전→후 | instruction slots 전→후 |
|---|---:|---:|---:|
| Original RGB | 8→3 | 7→7 | 144→114 |
| Original raw | 8→3 | 7→7 | 131→107 |
| Adaptive RGB | 8→3 | 7→7 | 145→117 |
| Adaptive raw | 8→3 | 7→7 | 132→110 |

변경하지 않은 기존 spatial entry 4 variant의 컴파일 bytecode hash는 전후 동일했다.
Load 명령 감소는 GPU 실행시간 또는 실제 VRAM traffic 감소율이 아니다.
선언된 temporary register 수는 Adaptive raw에서 6→7로 증가하므로 모든 자원이
일괄 감소했다고 표현하지 않는다.
C++ 변경은 없으며 이번에는 기존 Release x64 실행파일과 런타임 HLSL 컴파일을 사용했다.
전체 MSBuild 재빌드를 실시했다는 의미가 아니다.

## 4. 실제 GPU 출력·mask 비교

RTX 3060 Ti, 1920×1017에서 변경 전후 각각 독립 clean process로 실행했다.
캡처는 Hidden engineering capture이며 전체 PNG의 SHA-256을 비교했다.

| 자료 | 변경 전 run | 변경 후 run | 결과 |
|---|---|---|---|
| Bistro 최종 출력, 8 mode×12 frame | 20260909_141949 | 20260909_142410 | 84/96 동일, O-T2X 12 frame 차이 |
| Bistro debug view 2, 8 mode×12 frame | 20260909_142023 | 20260909_142441 | 96/96 동일 |
| Minecraft 최종 출력, 10 mode×6 frame | 20260909_142206 | 20260909_142541 | 60/60 동일 |
| Minecraft debug view 2, 10 mode×6 frame | 20260909_142241 | 20260909_142619 | 60/60 동일 |

직접 변경 영향을 받는 O/A-ET2X 및 O/A-ET2X-R의 최종 출력 72 frame과 대응 debug
mask 72 frame은 모두 byte-exact였다. Minecraft의 추가 두 mode는 O/A-1X control이다.
Standard mode의 debug 이미지까지 모두 후보 mask라고 부르지는 않는다.

Bistro O-T2X control 차이는 숨기거나 전체 8-mode PASS로 합치지 않는다.
수정된 함수는 이 mode에서 사용되지 않고 기존 spatial bytecode도 동일하지만,
이번 비교만으로 차이의 원인을 확정할 수 없다. 해당 control의 실행 간 결정성은
별도 재현 검증 대상으로 남긴다. 짧은 구간의 일치는 모든 경로·장면의 보증이 아니다.
3×3/ARM 확장 및 전체 parameter sweep 재측정은 이번 gate에 포함되지 않았다.

## 5. 성능: 단축 engineering 비교

Visible window, candidate readback Off, Bistro, warm-up 60 frame,
mode당 600 frame×3회로 측정했다. 전후 run은 각각 `20260909_142057`,
`20260909_142656`이다. 서로 다른 프로세스의 전후 비교이며 최종 4,800-frame
paired benchmark를 대체하지 않는다.

| Mode | SMAA 전(ms) | 후(ms) | 변화 |
|---|---:|---:|---:|
| O-ET2X | 0.222573 | 0.221317 | -0.56% |
| O-ET2X-R | 0.254826 | 0.253556 | -0.50% |
| A-ET2X | 0.195700 | 0.194740 | -0.49% |
| A-ET2X-R | 0.230046 | 0.228891 | -0.50% |

감소량은 약 0.001 ms다. 변경하지 않은 O-T2X와 O-T2X-R도 각각 -0.57%, -0.43%로
움직였고 Adaptive ET2X의 WholeFrame은 오히려 +0.68~0.83%였다.
따라서 이 결과로 통계적으로 확실한 가속이나 전체 frame 개선을 주장하지 않는다.
대규모 병목을 해소했다는 근거도 아니다. 확인한 것은 중복 명령 제거와 해당 캡처의
ET2X 출력 보존이며, 성능 효과의 분리는 추가 paired 측정이 필요하다.

## 6. Lifecycle와 재현 자료

`20260909_142817`의 `-smaaTemporalLifecycleTest`는 resets 60, frames 158,
seed 35, resolve 123, reprojection 92, failures 0으로 PASS했다.
실행 종료 후 잔류 CMAA2 프로세스는 0개였다.
원시 run은 `D:\SMAA-Research-Data\AutoBench`에 보존하며 Git에 포함하지 않는다.
로컬 `tmp/luma-reuse`에는 변경 전 wrapper, FXC 결과 및 전후 분석 JSON이 있다.

재컴파일 검증은 아래 인자를 사용한다. 변경 전 wrapper는 위 기준 커밋에서 준비한다.

```text
validate_integrated_luma_reuse.py --before <baseline-wrapper> --after <current-wrapper> --fxc <fxc.exe> --output <output-directory>
```

## 7. 다음 순서

후속 정정(2026-09-09): 아래 1번은 완료됐다. 같은 실행파일에서 준비 단계 분리 여부만
바꿔 O-T2X 시작 phase 차이를 확인했고, 교정된 96 PNG는 변경 전 baseline과 전부 일치했다.
자세한 검증 범위는 `SMAA-Temporal-Capture-Readiness-Determinism-ko.md`를 참고한다.

1. O-T2X control의 실행 간 차이를 재현·분리한다.
2. 성능 향상을 보고하려면 긴 전후 교차 paired 측정으로 약 0.001 ms 차이가 재현되는지 확인한다.
3. Contrast-tier 기반 후보 정책은 기존 정책을 보존한 독립 ablation으로 설계한다.
   후보 감소만으로 temporal 품질 또는 성능 개선이라고 판단하지 않는다.
