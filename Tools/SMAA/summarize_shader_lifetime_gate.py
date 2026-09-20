"""Publish bounded startup regression evidence and DX11 profiling limitations."""
import argparse,csv,hashlib,json,subprocess
from pathlib import Path
from validate_shader_lifetime import report,bridge
root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('gate',type=Path);p.add_argument('--profiler',type=Path,required=True);a=p.parse_args()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}',*args],cwd=root,text=True).strip()
assert not git('diff','b6d5245','--','Projects/CMAA2/SMAA','Modules/Rendering/Shaders')
checks=read(a.gate/'checks.json');smokes=read(a.gate/'smokes.json');captures=read(a.gate/'captures.json')
assert len(checks)==5 and len(smokes)==6 and len(captures)==2
assert {c['kind'] for c in checks}=={'expected-buffer-failure','expected-file-failure','lifetime'}
assert len({r['executable_sha256'] for r in checks+smokes+captures})==1
assert all(r['exit_code']==(0 if r['kind']=='lifetime' else 1) for r in checks)
lifetimes=[report(Path(r['report'])) for r in checks if r['kind']=='lifetime'];assert len(lifetimes)==3
for scene in ['bistro','minecraft']:
    assert sum(r['scene']==scene for r in smokes)==3
    assert sum(r['scene']==scene for r in captures)==1
smoke_results=[]
for r in smokes:
    path=Path(r['report']);text=path.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[[v.strip() for v in row] for row in csv.reader(text.splitlines()) if row and row[0].strip()=='timing']
    assert len(rows)==25 and all(row[2]=='0' and row[4]=='240' and float(row[5])>0 for row in rows)
    assert len({row[1] for row in rows})==5 and len({(row[1],row[3]) for row in rows})==25
    smoke_results.append(dict(scene=r['scene'],path=str(path),sha256=digest(path),modes=5,measured_frames_per_mode=240))
old={'bistro':'20260920_102001','minecraft':'20260920_102304'}
bridges={r['scene']:bridge(Path(r['report']).parent,root/'Projects/CMAA2/AutoBench'/old[r['scene']]) for r in captures}
profiler=read(a.profiler);assert not profiler['shader_hardware_stall_or_divergence_measured']
result=dict(classification='Startup correctness and tool capability gate; no new GPU speed or quality claim',
    implementation_commit=git('log','-1','--format=%H','--','Modules/Rendering/vaAssetPack.cpp'),
    aa_shader_diff_from_b6d5245='',
    executable_sha256=checks[0]['executable_sha256'],checks=checks,lifetimes=lifetimes,smokes=smoke_results,
    captures=bridges,profiler=profiler,
    excluded_run=dict(run='20260920_182136',pid=2464,executable_sha256='BED9ADC7FB2E418E4310F563EE347246AC2EBEDEE6018B2E66267ED8E70DF875',
        reason='Worker modal compiler-error waits, Albedo input macro undeclared; owned loop and process terminated, no finalized result'),
    limitations=['Original 0xc0000409 failing object was not identified; no proof that every startup failure has the same cause.',
        'Final finite regression passes do not establish absence of all races.',
        'DX11 only; shared header is compiled with DX12 modules but DX12 runtime is untested.',
        'Profiler trace used the earlier ownership-only executable; it is not the final executable performance measurement.'])
