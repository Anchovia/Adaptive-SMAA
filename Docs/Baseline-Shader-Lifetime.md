# 원본 기준선 실행의 셰이더 종료 수명 보완

독립 항목: `tooling/baseline-shader-lifetime`, base `baseline/smaa-t2x` (`88893da`).
기존 검증된 수정 `684ac91`에서 `vaRendering.h`, `vaShader.h` 두 파일의 수정만 재사용한다.
원본과 해당 기존 수정의 parent 사이에서 두 파일의 차이가 없음을 확인했다.
파생 객체를 소멸시키기 전에 shared-owner deleter가 비동기 shader 작업을 기다린다.
SMAA 알고리즘, sampler, jitter, history와 후보 선택은 수정하지 않는다.

원본 독립 Minecraft 캡처 `20260928_165112`는 1440 PNG와 Aggregate PASS를 저장한 후
종료 코드 -1073740791로 실패했다. 이 실행은 정식 데이터에서 제외한다.
종료 시점과 알려진 수명 문제에 근거해 기존 수정을 적용하는 것이며, 이 기록만으로
해당 crash의 전체 원인을 확정하지 않는다. 수정 후 clean-process 재실행으로 확인한다.

검증 브랜치는 이 커밋을 명시적으로 cherry-pick하여 재실행한다. 이전 연구 알고리즘이나
다른 실험 브랜치 전체를 통합하지 않는다. 현재 재검증 결과는 검증 브랜치 보고서에 기록한다.
