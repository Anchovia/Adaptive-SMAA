# ①-⑰ 메일 공유 패키지

작업 브랜치: tooling/smaa-mail-comparison-package. 알고리즘과 재측정 결과는 변경하지 않았다.
기준 수치 커밋: 53d26a8f9028dd4c703843c6b87ce6ccd92ef763.

메일용 요약 ZIP: 19,905,151 bytes / 22 files. 전체 비교 ZIP: 5,643,225,723 bytes / 1,283 files.
ZIP은 Deliverables/SMAA_Mail_Package_20261008에 보관하며 Git에 추가하지 않는다.
메일에는 요약본을 첨부하고 전체본은 큰 파일 공유로 전달한다. 실제 메일 전송은 하지 않았다.
압축 해제 후 index.html을 열면 모든 링크가 오프라인 상대 경로로 동작한다.

- 8쪽 PDF: 구현 설명, 전체 AA 및 temporal 표, 공간 참조 PSNR/SSIM, 구조 소실 프레임, 미디어 사용법.
- 짧은 전체 비교: 2개 장면 × 16개 ④ 대비 pair, 실제 240frame/4s, 정상 MP4와 slow/fast GIF.
- 짧은 ROI: 의자·창문·얇은 이음선·나뭇잎·잔디 경계의 80 pair GIF와 무손실 PNG 검사.
- 긴 비교: ⑭~⑰ × 14개 view, 기존 검증된 720frame/12s 캡처에서 만든 56 MP4 / 112 GIF 재사용.
- 대표 메일 GIF: ④ 대비 ⑥·⑬·⑭·⑰, 두 ROI, f110~199 전부 유지, 실제 1.5s/재생 3.6s, 고정 128색.
- 원본 해상도 전체 PNG, moving/transition/settled 연속 검사, 원본 CSV 102개와 provenance 포함.

전체 화면 MP4는 640×354/side, GIF는 384×212/side로 축소. ROI는 nearest 2배.
MP4 갤러리의 0.5/1/2배 버튼은 같은 경로의 재생 속도 변경이며 새 camera-speed 실험이 아니다.
빠른 GIF는 stride2이므로 반짝임 판단에는 모든 프레임을 유지한 자료와 원본 PNG를 사용한다.
③·④ Pattern On, ⑤~⑰ Off. 품질 proxy를 temporal ground truth로 표현하지 않는다. CGVQM 재계산 없음.
긴 자료는 ⑭~⑰에만 있으며 모든 번호가 동일한 긴 경로로 새로 캡처된 것은 아니다.

## 검증과 한 프레임의 파생 해시 예외

모든 새 미디어는 source RGB hash와 대조했고, 모든 GIF는 decoded frame count/palette RGB/delay,
MP4는 60fps/count/PTS 단조성을 검증했다. ZIP 전체 CRC 및 모든 갤러리 링크를 검사했다.
PDF 최종 8페이지와 대표 GIF decoded frame을 직접 열었다. Animated 재생을 관찰했다고 주장하지 않는다.

Minecraft의 4,080프레임을 재확인하며 case5 f14 초기 정지 구간 한 프레임의 이전 파생 RGB hash 차이를 발견했다.
PNG SHA-256은 용량 정리 사전·사후 기록과 같고 repeated decode는 일정했다. 원인은 확정하지 않았다.
원본 PNG와 이전 hash artifact는 변경하지 않고 별도 근거를 남겼다. 품질 표의 moving/transition/settled 구간은
모두 기존 RGB hash와 일치하므로 수치는 유지했다. source-hash-correction.json과 source-recheck.json 참조.

## 재생성

기존 재측정 자료와 검증된 long pair 미디어를 보존한 상태에서 다음 도구를 사용한다.
Tools/SMAA/package_mail_comparisons.py --media bistro
Tools/SMAA/package_mail_comparisons.py --media minecraft
Tools/SMAA/package_mail_comparisons.py --mail-media
Tools/SMAA/package_mail_comparisons.py --report
Tools/SMAA/package_mail_comparisons.py --package

PDF를 재생성할 때 PDF skill의 marker 및 render/visual QA 절차를 수행한다.
번들 Python/Pillow/numpy/reportlab/PyAV, Windows Malgun/Consolas 폰트를 사용한다.
원본 PNG·실행 파일·장면 asset은 ZIP에 전체 복제하지 않고 기존 경로에 보존했다.