out=root/'Docs/Shader-Lifetime-and-DX11-Profiling';out.mkdir(parents=True,exist_ok=True)
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
n=profiler['ranges']['SMAATemporalResolve']
text=f'''# 시작 안정성 보완과 DX11 계측 결과

비동기 셰이더의 파괴 순서와 재질 입력의 조기 공개를 수정했다. 최종 실행파일에서 독립 정상 실행
11회(수명 3회, smoke 6회, capture 2회)가 완료됐고, 두 장면 총 3,360장 출력은 수정 전과 동일했다.
추가로 의도적인 compiler failure 두 실행은 종료 코드 1로 거부됐다. 이것은 안정성·정확성 검증이며
새로운 AA 속도 또는 품질 개선 결과가 아니다.

## 구현

- shared owner의 마지막 해제에서 compile task를 기다린 뒤 객체 파괴를 시작한다.
- APACK/unpacked 재질은 모든 입력을 읽은 뒤 기존 asset-pack 등록 단계에서 UID에 공개한다.
- 자동 실행의 DX11 compiler 오류는 숨겨진 확인 창 대신 진단 로그와 실패 종료로 전달한다.
  일반 interactive 실행의 오류 확인 동작은 유지한다.

공식 근거, 적용 범위와 재현 명령은 [method.md](method.md)를 따른다.

## 최종 검증

| 항목 | 결과 |
|---|---|
| Release x64 / DX11 | 빌드 및 실행 PASS |
| 지연 compile 작업의 owner 해제 | 32회 ×3 프로세스, 작업 완료 후 destructor 진입 |
| 여섯 shader stage의 shared/auto factory | 3회 PASS |
| 미초기화 재질 UID 비공개→초기화→등록 | 3회 PASS |
| 실제 PS/CS compile 직후 해제 및 PS reload | 3회 PASS, 잔류 compile 0 / shader 개수 복원 |
| 잘못된 buffer/file shader 주입 | 각각 exit 1, 오류 로그 확인, 잔류 데모 0 |
| Bistro/Minecraft 시작·종료 smoke | 각각 독립 3회, 5 mode ×240 측정 frame, 모든 CSV PASS |
| Bistro 수정 전후 PNG | 7 mode ×240 frame, SHA-256 mismatch 0 |
| Minecraft 수정 전후 PNG | 7 mode ×240 frame, SHA-256 mismatch 0 |

최종 EXE SHA-256: `{result['executable_sha256']}`.
각 실행 ID, CSV hash, sequence hash 및 계측 receipt는 [results.json](results.json)에 기록했다.
원시 capture와 profiler 파일은 로컬 AutoBench/tmp에 보존하며 Git에 넣지 않는다.

## 실제 계측 범위

설치된 Nsight Systems 2026.3.1로 Minecraft DX11 추적을 실제 수집했다.
`SMAATemporalResolve` CPU annotation {n['instances']:,}개가 있으며 CPU 평균
{n['mean_cpu_ns']/1000:.3f} us, 중앙값 {n['median_cpu_ns']/1000:.3f} us였다.
이는 GPU의 약 25~39 us resolve 시간과 다른 값이다. warm-up과 다섯 mode가 섞인
계측 실행의 CPU 구간 요약이므로 mode별 속도 비교나 GPU 병목 결론에 사용하지 않는다.

실제 SQLite에는 DX11 PIX annotation과 DXGI 정보가 있지만 개별 D3D11 Draw API table 및
GPU_METRICS는 없다. GPU 전체 counter 지원 조회는 RTX 3060 Ti의
`Insufficient privilege / ERR_NVGPUCTRPERM`으로 거부됐다. GPU가 지원되지 않는다는 뜻으로
바꾸어 표현하지 않는다. 시스템 전체 성능 카운터 허용 정책은 변경하지 않았다.
최신 Nsight Graphics의 공식 지원표에는 DX11 shader profiling 지원이 없다.

따라서 **warp divergence, cache miss, instruction stall의 지배적인 원인은 여전히 미측정**이다.
추가 분석에는 관리자 권한의 제한된 계측 실행과 특정 temporal 작업에 귀속할 수 있는 수집 설계가
필요하다. 권한만 얻은 전체 GPU 평균으로 짧은 temporal pass의 원인을 확정하지 않는다.

## 실패 기록과 해석 한계

수명 수정만 적용한 중간 EXE의 `20260920_182136`은 shader 오류 확인 대기로 멈췄다.
live unwind에서 main의 join 및 worker의 MessageBox 대기를 확인했고, 해당 프로세스의 compiler
진단에서 `VA_RM_INPUT_LOAD_Albedo` 미선언을 확인했다. 이 실행은 결과에서 제외하고 이번 작업의
측정 루프와 데모만 종료했다. 이후 재질 조기 공개와 자동 오류 처리를 함께 수정했다.
관련 진단은 `tmp/lifetime-stall-threads.txt`, `tmp/lifetime-stall-detail.txt`,
`tmp/lifetime-stall-log.txt`에 보존했다.

이전 `20260920_103030`의 `_purecall` 실패 객체는 특정하지 못했다. 이번에 확인·수정한 수명
위험과 일관되지만 동일 원인으로 확정하지 않는다. 최종 유한 횟수 검사 통과도 모든 시작 오류의
영구 해결을 보장하지 않는다. AA 출력이 동일하므로 기존 선택 방식의 깜빡임·고스팅 한계도 그대로다.
'''
(out/'report.md').write_text(text,encoding='utf-8');print('Published',out)
